import hashlib
import os
import sqlite3
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
EMBEDDING_BATCH_SIZE = 20
MAX_THREADS = 8
MAX_DOCUMENTS = -1
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 100
BATCH_DELAY = 0.5
MAX_RETRIES = 3


class DocumentTracker:
    """Tracks processed documents to enable incremental processing."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_tracking_table()
    
    def init_tracking_table(self):
        """Initialize the tracking table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_tracking (
                    file_path TEXT PRIMARY KEY,
                    last_modified REAL,
                    content_hash TEXT,
                    data_source TEXT,
                    processed_at REAL,
                    chunk_count INTEGER
                )
            """)
            conn.commit()
    
    def get_file_info(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Get tracking information for a file."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT last_modified, content_hash, data_source, processed_at, chunk_count FROM document_tracking WHERE file_path = ?",
                (str(file_path),)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'last_modified': row[0],
                    'content_hash': row[1],
                    'data_source': row[2],
                    'processed_at': row[3],
                    'chunk_count': row[4]
                }
        return None
    
    def update_file_info(self, file_path: Path, content_hash: str, data_source: str, chunk_count: int):
        """Update tracking information for a file."""
        current_time = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO document_tracking 
                (file_path, last_modified, content_hash, data_source, processed_at, chunk_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(file_path), current_time, content_hash, data_source, current_time, chunk_count))
            conn.commit()
    
    def remove_file_info(self, file_path: Path):
        """Remove tracking information for a file (when file is deleted)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM document_tracking WHERE file_path = ?", (str(file_path),))
            conn.commit()
    
    def get_all_tracked_files(self) -> List[str]:
        """Get all tracked file paths."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT file_path FROM document_tracking")
            return [row[0] for row in cursor.fetchall()]


class IncrementalXMLParser:
    def __init__(self, data_dirs: List[str]):
        self.data_dirs = [Path(data_dir) for data_dir in data_dirs]
        self.initial_doc_count = 0

        # Initialize document tracker
        self.tracker = DocumentTracker("chroma_db/chroma.sqlite3")

        # Validate data directories exist and contain XML files
        total_xml_files = 0
        for data_dir in self.data_dirs:
            if not data_dir.exists():
                raise ValueError(f"Data directory does not exist: {data_dir}")
            
            xml_files = list(data_dir.rglob("*.xml"))
            if not xml_files:
                logger.warning(f"No XML files found in {data_dir}")
            else:
                total_xml_files += len(xml_files)
                logger.info(f"Found {len(xml_files)} XML files in {data_dir}")

        if total_xml_files == 0:
            raise ValueError(f"No XML files found in any of the provided directories")

        logger.info(f"Total XML files found: {total_xml_files}")

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

    def compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file content."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def has_file_changed(self, file_path: Path) -> bool:
        """Check if a file has changed since last processing."""
        if not file_path.exists():
            return False
        
        # Get current file info
        current_mtime = file_path.stat().st_mtime
        current_hash = self.compute_file_hash(file_path)
        
        # Get stored file info
        stored_info = self.tracker.get_file_info(file_path)
        
        if not stored_info:
            logger.debug(f"New file detected: {file_path}")
            return True
        
        # Check if modification time or content hash has changed
        if stored_info['last_modified'] != current_mtime or stored_info['content_hash'] != current_hash:
            logger.debug(f"File changed: {file_path}")
            return True
        
        logger.debug(f"File unchanged: {file_path}")
        return False

    def remove_deleted_documents(self):
        """Remove documents from vector store for files that no longer exist."""
        tracked_files = self.tracker.get_all_tracked_files()
        deleted_files = []
        
        for file_path_str in tracked_files:
            file_path = Path(file_path_str)
            if not file_path.exists():
                deleted_files.append(file_path_str)
                logger.info(f"File deleted: {file_path_str}")
        
        if deleted_files:
            logger.info(f"Removing {len(deleted_files)} deleted files from tracking")
            for file_path_str in deleted_files:
                self.tracker.remove_file_info(Path(file_path_str))
                # Note: We could also remove from vector store, but that's more complex
                # For now, we just remove from tracking

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
            
            # Add data source identifier based on file path
            if "vosdroits" in str(file_path):
                metadata["data_source"] = "vosdroits"
            elif "entreprendre" in str(file_path):
                metadata["data_source"] = "entreprendre"
            else:
                metadata["data_source"] = "unknown"
            
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
            
            # Update tracking information
            content_hash = self.compute_file_hash(file_path)
            self.tracker.update_file_info(file_path, content_hash, metadata["data_source"], len(chunks))
            
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
        hash_ids = [hashlib.md5(text.encode()).hexdigest() for text in texts]
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

        return total_success, total_errors

    def process_directory(self):
        """Process only changed XML files incrementally."""
        # First, remove tracking for deleted files
        self.remove_deleted_documents()
        
        # Collect all XML files
        all_xml_files = []
        for data_dir in self.data_dirs:
            xml_files = list(data_dir.rglob("*.xml"))[:MAX_DOCUMENTS]
            all_xml_files.extend(xml_files)
        
        # Filter for changed files only
        changed_files = [f for f in all_xml_files if self.has_file_changed(f)]
        
        logger.info(f"Found {len(changed_files)} changed files out of {len(all_xml_files)} total files")
        
        if not changed_files:
            logger.info("No files have changed since last processing. Nothing to do.")
            return

        total_success = 0
        total_errors = 0

        for file_path in tqdm(changed_files, desc="Processing changed files"):
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

        logger.info("Incremental processing complete!")
        logger.info(f"Documents added: {added_docs}")
        logger.info(f"Successful: {total_success}")
        logger.info(f"Failed: {total_errors}")

        if added_docs != total_success:
            logger.error(f"Document count mismatch! Expected {total_success}, got {added_docs}")
        else:
            logger.success("All changed documents processed successfully")


def main():
    # Process both vosdroits and entreprendre data sources
    data_directories = [
        "data/service-public/vosdroits-latest",
        "data/service-public/entreprendre-latest"
    ]
    
    parser = IncrementalXMLParser(data_directories)
    parser.process_directory()


if __name__ == "__main__":
    main() 