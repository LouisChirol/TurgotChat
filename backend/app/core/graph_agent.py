import os
import re
import time
from pathlib import Path
from typing import Any, List, Literal

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mistralai import ChatMistralAI
from langgraph.graph import END, StateGraph
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
MAX_TOKENS = 32000
RESERVED_TOKENS = 8000


class GraphState(BaseModel):
    """State shared across all nodes in the graph."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Input
    message: str
    session_id: str
    
    # History and context
    history: Any = None
    history_messages: List[Any] = Field(default_factory=list)
    
    # Classification
    needs_rag: bool = False
    
    # RAG components
    search_query: str = ""
    documents: List[DocumentRetrieved] = Field(default_factory=list)
    context: str = ""
    sources: List[str] = Field(default_factory=list)
    
    # Token management
    trimmed_history: List[Any] = Field(default_factory=list)
    total_tokens: int = 0
    
    # Response
    answer: str = ""
    formatted_response: str = ""
    
    # Error handling
    error: str | None = None


class TurgotGraphAgent:
    """LangGraph-based implementation of the Turgot agent."""
    
    def __init__(self):
        # Initialize services
        self.redis_service = RedisService()
        self.retriever = DocumentRetriever()
        
        # Initialize message trimmer
        self.message_trimmer = create_message_trimmer(
            max_tokens=MAX_TOKENS - RESERVED_TOKENS, model_name="mistral-medium-latest"
        )
        
        # Initialize LLMs
        self.llm = ChatMistralAI(
            model="mistral-medium-latest",
            temperature=0,
            max_retries=2,
            timeout=120,
            api_key=MISTRAL_API_KEY,
        )
        
        self.classifier_llm = ChatMistralAI(
            model="mistral-small-latest",
            temperature=0,
            max_retries=2,
            api_key=MISTRAL_API_KEY,
        )
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(GraphState)
        
        # Add all nodes
        workflow.add_node("load_history", self._load_history)
        workflow.add_node("classify_query", self._classify_query)
        workflow.add_node("generate_simple_response", self._generate_simple_response)
        workflow.add_node("generate_search_query", self._generate_search_query)
        workflow.add_node("retrieve_documents", self._retrieve_documents)
        workflow.add_node("format_context", self._format_context)
        workflow.add_node("generate_rag_response", self._generate_rag_response)
        workflow.add_node("format_response", self._format_response)
        workflow.add_node("store_messages", self._store_messages)
        
        # Define the flow
        workflow.set_entry_point("load_history")
        workflow.add_edge("load_history", "classify_query")
        
        # Conditional routing after classification
        workflow.add_conditional_edges(
            "classify_query",
            self._route_after_classification,
            {
                "simple": "generate_simple_response",
                "rag": "generate_search_query"
            }
        )
        
        # Simple response path
        workflow.add_edge("generate_simple_response", "store_messages")
        
        # RAG response path
        workflow.add_edge("generate_search_query", "retrieve_documents")
        workflow.add_edge("retrieve_documents", "format_context")
        workflow.add_edge("format_context", "generate_rag_response")
        workflow.add_edge("generate_rag_response", "format_response")
        workflow.add_edge("format_response", "store_messages")
        
        # End
        workflow.add_edge("store_messages", END)
        
        return workflow.compile()
    
    def _load_history(self, state: GraphState) -> GraphState:
        """Load conversation history from Redis."""
        try:
            logger.debug(f"Loading history for session: {state.session_id}")
            
            history = self.redis_service.get_history(state.session_id)
            history_messages = history.messages if hasattr(history, "messages") else []
            
            logger.debug(f"Loaded {len(history_messages)} history messages")
            
            return state.model_copy(update={
                "history": history,
                "history_messages": history_messages,
                "error": None
            })
            
        except Exception as e:
            logger.error(f"Error loading history: {str(e)}")
            return state.model_copy(update={
                "history": None,
                "history_messages": [],
                "error": f"Failed to load history: {str(e)}"
            })
    
    def _classify_query(self, state: GraphState) -> GraphState:
        """Classify whether the query needs RAG or can be answered simply."""
        try:
            logger.debug(f"Classifying query: {state.message[:50]}...")
            
            messages = [
                SystemMessage(content=CLASSIFICATION_PROMPT),
                HumanMessage(content=f"Question: {state.message}"),
            ]
            
            # Add recent history context if available (last 2 messages max)
            if state.history_messages:
                recent_history = state.history_messages[-2:]
                history_context = "\n".join([
                    f"{msg.type}: {msg.content[:100]}..."
                    if len(msg.content) > 100
                    else f"{msg.type}: {msg.content}"
                    for msg in recent_history
                ])
                messages.insert(
                    1, HumanMessage(content=f"Contexte récent: {history_context}")
                )
            
            result = self.classifier_llm.invoke(messages)
            classification = result.content.strip().upper()
            needs_rag = classification == "OUI"
            
            logger.info(f"Classification result: {classification} -> needs_rag={needs_rag}")
            
            return state.model_copy(update={
                "needs_rag": needs_rag,
                "error": None
            })
            
        except Exception as e:
            logger.error(f"Error in classification: {str(e)}")
            # Default to RAG if classification fails (safer approach)
            logger.warning("Defaulting to RAG=True due to classification error")
            return state.model_copy(update={
                "needs_rag": True,
                "error": None  # Don't treat this as a fatal error
            })
    
    def _route_after_classification(self, state: GraphState) -> Literal["simple", "rag"]:
        """Route to either simple or RAG response based on classification."""
        return "simple" if not state.needs_rag else "rag"
    
    def _generate_simple_response(self, state: GraphState) -> GraphState:
        """Generate a simple response without RAG."""
        try:
            logger.info("Generating simple response without RAG")
            
            # Convert history to dict format for token trimming
            history_dicts = self._convert_to_message_dicts(state.history_messages)
            
            # Trim messages to fit token limit
            trimmed_history_dicts, total_tokens = self.message_trimmer.trim_messages(
                history_dicts,
                system_messages=[{"role": "system", "content": TURGOT_PROMPT}],
                context_text="Tu réponds sans utiliser de documents de référence. Sois naturel et utile.",
            )
            
            # Convert back to LangChain format
            trimmed_history = self._convert_to_langchain_messages(trimmed_history_dicts)
            
            logger.info(f"Simple response: using {total_tokens} tokens ({len(trimmed_history)} messages)")
            
            # Generate response
            messages = [
                SystemMessage(content=TURGOT_PROMPT),
                SystemMessage(content="Tu réponds sans utiliser de documents de référence. Sois naturel et utile."),
                *trimmed_history,
                HumanMessage(content=state.message),
            ]
            
            response = self.llm.invoke(messages)
            answer = response.content
            
            return state.model_copy(update={
                "answer": answer,
                "formatted_response": answer,  # For simple responses, no additional formatting needed
                "trimmed_history": trimmed_history,
                "total_tokens": total_tokens,
                "error": None
            })
            
        except Exception as e:
            logger.error(f"Error generating simple response: {str(e)}")
            fallback_answer = "Bonjour ! Je suis Turgot, votre assistant pour les démarches administratives françaises. Comment puis-je vous aider aujourd'hui ? 😊"
            return state.model_copy(update={
                "answer": fallback_answer,
                "formatted_response": fallback_answer,
                "error": f"Simple response generation failed: {str(e)}"
            })
    
    def _generate_search_query(self, state: GraphState) -> GraphState:
        """Generate a search query for RAG retrieval."""
        try:
            logger.debug("Generating search query for RAG")
            
            query = self.retriever.generate_search_query(state.message, state.history)
            logger.debug(f"Generated search query: {query}")
            
            return state.model_copy(update={
                "search_query": query,
                "error": None
            })
            
        except Exception as e:
            logger.error(f"Error generating search query: {str(e)}")
            # Fallback to original message
            return state.model_copy(update={
                "search_query": state.message,
                "error": f"Search query generation failed, using original message: {str(e)}"
            })
    
    def _retrieve_documents(self, state: GraphState) -> GraphState:
        """Retrieve documents using the search query."""
        try:
            logger.debug(f"Retrieving documents for query: {state.search_query}")
            
            docs = self.retriever.retrieve_documents(
                state.search_query, 
                top_k=TOP_K_RETRIEVAL, 
                max_docs=TOP_N_SOURCES
            )
            
            logger.info(f"Retrieved {len(docs)} documents")
            
            return state.model_copy(update={
                "documents": docs,
                "error": None
            })
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            return state.model_copy(update={
                "documents": [],
                "error": f"Document retrieval failed: {str(e)}"
            })
    
    def _format_context(self, state: GraphState) -> GraphState:
        """Format retrieved documents into context for the LLM."""
        try:
            docs = state.documents
            
            if not docs:
                context = "Aucun document pertinent n'a été trouvé pour cette question."
                sources = []
            else:
                context = "CONTEXTE - Documents officiels trouvés :\n\n"
                sources = []
                
                for doc in docs:
                    context += f"Document {doc.id} (URL: {doc.sp_url}):\n"
                    context += "Extraits pertinents:\n"
                    context += f"{doc.page_content}\n"
                    context += "---\n\n"
                    
                    # Extract valid sources
                    if doc.sp_url is not None and doc.sp_url.strip():
                        sources.append(doc.sp_url)
                
                context += "INSTRUCTION: Basez votre réponse UNIQUEMENT sur les informations contenues dans ces documents. "
                context += "Si les documents contiennent des informations contradictoires ou incomplètes, mentionnez-le clairement."
            
            logger.debug(f"Formatted context with {len(sources)} sources")
            
            return state.model_copy(update={
                "context": context,
                "sources": sources,
                "error": None
            })
            
        except Exception as e:
            logger.error(f"Error formatting context: {str(e)}")
            return state.model_copy(update={
                "context": "Erreur lors du formatage du contexte.",
                "sources": [],
                "error": f"Context formatting failed: {str(e)}"
            })
    
    def _generate_rag_response(self, state: GraphState) -> GraphState:
        """Generate response using RAG context."""
        try:
            logger.info("Generating RAG-based response")
            
            # Prepare system messages
            system_messages = [
                {"role": "system", "content": TURGOT_PROMPT},
                {"role": "system", "content": OUTPUT_PROMPT},
            ]
            
            # Convert history to dict format for token trimming
            history_dicts = self._convert_to_message_dicts(state.history_messages)
            
            # Add current user message to history for trimming calculation
            all_messages = history_dicts + [{"role": "user", "content": state.message}]
            
            # Trim messages to fit token limit
            trimmed_messages, total_tokens = self.message_trimmer.trim_messages(
                all_messages, 
                system_messages=system_messages, 
                context_text=state.context
            )
            
            # Convert back to LangChain format and reconstruct message list
            trimmed_langchain = self._convert_to_langchain_messages(
                trimmed_messages[:-1]  # Exclude current message
            )
            
            # Build final message list
            messages = [
                SystemMessage(content=TURGOT_PROMPT),
                SystemMessage(content=OUTPUT_PROMPT),
                *trimmed_langchain,  # Use trimmed history
                HumanMessage(content=state.message),
                HumanMessage(content=state.context),
            ]
            
            logger.info(f"RAG response: using {total_tokens} tokens ({len(trimmed_messages)} trimmed messages)")
            
            # Generate answer
            start_time = time.time()
            llm_response = self.llm.invoke(messages)
            end_time = time.time()
            
            logger.debug(f"Response generation took {end_time - start_time:.2f} seconds")
            
            answer = llm_response.content
            
            # Handle case where no documents were found
            if not state.documents:
                answer = (
                    "Note: Je n'ai pas trouvé d'informations spécifiques dans ma base de données "
                    "pour répondre à votre question. Je vais donc répondre en me basant sur mes "
                    "connaissances générales. Veuillez noter que cette réponse n'est pas "
                    "nécessairement spécifique au contexte français ou aux services publics français.\n\n"
                ) + answer
            
            return state.model_copy(update={
                "answer": answer,
                "trimmed_history": trimmed_langchain,
                "total_tokens": total_tokens,
                "error": None
            })
            
        except Exception as e:
            logger.error(f"Error generating RAG response: {str(e)}")
            fallback_answer = "Désolé, une erreur est survenue lors de la génération de la réponse."
            return state.model_copy(update={
                "answer": fallback_answer,
                "error": f"RAG response generation failed: {str(e)}"
            })
    
    def _format_response(self, state: GraphState) -> GraphState:
        """Format the final response with sources."""
        try:
            answer = state.answer
            sources = state.sources
            
            # Strip code blocks
            formatted_answer = self._strip_code_blocks(answer.strip())
            
            # Add sources if they exist and aren't already included
            if sources and len(sources) > 0:
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
                    sources_text += "\nNous vous recommandons de consulter les fiches complètes pour plus d'informations.\n"
                    sources_text += "La réponse est un résumé des informations contenues dans ces fiches, et ne doit pas être considérée comme exhaustive.\n"
                    for source in sources:
                        sources_text += f"- [{source}]({source})\n"
                    formatted_answer += sources_text
                else:
                    logger.info("Response already contains sources section, skipping duplicate")
            
            # If no sources found, add service-public.fr as fallback
            elif not state.documents:
                formatted_answer += "\n\n## Sources:\n- [https://www.service-public.fr](https://www.service-public.fr)\n"
            
            return state.model_copy(update={
                "formatted_response": formatted_answer,
                "error": None
            })
            
        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            return state.model_copy(update={
                "formatted_response": state.answer or "Erreur lors du formatage de la réponse.",
                "error": f"Response formatting failed: {str(e)}"
            })
    
    def _store_messages(self, state: GraphState) -> GraphState:
        """Store the conversation messages in Redis."""
        try:
            logger.debug("Storing messages in Redis")
            
            # Store user message
            self.redis_service.store_message(
                state.session_id, 
                {"role": "user", "content": state.message}
            )
            
            # Store assistant response
            response_to_store = state.formatted_response or state.answer or ""
            self.redis_service.store_message(
                state.session_id,
                {"role": "assistant", "content": response_to_store}
            )
            
            logger.debug("Messages stored successfully")
            
            return state.model_copy(update={
                "error": None
            })
            
        except Exception as e:
            logger.error(f"Error storing messages: {str(e)}")
            # Don't fail the entire flow if storage fails
            return state.model_copy(update={
                "error": f"Message storage failed: {str(e)}"
            })
    
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
    
    def _strip_code_blocks(self, text: str) -> str:
        """Remove Markdown code block formatting from a string."""
        # Remove triple backtick code blocks
        text = re.sub(r"```[a-zA-Z]*\n?", "", text)
        text = text.replace("```", "")
        # Remove single backtick inline code
        text = text.replace("`", "")
        return text.strip()
    
    def ask_turgot(self, message: str, session_id: str) -> str:
        """
        Main entry point for the agent. Maintains the same API as the original agent.
        
        Args:
            message: User's message
            session_id: Session identifier for conversation history
            
        Returns:
            Generated response string
        """
        try:
            logger.info(f"Processing request for session {session_id}: {message[:50]}...")
            
            # Initialize state
            initial_state = GraphState(
                message=message,
                session_id=session_id
            )
            
            # Execute the graph
            result = self.graph.invoke(initial_state)
            
            # Log any errors that occurred during processing
            if result.get("error"):
                logger.warning(f"Errors during processing: {result['error']}")
            
            # Return the formatted response
            response = result.get("formatted_response", result.get("answer", ""))
            
            if not response:
                logger.error("No response generated, using fallback")
                response = "Désolé, une erreur est survenue lors de la génération de la réponse."
            
            logger.info("Request processed successfully")
            return response
            
        except Exception as e:
            logger.error(f"Critical error in ask_turgot: {str(e)}")
            logger.exception("Full traceback:")
            return "Désolé, une erreur critique est survenue lors de la génération de la réponse." 