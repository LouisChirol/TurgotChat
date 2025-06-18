import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mistralai import ChatMistralAI
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from app.core.prompts import CLASSIFICATION_PROMPT, OUTPUT_PROMPT, TURGOT_PROMPT
from app.services.redis import RedisService
from app.services.retrieval import DocumentRetrieved, DocumentRetriever
from app.utils.tokens import create_message_trimmer

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY environment variable is not set")

# RAG parameters
TOP_K_RETRIEVAL = 15
TOP_N_SOURCES = 4

# Token limits
MAX_TOKENS = 32000  # Mistral Medium context limit
RESERVED_TOKENS = 8000  # Reserve for output and safety margin

# Paths
WORKSPACE_ROOT = Path(__file__).parent.parent.parent
CHROMA_DB_PATH = WORKSPACE_ROOT / "database" / "chroma_db"


class TurgotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str | None = Field(
        description="The answer to the user's question", default=None
    )
    sources: list[str] | None = Field(
        description="The sources used to answer the user's question, should be a list of urls",
        default=None,
    )


class TurgotAgent:
    def __init__(self):
        # Initialize Redis service
        self.redis_service = RedisService()

        # Initialize document retriever
        self.retriever = DocumentRetriever()

        # Initialize message trimmer
        self.message_trimmer = create_message_trimmer(
            max_tokens=MAX_TOKENS - RESERVED_TOKENS, model_name="mistral-medium-latest"
        )

        self.llm = ChatMistralAI(
            model="mistral-medium-latest",
            temperature=0,
            max_retries=2,
            timeout=120,
            api_key=MISTRAL_API_KEY,
        )

        # Initialize small model for RAG classification
        self.classifier_llm = ChatMistralAI(
            model="mistral-small-latest",
            temperature=0,
            max_retries=2,
            api_key=MISTRAL_API_KEY,
        )

    def _needs_rag(self, message: str, history_messages: list) -> bool:
        """Determine if the user's message requires RAG retrieval."""
        try:
            # Create classification messages
            messages = [
                SystemMessage(content=CLASSIFICATION_PROMPT),
                HumanMessage(content=f"Question: {message}"),
            ]

            # Add recent history context if available (last 2 messages max)
            if history_messages:
                recent_history = history_messages[-2:]
                history_context = "\n".join(
                    [
                        f"{msg.type}: {msg.content[:100]}..."
                        if len(msg.content) > 100
                        else f"{msg.type}: {msg.content}"
                        for msg in recent_history
                    ]
                )
                messages.insert(
                    1, HumanMessage(content=f"Contexte récent: {history_context}")
                )

            result = self.classifier_llm.invoke(messages)
            classification = result.content.strip().upper()

            needs_rag = classification == "OUI"
            logger.info(
                f"RAG classification for '{message[:50]}...': {classification} -> needs_rag={needs_rag}"
            )

            return needs_rag

        except Exception as e:
            logger.error(f"Error in RAG classification: {str(e)}")
            # Default to True if classification fails (safer approach)
            logger.warning("Defaulting to RAG=True due to classification error")
            return True

    def _generate_simple_response(self, message: str, history_messages: list) -> str:
        """Generate a response without RAG for simple queries."""
        messages = [
            SystemMessage(content=TURGOT_PROMPT),
            SystemMessage(
                content="Tu réponds sans utiliser de documents de référence. Sois naturel et utile."
            ),
            *history_messages,
            HumanMessage(content=message),
        ]

        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Error generating simple response: {str(e)}")
            return "Bonjour ! Je suis Turgot, votre assistant pour les démarches administratives françaises. Comment puis-je vous aider aujourd'hui ? 😊"

    def _convert_to_message_dicts(self, langchain_messages: list) -> list[dict]:
        """Convert LangChain messages to simple dictionaries for token counting."""
        message_dicts = []
        for msg in langchain_messages:
            if hasattr(msg, "type") and hasattr(msg, "content"):
                role = "user" if msg.type == "human" else msg.type
                message_dicts.append({"role": role, "content": msg.content})
        return message_dicts

    def _convert_to_langchain_messages(self, message_dicts: list[dict]) -> list:
        """Convert message dictionaries back to LangChain messages."""
        langchain_messages = []
        for msg in message_dicts:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            else:  # user, assistant, or other
                langchain_messages.append(HumanMessage(content=content))

        return langchain_messages

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

    def _extract_sources_from_docs(self, docs: list[DocumentRetrieved]) -> list[str]:
        """Extract valid sources from documents, filtering out None values.

        Some documents in the XML files may not have spUrl attributes,
        which results in None values. This method filters them out to ensure
        only valid URLs are included in the response sources.

        The order of sources matches the order of documents as retrieved,
        maintaining the relevance ranking from the vector search.

        Args:
            docs: List of DocumentRetrieved objects from vector search

        Returns:
            List of valid URL strings, filtered and ordered by relevance
        """
        sources = []
        invalid_count = 0
        for doc in docs:
            if doc.sp_url is not None and doc.sp_url.strip():
                sources.append(doc.sp_url)
            else:
                invalid_count += 1
                logger.warning(f"Document {doc.id} has invalid sp_url: {doc.sp_url}")

        if invalid_count > 0:
            logger.info(
                f"Filtered out {invalid_count} documents with invalid URLs. Valid sources: {len(sources)}"
            )

        return sources

    def _format_response(self, response: TurgotResponse) -> str:
        """Format the response with sources using markdown."""
        # Format the answer with proper spacing and line breaks
        formatted_answer = self._strip_code_blocks(response.answer.strip())

        # Format sources as markdown links with prefix
        if response.sources and len(response.sources) > 0:
            # Check if the response already contains sources section (various formats)
            lower_answer = formatted_answer.lower()
            has_sources_section = any(keyword in lower_answer for keyword in [
                "## fiches complètes",
                "## sources",
                "### fiches complètes", 
                "### sources",
                "**fiches complètes**",
                "**sources**"
            ])
            
            if not has_sources_section:
                sources_text = "\n\n## Fiches complètes:\n"
                sources_text += """\nNous vous recommandons de consulter les fiches complètes pour plus d'informations.
                La réponse est un résumé des informations contenues dans ces fiches, et ne doit pas être considérée comme exhaustive.\n"""
                for source in response.sources:
                    sources_text += f"- [{source}]({source})\n"
                formatted_answer += sources_text
            else:
                logger.info("Response already contains sources section, skipping duplicate")

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

    def ask_turgot(self, message: str, session_id: str) -> str:
        try:
            # Get conversation history
            history = self.get_redis_history(session_id)
            history_messages = history.messages if hasattr(history, "messages") else []
            logger.debug(f"Messages of history: {len(history_messages)}")

            # Determine if RAG is needed
            needs_rag = self._needs_rag(message, history_messages)

            if not needs_rag:
                # Generate simple response without RAG
                logger.info("Generating simple response without RAG")

                # Convert history to dict format for token trimming
                history_dicts = self._convert_to_message_dicts(history_messages)

                # Trim messages to fit token limit (more conservative for simple responses)
                trimmed_history_dicts, total_tokens = (
                    self.message_trimmer.trim_messages(
                        history_dicts,
                        system_messages=[{"role": "system", "content": TURGOT_PROMPT}],
                        context_text="Tu réponds sans utiliser de documents de référence. Sois naturel et utile.",
                    )
                )

                # Convert back to LangChain format
                trimmed_history = self._convert_to_langchain_messages(
                    trimmed_history_dicts
                )

                logger.info(
                    f"Simple response: using {total_tokens} tokens ({len(trimmed_history)} messages)"
                )

                answer = self._generate_simple_response(message, trimmed_history)

                # Store messages in history
                self.redis_service.store_message(
                    session_id, {"role": "user", "content": message}
                )
                self.redis_service.store_message(
                    session_id, {"role": "assistant", "content": answer}
                )

                return answer

            # RAG-based response
            logger.info("Generating RAG-based response")
            turgot_response = TurgotResponse()

            # Generate query
            query = self.retriever.generate_search_query(message, history)
            logger.debug(f"Vector db query: {query}")

            # Retrieve and process documents
            docs = self.retriever.retrieve_documents(
                query, top_k=TOP_K_RETRIEVAL, max_docs=TOP_N_SOURCES
            )
            context = self._format_context(docs)

            # Extract valid sources (filter out None values)
            turgot_response.sources = self._extract_sources_from_docs(docs)

            # Prepare system messages
            system_messages = [
                {"role": "system", "content": TURGOT_PROMPT},
                {"role": "system", "content": OUTPUT_PROMPT},
            ]

            # Convert history to dict format for token trimming
            history_dicts = self._convert_to_message_dicts(history_messages)

            # Add current user message to history for trimming calculation
            all_messages = history_dicts + [{"role": "user", "content": message}]

            # Trim messages to fit token limit
            trimmed_messages, total_tokens = self.message_trimmer.trim_messages(
                all_messages, system_messages=system_messages, context_text=context
            )

            # Convert back to LangChain format and reconstruct message list
            trimmed_langchain = self._convert_to_langchain_messages(
                trimmed_messages[:-1]
            )  # Exclude current message

            messages = [
                SystemMessage(content=TURGOT_PROMPT),
                SystemMessage(content=OUTPUT_PROMPT),
                *trimmed_langchain,  # Use trimmed history
                HumanMessage(content=message),
                HumanMessage(content=context),
            ]

            logger.info(
                f"RAG response: using {total_tokens} tokens ({len(trimmed_messages)} trimmed messages)"
            )

            # Generate answer using medium model
            logger.debug("Generating answer...")
            start_time = time.time()
            llm_response = self.llm.invoke(messages)
            end_time = time.time()
            logger.debug(f"Time taken: {end_time - start_time} seconds")
            turgot_response.answer = llm_response.content

            if not docs:
                turgot_response.answer = (
                    "Note: Je n'ai pas trouvé d'informations spécifiques dans ma base de données "
                    "pour répondre à votre question. Je vais donc répondre en me basant sur mes "
                    "connaissances générales. Veuillez noter que cette réponse n'est pas "
                    "nécessairement spécifique au contexte français ou aux services publics français.\n\n"
                ) + turgot_response.answer
                turgot_response.sources = ["https://www.service-public.fr"]

            # Format the response
            logger.debug(f"Response: {turgot_response}")
            output = self._format_response(turgot_response)

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
