# Colbert Backend

The backend service for Colbert, a RAG-powered chatbot for French public administration information. Built with FastAPI and LangChain, it provides a robust API for handling chat interactions with AI-powered responses using ChromaDB vector search and Mistral AI.

## Overview

The backend service provides:

- **RESTful API**: FastAPI-based endpoints for chat interactions
- **RAG Architecture**: Retrieval-Augmented Generation with ChromaDB vector search
- **Session Management**: Redis-based conversation context storage
- **AI Integration**: Mistral AI for embeddings and response generation
- **Vector Search**: Semantic search across Service-Public.fr database
- **Logging System**: Structured logging with rotation and retention
- **Web Search**: Tavily integration for additional context when needed

## Technical Stack

- **Framework**: FastAPI with async support
- **AI/ML**:
  - LangChain/LangGraph for orchestration
  - Mistral AI for embeddings and generation
  - ChromaDB for vector storage and similarity search
- **Caching**: Redis for session management and conversation history
- **Logging**: Loguru with file rotation and structured output
- **Python Version**: 3.11+
- **Package Management**: UV for fast dependency resolution

## Project Structure

```
backend/
├── main.py                 # FastAPI application and API endpoints
├── colbert_agent.py        # Core RAG agent with LangGraph workflow
├── colbert_prompt.py       # Prompt templates and prompt management
├── search_tool.py          # Vector search tool implementation
├── redis_service.py        # Redis session management service
├── retrieval.py           # Document retrieval and processing
├── clear_redis_history.py  # Utility for clearing session data
├── chroma_db/             # Vector database storage (mounted from database/)
├── logs/                  # Application logs with rotation
├── Dockerfile             # Container configuration
├── pyproject.toml         # Project dependencies and configuration
└── uv.lock               # Locked dependency versions
```

## Setup

### Prerequisites

- Python 3.11+
- Redis server
- Access to Mistral AI API
- ChromaDB vector database (from database/ module)

### Local Development

1. **Create and activate virtual environment**:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. **Install dependencies** (using UV for faster installation):

```bash
# Install UV if not already installed
pip install uv

# Install project dependencies
uv pip install -e .
```

3. **Set up environment variables**:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Required
MISTRAL_API_KEY=your_mistral_api_key
REDIS_URL=redis://localhost:6379
TAVILY_API_KEY=your_tavily_api_key

# Optional
LOG_LEVEL=INFO
CHROMA_DB_PATH=database/chroma_db
```

4. **Start Redis server** (if not already running):

```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or using system package manager
sudo systemctl start redis
```

5. **Start the development server**:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:

- Main API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- ReDoc documentation: http://localhost:8000/redoc

## API Endpoints

### GET /

Health check endpoint.

**Response**:

```json
{
  "message": "Welcome to Colbert API"
}
```

### POST /chat

Main conversational endpoint for chat interactions.

**Request**:

```json
{
  "message": "Comment faire une demande de passeport ?",
  "session_id": "unique-session-identifier"
}
```

**Response**:

```json
{
  "answer": "Pour faire une demande de passeport, vous devez vous rendre en mairie ou dans un bureau de police municipale..."
}
```

**Features**:

- Context-aware responses using session history
- Vector similarity search in Service-Public.fr database
- Source citation integration
- Error handling with meaningful messages

## Architecture

### RAG Pipeline

1. **Query Processing**: User message is processed and prepared
2. **Vector Search**: Semantic search in ChromaDB for relevant documents
3. **Context Retrieval**: Most relevant documents are retrieved
4. **Prompt Construction**: Query + context + conversation history
5. **AI Generation**: Mistral AI generates contextual response
6. **Session Storage**: Conversation stored in Redis for context

## Environment Variables

```bash
MISTRAL_API_KEY=your_mistral_api_key     # Mistral AI API access
REDIS_URL=redis://localhost:6379         # Redis connection string
TAVILY_API_KEY=your_tavily_api_key       # Web search API (optional)
```

## Docker Deployment

### Build Container

```bash
docker build -t colbert-backend .
```

### Run Container

```bash
docker run -p 8000:8000 \
  -e MISTRAL_API_KEY=your_key \
  -e REDIS_URL=redis://redis:6379 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/database/chroma_db:/app/database/chroma_db \
  colbert-backend
```

### Docker Compose

The backend is configured in docker-compose.yml:

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0) license.
