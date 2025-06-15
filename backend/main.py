import os
import tempfile
from pathlib import Path

from colbert_agent import ColbertAgent
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from loguru import logger
from pdf_service import create_chat_pdf
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Ensure logs directory exists
logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(logs_dir, exist_ok=True)

# Configure logger with absolute path
log_file = os.path.join(logs_dir, "colbert_backend.log")
logger.add(log_file, rotation="10 MB", retention="7 days", level="INFO")

app = FastAPI(
    title="Colbert Backend",
    description="RAG-powered chatbot for French public administration information",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ChatResponse(BaseModel):
    answer: str


class ExportPDFRequest(BaseModel):
    session_id: str


@app.get("/")
async def root():
    return {"message": "Welcome to Colbert API"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        logger.info(f"Processing chat request for session: {request.session_id}")
        colbert_agent = ColbertAgent()
        # Generate response using chat history for context
        answer = colbert_agent.ask_colbert(request.message, request.session_id)

        return ChatResponse(
            answer=answer,
        )
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/export-pdf")
async def export_pdf(request: ExportPDFRequest):
    """Export the chat history as a PDF file."""
    try:
        # Create the PDF file
        pdf_path = create_chat_pdf(request.session_id)
        
        # Return the file as a response
        response = FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"colbert_chat_{request.session_id}.pdf",
            background=None  # This ensures the file is deleted after sending
        )
        
        # Delete the file after sending
        response.background = lambda: os.unlink(pdf_path)
        
        return response
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error exporting PDF: {str(e)}")
        raise HTTPException(status_code=500, detail="Error exporting PDF file")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
    uvicorn.run(app, host="0.0.0.0", port=8000)
