import os
import uuid

from colbert_agent import ColbertAgent
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from visitor_metrics import track_message, track_session_end, track_session_start

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

# Initialize Prometheus metrics
Instrumentator().instrument(app).expose(app)

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


@app.get("/")
async def root():
    return {"message": "Welcome to Colbert API"}


@app.post("/session/new")
async def create_session():
    """Create a new session and start tracking it."""
    session_id = str(uuid.uuid4())
    track_session_start(session_id)
    return {"session_id": session_id}


@app.delete("/session/{session_id}")
async def end_session(session_id: str):
    """End a session and stop tracking it."""
    track_session_end(session_id)
    return {"status": "success"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        logger.info(f"Processing chat request for session: {request.session_id}")
        # Track the message and session
        track_message(request.session_id)
        
        colbert_agent = ColbertAgent()
        # Generate response using chat history for context
        answer = colbert_agent.ask_colbert(request.message, request.session_id)

        return ChatResponse(
            answer=answer,
        )
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
