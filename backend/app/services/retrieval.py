import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

# Constants
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY environment variable is not set")

# Determine if we're running in Docker container
IS_DOCKER = os.path.exists("/.dockerenv")

# Set database path based on environment
if IS_DOCKER:
    CHROMA_DB_PATH = Path("/app/database/chroma_db")
    XML_FILES_PATH = Path("/app/database")
else:
    # Go up from backend/app/services/ to project root
    WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
    CHROMA_DB_PATH = WORKSPACE_ROOT / "database" / "chroma_db"
    XML_FILES_PATH = WORKSPACE_ROOT / "database"

logger.info(f"Using database path: {CHROMA_DB_PATH}")


class DocumentRetrieved(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(description="L'identifiant du document", default=None)
    source_file: str | None = Field(
        description="Le chemin du fichier source du document", default=None
    )
    sp_url: str | None = Field(description="L'URL du document", default=None)
    page_content: str | None = Field(description="Le contenu du document", default=None)


class DocumentRetriever:
    def __init__(self):
        # Initialize vector store
        self.embeddings = MistralAIEmbeddings(
            model="mistral-embed", api_key=MISTRAL_API_KEY
        )

        # Ensure the chroma_db directory exists
        CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)

        # Initialize vector store
        self.vector_store = Chroma(
            collection_name="service_public",
            embedding_function=self.embeddings,
            persist_directory=str(CHROMA_DB_PATH),
        )

        # Initialize small model for query generation and document synthesis
        self.query_llm = ChatMistralAI(
            model="mistral-small-latest",
            temperature=0,
            max_retries=2,
            api_key=MISTRAL_API_KEY,
        )

        # Create the query generation prompt
        self.query_system_prompt = """Vous êtes un assistant qui génère des requêtes de recherche.
        Étant donné une question de l'utilisateur et l'historique de conversation,
        vous devez générer une requête optimisée pour la recherche de documents dans une base de données vectorielle (RAG).
        La requête doit être en français et doit être concise.
        """

        # Log initial document count
        self.doc_count = self.vector_store._collection.count()
        logger.info(
            f"Initialized Chroma DB with {self.doc_count} documents at {CHROMA_DB_PATH}"
        )

    def generate_search_query(
        self, question: str, history: list[dict]
    ) -> tuple[str, str]:
        """Generate a search query and concise summary from the user question and history."""
        # Format history for the prompt
        history_text = (
            "\n".join([f"{msg.type}: {msg.content}" for msg in history.messages])
            if hasattr(history, "messages")
            else ""
        )
        logger.critical(f"History length: {len(history_text)}")
        try:
            # Generate query and summary using structured output
            messages = [
                SystemMessage(content=self.query_system_prompt),
                HumanMessage(content=f"History: {history_text}"),
                HumanMessage(content=f"Question: {question}"),
            ]

            result = self.query_llm.invoke(messages)
            logger.debug(f"Query generation response: {result}")
            return result.content

        except Exception as e:
            logger.error(f"Error generating query and summary: {str(e)}")
            logger.exception("Full traceback:")
            logger.warning("Using original question as fallback")
            return question

    def merge_document_pair(
        self, doc1: DocumentRetrieved, doc2: DocumentRetrieved
    ) -> DocumentRetrieved:
        """Merge two documents into a single one."""
        page_content = f"{doc1.page_content}\n\n{doc2.page_content}"
        return DocumentRetrieved(
            id=doc1.id,
            source_file=doc1.source_file,
            sp_url=doc1.sp_url,
            page_content=page_content,
        )

    def merge_documents(self, docs: list[DocumentRetrieved]) -> list[DocumentRetrieved]:
        """Merge documents with the same ID into a single one."""
        merged_docs = {}

        for doc in docs:
            if doc.id not in merged_docs:
                merged_docs[doc.id] = doc
            else:
                merged_docs[doc.id] = self.merge_document_pair(merged_docs[doc.id], doc)

        return list(merged_docs.values())

    def retrieve_documents(
        self, query: str, top_k: int = 20, max_docs: int = 5
    ) -> list[DocumentRetrieved]:
        """Retrieve documents from the vector store and deduplicate by ID."""
        docs = self.vector_store.similarity_search(query, k=top_k)
        retrieved_docs = [
            DocumentRetrieved(
                id=doc.metadata.get("ID"),
                source_file=doc.metadata.get("source_file", ""),
                sp_url=doc.metadata.get("spUrl"),
                page_content=doc.page_content,
            )
            for doc in docs
        ]
        retrieved_docs = self.merge_documents(retrieved_docs)

        logger.info(
            f"Retrieved {len(retrieved_docs)} unique documents from {len(docs)} total matches; cutting to {max_docs}"
        )
        retrieved_docs = retrieved_docs[:max_docs]
        return retrieved_docs
