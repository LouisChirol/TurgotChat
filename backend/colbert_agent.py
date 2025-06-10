import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mistralai import ChatMistralAI
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from colbert_prompt import COLBERT_PROMPT, OUTPUT_PROMPT
from redis_service import RedisService
from retrieval import DocumentRetrieved, DocumentRetriever

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY environment variable is not set")

# RAG parameters
TOP_K_RETRIEVAL = 15
TOP_N_SOURCES = 4

# Paths
WORKSPACE_ROOT = Path(__file__).parent.parent
CHROMA_DB_PATH = WORKSPACE_ROOT / "database" / "chroma_db"


class ColbertResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str | None = Field(
        description="The answer to the user's question", default=None
    )
    sources: list[str] | None = Field(
        description="The sources used to answer the user's question, should be a list of urls",
        default=None,
    )


class ColbertAgent:
    def __init__(self):
        # Initialize Redis service
        self.redis_service = RedisService()

        # Initialize document retriever
        self.retriever = DocumentRetriever()

        self.llm = ChatMistralAI(
            model="mistral-medium-latest",
            temperature=0,
            max_retries=2,
            timeout=120,
            api_key=MISTRAL_API_KEY,
        )

    def get_redis_history(self, session_id: str):
        history = self.redis_service.get_history(session_id)
        logger.debug(f"History: {history}")
        return history

    def _strip_code_blocks(self, text: str) -> str:
        """Remove Markdown code block formatting from a string."""
        # Remove triple backtick code blocks
        text = re.sub(r"```[a-zA-Z]*\n?", "", text)
        text = text.replace("```", "")
        # Remove single backtick inline code
        text = text.replace("`", "")
        return text.strip()

    def _format_response(self, response: ColbertResponse) -> str:
        """Format the response with sources using markdown."""
        # Format the answer with proper spacing and line breaks
        formatted_answer = self._strip_code_blocks(response.answer.strip())

        # Format sources as markdown links with prefix
        if response.sources:
            sources_text = "\n\n## Fiches complètes:\n"
            sources_text += """\nNous vous recommandons de consulter les fiches complètes pour plus d'informations.
            La réponse est un résumé des informations contenues dans ces fiches, et ne doit pas être considérée comme exhaustive.\n"""
            for source in response.sources:
                sources_text += f"- [{source}]({source})\n"
            formatted_answer += sources_text

        return formatted_answer

    def _format_context(self, docs: list[DocumentRetrieved]) -> str:
        """Format the retrieved elements into context for the LLM."""
        if not docs:
            return "Aucun document pertinent n'a été trouvé pour cette question."

        context = "CONTEXTE - Documents officiels trouvés :\n\n"

        for doc in docs:
            context += f"Document {doc.id} (URL: {doc.sp_url}):\n"
            context += "Extraits pertinents:\n"
            context += f"{doc.page_content}\n"
            context += "---\n\n"

        context += "INSTRUCTION: Basez votre réponse UNIQUEMENT sur les informations contenues dans ces documents. "
        context += "Si les documents contiennent des informations contradictoires ou incomplètes, mentionnez-le clairement."

        return context

    def ask_colbert(self, message: str, session_id: str) -> str:
        colbert_response = ColbertResponse()
        try:
            # Get conversation history
            history = self.get_redis_history(session_id)
            # Extract messages from the history object
            history_messages = history.messages if hasattr(history, "messages") else []
            logger.debug(f"Messages of history: {len(history_messages)}")

            # Generate query
            query = self.retriever.generate_search_query(message, history)
            logger.debug(f"Vector db query: {query}")

            # Retrieve and process documents
            docs = self.retriever.retrieve_documents(
                query, top_k=TOP_K_RETRIEVAL, max_docs=TOP_N_SOURCES
            )
            context = self._format_context(docs)
            colbert_response.sources = [doc.sp_url for doc in docs]

            messages = [
                SystemMessage(content=COLBERT_PROMPT),
                SystemMessage(content=OUTPUT_PROMPT),
                *history_messages,  # Unpack the actual history messages
                HumanMessage(content=message),
                HumanMessage(content=context),
            ]
            logger.critical(f"len(messages): {len(str(messages))}")
            # Generate answer using medium model
            logger.debug("Generating answer...")
            llm_response = self.llm.invoke(messages)
            colbert_response.answer = llm_response.content

            if not docs:
                colbert_response.answer = (
                    "Note: Je n'ai pas trouvé d'informations spécifiques dans ma base de données "
                    "pour répondre à votre question. Je vais donc répondre en me basant sur mes "
                    "connaissances générales. Veuillez noter que cette réponse n'est pas "
                    "nécessairement spécifique au contexte français ou aux services publics français.\n\n"
                ) + colbert_response.answer
                colbert_response.sources = ["https://www.service-public.fr"]

            # Format the response
            logger.debug(f"Response: {colbert_response}")
            output = self._format_response(colbert_response)

            # Store messages in history
            self.redis_service.store_message(
                session_id, {"role": "user", "content": message}
            )
            self.redis_service.store_message(
                session_id, {"role": "assistant", "content": output}
            )

            return output

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            logger.exception("Full traceback:")
            return (
                "Désolé, une erreur est survenue lors de la génération de la réponse."
            )
