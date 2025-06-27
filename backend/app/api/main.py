import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

from app.core.graph_agent import TurgotGraphAgent
from app.services.pdf import PDFService

# Configure logging
logger.remove()  # Remove default handler
logger.add(
    "logs/turgot_backend.log",
    rotation="10 MB",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    backtrace=True,
    diagnose=True
)
# Also add console output for development/debugging
logger.add(
    lambda msg: print(msg, end=""),
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
)

# Models
class QuestionRequest(BaseModel):
    message: str
    session_id: str


class QuestionResponse(BaseModel):
    answer: str
    session_id: str


class PDFRequest(BaseModel):
    text: str
    title: Optional[str] = None


class PDFResponse(BaseModel):
    pdf_url: str


class ClearSessionRequest(BaseModel):
    session_id: str


class ClearSessionResponse(BaseModel):
    success: bool
    message: str


class LastUpdateResponse(BaseModel):
    last_update: str


# Global agent instance
agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global agent
    logger.info("Starting Turgot backend...")
    agent = TurgotGraphAgent()
    logger.info("Turgot agent initialized")
    yield
    # Shutdown
    logger.info("Shutting down Turgot backend...")


# Create FastAPI app
app = FastAPI(
    title="Turgot API",
    description="RAG-powered chatbot for French public administration information",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Turgot API is running"}


@app.post("/chat", response_model=QuestionResponse)
async def chat(request: QuestionRequest):
    """
    Process a chat message and return Turgot's response.

    Args:
        request: Contains the user message and session ID

    Returns:
        The response from Turgot including the answer and session ID
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        logger.info(f"Processing question from session {request.session_id}")
        start_time = time.time()

        # Get response from agent
        answer = agent.ask_turgot(request.message, request.session_id)

        end_time = time.time()
        logger.info(f"Question processed in {end_time - start_time:.2f} seconds")

        return QuestionResponse(answer=answer, session_id=request.session_id)

    except Exception as e:
        logger.error(f"Error processing question: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(
            status_code=500, detail="Erreur lors du traitement de votre question"
        )


@app.post("/generate-pdf", response_model=PDFResponse)
async def generate_pdf(request: PDFRequest, background_tasks: BackgroundTasks):
    """
    Generate a PDF from markdown text.

    Args:
        request: Contains the text content and optional title
        background_tasks: FastAPI background tasks

    Returns:
        URL to access the generated PDF
    """
    try:
        pdf_service = PDFService()

        # Generate PDF
        pdf_path = pdf_service.create_pdf_from_markdown(
            markdown_content=request.text, title=request.title or "Document Turgot"
        )

        # Schedule cleanup after 1 hour
        background_tasks.add_task(pdf_service.cleanup_file, pdf_path, delay=3600)

        # Return public URL
        pdf_filename = os.path.basename(pdf_path)
        pdf_url = f"/pdfs/{pdf_filename}"

        logger.info(f"Generated PDF: {pdf_filename}")

        return PDFResponse(pdf_url=pdf_url)

    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(
            status_code=500, detail="Erreur lors de la génération du PDF"
        )


@app.get("/pdfs/{filename}")
async def get_pdf(filename: str):
    """
    Serve generated PDF files.

    Args:
        filename: The PDF filename to serve

    Returns:
        The PDF file content
    """
    try:
        pdf_service = PDFService()
        return pdf_service.serve_pdf(filename)

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF not found")
    except Exception as e:
        logger.error(f"Error serving PDF: {str(e)}")
        raise HTTPException(status_code=500, detail="Error serving PDF")


@app.post("/clear-session", response_model=ClearSessionResponse)
async def clear_session(request: ClearSessionRequest):
    """
    Clear the chat history for a specific session.

    Args:
        request: Contains the session ID to clear

    Returns:
        Success status and message
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        logger.info(f"Clearing session history for session {request.session_id}")
        
        # Clear the session history using the Redis service
        agent.redis_service.clear_session_history(request.session_id)
        
        return ClearSessionResponse(
            success=True,
            message=f"Session {request.session_id} cleared successfully"
        )

    except Exception as e:
        logger.error(f"Error clearing session: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(
            status_code=500, detail="Erreur lors de la suppression de la session"
        )


@app.get("/last-update", response_model=LastUpdateResponse)
async def get_last_update():
    """
    Get the last update date of the database.

    Returns:
        The last update date from the database
    """
    try:
        # Read the last update file from the database directory
        from pathlib import Path

        # Get the database path (same logic as in retrieval service)
        if os.path.exists("/.dockerenv"):  # Docker environment
            last_update_path = Path("/app/database/last_update.txt")
        else:  # Local development
            workspace_root = Path(__file__).parent.parent.parent.parent
            last_update_path = workspace_root / "database" / "last_update.txt"
        
        if last_update_path.exists():
            with open(last_update_path, 'r', encoding='utf-8') as f:
                last_update = f.read().strip()
        else:
            logger.warning(f"Last update file not found at {last_update_path}")
            last_update = "Date non disponible"
        
        return LastUpdateResponse(last_update=last_update)

    except Exception as e:
        logger.error(f"Error reading last update: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(
            status_code=500, detail="Erreur lors de la lecture de la date de mise à jour"
        )


if __name__ == "__main__":
    # Configure logging
    logger.info("Starting Turgot API server...")

    # Run the server
    uvicorn.run(
        "app.api.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
