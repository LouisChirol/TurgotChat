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
EMBEDDING_BATCH_SIZE = 20  # Increased batch size for higher rate limits
MAX_THREADS = 8  # Increased threads for parallel processing
MAX_DOCUMENTS = -1  # Keep the same control parameter, -1 for all
CHUNK_SIZE = 2000  # Keep the same chunk size
CHUNK_OVERLAP = 100  # Keep the same overlap
BATCH_DELAY = 0.5  # Reduced delay between batches due to higher rate limits
MAX_RETRIES = 3  # Keep the same retry logic


class XMLParserV2:
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

        # Initialize text splitter
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
        logger.info(f"Initial document count: {self.initial_doc_count}")

    def extract_text_content(self, element: ET.Element) -> str:
        """Extract text content from XML element and its children without duplication."""
        text_parts = []
        if element.text and element.text.strip():
            text_parts.append(element.text.strip())

        for child in element:
            child_text = self.extract_text_content(child)
            if child_text:
                text_parts.append(child_text)
            if child.tail and child.tail.strip():
                text_parts.append(child.tail.strip())

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
            tree = ET.parse(file_path)
            root = tree.getroot()

            content = self.extract_text_content(root)
            metadata = self.extract_metadata(root)

            if not content.strip():
                return []

            metadata["source_file"] = str(file_path)
            chunks = self.text_splitter.split_text(content)

            if not chunks:
                return []

            documents = []
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
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
            return self.embeddings.embed_documents(texts)
        except Exception as e:
            if "429" in str(e):
                logger.warning(f"Rate limit hit, retrying: {str(e)}")
                raise
            logger.error(f"Error getting embeddings: {str(e)}")
            raise

    def embed_and_insert_batch(self, batch: List[Dict[str, Any]]) -> Tuple[int, int]:
        """Embed a batch of documents and insert them into the vector store."""
        if not batch:
            return 0, 0

        texts = [doc["content"] for doc in batch]
        metadatas = [doc["metadata"] for doc in batch]
        hash_ids = [md5(text.encode()).hexdigest() for text in texts]
        ids = [f"doc_{i}_{hash_id}" for i, hash_id in enumerate(hash_ids)]

        try:
            embeddings = self.get_embeddings_batch(texts)
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

        batches = [
            documents[i : i + EMBEDDING_BATCH_SIZE]
            for i in range(0, len(documents), EMBEDDING_BATCH_SIZE)
        ]

        total_success = 0
        total_errors = 0

        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            future_to_batch = {
                executor.submit(self.embed_and_insert_batch, batch): i
                for i, batch in enumerate(batches)
            }

            for future in as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                try:
                    success, errors = future.result()
                    total_success += success
                    total_errors += errors
                except Exception as e:
                    logger.error(f"Batch {batch_idx + 1} failed: {str(e)}")
                    total_errors += len(batches[batch_idx])

                    logger.error(f"Batch {batch_idx + 1} failed: {str(e)}")
                    total_errors += len(batches[batch_idx])

        return total_success, total_errors

    def process_directory(self):
        """Process XML files sequentially, but process batches from each file in parallel."""
        xml_files = list(self.data_dir.rglob("*.xml"))[:MAX_DOCUMENTS]
        logger.info(f"Processing {len(xml_files)} XML files")

        total_success = 0
        total_errors = 0

        for file_path in tqdm(xml_files, desc="Processing files"):
            try:
                documents = self.process_xml_file(file_path)
                if not documents:
                    continue

                success, errors = self.process_file_batches(documents, file_path)
                total_success += success
                total_errors += errors

                time.sleep(BATCH_DELAY)

            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
                continue

        final_doc_count = self.vector_store._collection.count()
        added_docs = final_doc_count - self.initial_doc_count

        logger.info("Processing complete!")
        logger.info(f"Documents added: {added_docs}")
        logger.info(f"Successful: {total_success}")
        logger.info(f"Failed: {total_errors}")

        if added_docs != total_success:
            logger.error(f"Document count mismatch! Expected {total_success}, got {added_docs}")
        else:
            logger.success("All documents added successfully")


def main():
    parser = XMLParserV2("data/service-public")
    parser.process_directory()


if __name__ == "__main__":
    main() 