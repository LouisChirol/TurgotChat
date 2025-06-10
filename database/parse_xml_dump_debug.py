import os
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import md5
from pathlib import Path
from typing import Any, Dict, List, Tuple

import backoff
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_mistralai import MistralAIEmbeddings
from loguru import logger
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Constants
EMBEDDING_BATCH_SIZE = 10  # Batch size for embedding API calls
MAX_THREADS = 4  # Number of parallel threads for processing batches
MAX_DOCUMENTS = 100  # Process fewer documents for debugging
CHUNK_SIZE = 2000  # Larger chunks to reduce total number of documents
CHUNK_OVERLAP = 100  # Smaller overlap
BATCH_DELAY = 2  # Delay between batches in seconds
MAX_RETRIES = 3  # Maximum number of retries for rate-limited requests


class XMLParserDebug:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.initial_doc_count = 0

        # Validate data directory exists
        if not self.data_dir.exists():
            raise ValueError(f"Data directory does not exist: {self.data_dir}")

        # Validate data directory contains XML files
        xml_files = list(self.data_dir.rglob("*.xml"))
        if not xml_files:
            raise ValueError(f"No XML files found in {self.data_dir}")

        logger.info(f"Found {len(xml_files)} XML files in {self.data_dir}")

        # Use larger chunks to reduce total number of documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
        )

        # Initialize embeddings with retry logic
        self.embeddings = MistralAIEmbeddings(
            model="mistral-embed",
            api_key=os.getenv("MISTRAL_API_KEY"),
            max_retries=MAX_RETRIES,
        )

        # Create chroma_db directory if it doesn't exist
        persist_dir = Path("chroma_db")
        persist_dir.mkdir(exist_ok=True)

        # Initialize vector store
        self.vector_store = Chroma(
            collection_name="service_public",
            embedding_function=self.embeddings,
            persist_directory=str(persist_dir),
        )

        # Get initial document count
        self.initial_doc_count = self.vector_store._collection.count()
        logger.info(f"Initial document count in vector store: {self.initial_doc_count}")

    def extract_text_content(self, element: ET.Element) -> str:
        """Extract text content from XML element and its children without duplication."""
        # Get direct text content of the element
        text_parts = []
        if element.text and element.text.strip():
            text_parts.append(element.text.strip())

        # Process child elements
        for child in element:
            # Get text from child element
            child_text = self.extract_text_content(child)
            if child_text:
                text_parts.append(child_text)
            # Get tail text (text after the child element)
            if child.tail and child.tail.strip():
                text_parts.append(child.tail.strip())

        # Join all text parts with a single space
        return " ".join(text_parts)

    def extract_metadata(self, element: ET.Element) -> Dict[str, Any]:
        """Extract metadata from XML element."""
        metadata = {}

        # Extract Dublin Core metadata
        for dc_elem in element.findall(".//{http://purl.org/dc/elements/1.1/}*"):
            tag = dc_elem.tag.split("}")[-1]
            metadata[tag] = dc_elem.text

        # Extract other important attributes
        for attr in element.attrib:
            if attr in ["ID", "type", "spUrl", "dateCreation", "dateMaj"]:
                metadata[attr] = element.attrib[attr]

        return metadata

    def process_xml_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Process a single XML file and return chunks with metadata."""
        try:
            logger.debug(f"Processing file: {file_path}")
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Extract main content
            content = self.extract_text_content(root)
            metadata = self.extract_metadata(root)

            # Skip if content is empty
            if not content.strip():
                logger.warning(f"Skipping {file_path}: Empty content")
                return []

            # Add file information to metadata
            metadata["source_file"] = str(file_path)

            # Split content into chunks
            chunks = self.text_splitter.split_text(content)
            logger.debug(f"Created {len(chunks)} chunks for {file_path}")

            # Skip if no chunks were created
            if not chunks:
                logger.warning(f"Skipping {file_path}: No chunks created")
                return []

            # Create documents with metadata
            documents = []
            for i, chunk in enumerate(chunks):
                if not chunk.strip():  # Skip empty chunks
                    continue
                doc = {
                    "content": chunk,
                    "metadata": {
                        **metadata,
                        "chunk_id": i,
                        "total_chunks": len(chunks),
                    },
                }
                documents.append(doc)
            return documents

        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")
            return []

    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=MAX_RETRIES,
        giveup=lambda e: "429" not in str(e),
    )
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a batch of texts with retry logic."""
        try:
            embeddings = self.embeddings.embed_documents(texts)
            return embeddings
        except Exception as e:
            if "429" in str(e):
                logger.warning(
                    f"Rate limit hit while getting embeddings, retrying: {str(e)}"
                )
                raise
            logger.error(f"Error getting embeddings: {str(e)}")
            raise

    def embed_and_insert_batch(self, batch: List[Dict[str, Any]]) -> Tuple[int, int]:
        """Embed a batch of documents and insert them into the vector store.
        Returns (success_count, error_count)"""
        if not batch:
            return 0, 0

        texts = [doc["content"] for doc in batch]
        metadatas = [doc["metadata"] for doc in batch]

        # Generate unique IDs for each document
        hash_ids = [md5(text.encode()).hexdigest() for text in texts]
        ids = [f"doc_{i}_{hash_id}" for i, hash_id in enumerate(hash_ids)]

        try:
            # Get embeddings for the batch
            embeddings = self.get_embeddings_batch(texts)

            # Add documents to vector store
            self.vector_store._collection.add(
                ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas
            )

            return len(batch), 0
        except Exception as e:
            logger.error(f"Error in embed_and_insert_batch: {str(e)}")
            return 0, len(batch)

    def process_file_batches(
        self, documents: List[Dict[str, Any]], file_path: Path
    ) -> Tuple[int, int]:
        """Process all batches from a single file in parallel."""
        if not documents:
            return 0, 0

        # Split documents into batches
        batches = [
            documents[i : i + EMBEDDING_BATCH_SIZE]
            for i in range(0, len(documents), EMBEDDING_BATCH_SIZE)
        ]
        logger.info(
            f"Processing {len(documents)} documents from {file_path} in {len(batches)} batches"
        )

        total_success = 0
        total_errors = 0

        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            future_to_batch = {
                executor.submit(self.embed_and_insert_batch, batch): i
                for i, batch in enumerate(batches)
            }

            for future in tqdm(
                as_completed(future_to_batch),
                total=len(batches),
                desc=f"Processing batches from {file_path.name}",
            ):
                batch_idx = future_to_batch[future]
                try:
                    success, errors = future.result()
                    total_success += success
                    total_errors += errors
                    if success > 0:
                        logger.debug(
                            f"Batch {batch_idx + 1}/{len(batches)}: {success} documents added"
                        )
                    if errors > 0:
                        logger.warning(
                            f"Batch {batch_idx + 1}/{len(batches)}: {errors} documents failed"
                        )
                except Exception as e:
                    logger.error(f"Batch {batch_idx + 1} failed: {str(e)}")
                    total_errors += len(batches[batch_idx])

        return total_success, total_errors

    def process_directory(self):
        """Process XML files sequentially, but process batches from each file in parallel."""
        xml_files = list(self.data_dir.rglob("*.xml"))[:MAX_DOCUMENTS]
        logger.info(f"Processing first {len(xml_files)} XML files for debugging")

        total_success = 0
        total_errors = 0

        # Process XML files sequentially
        for file_path in tqdm(xml_files, desc="TOTAL PROGRESS OVER XML FILES"):
            try:
                # Process XML file into documents
                documents = self.process_xml_file(file_path)
                if not documents:
                    continue

                # Process all batches from this file in parallel
                success, errors = self.process_file_batches(documents, file_path)
                total_success += success
                total_errors += errors

                # Add delay between files to avoid rate limits
                time.sleep(BATCH_DELAY)

            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                continue

        # Final verification
        final_doc_count = self.vector_store._collection.count()
        added_docs = final_doc_count - self.initial_doc_count

        logger.info("Processing complete!")
        logger.info(f"Initial document count: {self.initial_doc_count}")
        logger.info(f"Final document count: {final_doc_count}")
        logger.info(f"Total documents added: {added_docs}")
        logger.info(f"Total successful documents: {total_success}")
        logger.info(f"Total failed documents: {total_errors}")

        if added_docs != total_success:
            logger.error(
                f"Document count mismatch! Expected to add {total_success} but added {added_docs}"
            )
        else:
            logger.success("Success! All documents were added correctly.")


def main():
    # Use the correct path to the XML files
    parser = XMLParserDebugV2("data/service-public")
    parser.process_directory()


if __name__ == "__main__":
    main()
