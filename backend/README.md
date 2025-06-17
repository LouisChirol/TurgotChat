# Turgot Backend

A RAG-powered chatbot backend for French public administration information, built with FastAPI and powered by Mistral AI.

## 🏗️ Architecture

The backend follows a clean, modular architecture:

```
backend/
├── app/                    # Main application package
│   ├── api/               # FastAPI application and endpoints
│   ├── core/              # Core business logic (agent, prompts)
│   ├── services/          # External services (Redis, retrieval, PDF)
│   └── utils/             # Utility functions (tokens, search)
├── scripts/               # Development and maintenance scripts
├── logs/                  # Application logs
├── pyproject.toml         # Dependencies and project config
├── Dockerfile             # Container configuration
└── run.py                 # Development runner
```

## 🚀 Quick Start

### Development

1. **Install dependencies:**
   ```bash
   pip install uv
   uv pip install -e .
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. **Run the application:**
   ```bash
   python run.py
   ```

   The API will be available at `http://localhost:8000`

### Production (Docker)

```bash
docker build -t turgot-backend .
docker run -p 8000:8000 --env-file .env turgot-backend
```

## 📁 Package Structure

### `app/core/`
- **`agent.py`**: Main TurgotAgent class with RAG pipeline and token management
- **`prompts.py`**: System prompts for classification and response generation

### `app/services/`
- **`redis.py`**: Redis service for conversation history management
- **`retrieval.py`**: Vector database and document retrieval service
- **`pdf.py`**: PDF generation service for exporting conversations

### `app/utils/`
- **`tokens.py`**: Token counting and message trimming utilities
- **`search.py`**: Web search utilities for extended functionality

### `app/api/`
- **`main.py`**: FastAPI application with endpoints for chat and PDF generation

### `scripts/`
- **`clear_redis.py`**: Utility script for clearing Redis chat histories

## 🔧 Key Features

### Smart RAG Pipeline
- **Intelligent Classification**: Automatically determines when RAG is needed
- **Token Management**: Smart message trimming to stay within 32k context limits
- **Source Filtering**: Removes invalid sources and maintains proper ordering

### Advanced Token Handling
- **Accurate Counting**: Uses official Mistral tokenizer for precise token counts
- **Smart Trimming**: Preserves important context while respecting limits
- **Fallback Strategy**: Character-based estimation when tokenizer unavailable

### Conversation Management
- **Session Persistence**: Redis-based chat history storage
- **Context Preservation**: Maintains conversation flow across interactions
- **Memory Efficiency**: Automatic cleanup and trimming of old conversations

## 🌐 API Endpoints

### `POST /chat`
Process a chat message and return Turgot's response.

**Request:**
```json
{
  "message": "Comment faire une demande de passeport ?",
  "session_id": "user-session-123"
}
```

**Response:**
```json
{
  "answer": "Pour faire une demande de passeport...",
  "session_id": "user-session-123"
}
```

### `POST /generate-pdf`
Generate a PDF from markdown content.

**Request:**
```json
{
  "text": "# Mon Document\n\nContenu en markdown...",
  "title": "Document Turgot"
}
```

**Response:**
```json
{
  "pdf_url": "/pdfs/document-123.pdf"
}
```

### `GET /health`
Health check endpoint with detailed status.

## 🔧 Development

### Running Tests
```bash
# Run with pytest (when tests are added)
pytest
```

### Code Quality
```bash
# Format code
black app/ scripts/

# Lint code  
ruff check app/ scripts/

# Type checking
mypy app/
```

### Utilities

**Clear Redis histories:**
```bash
# Clear all sessions
python scripts/clear_redis.py --all

# Clear specific session
python scripts/clear_redis.py --session user-session-123
```

## 🌊 Environment Variables

Required environment variables:

```bash
MISTRAL_API_KEY=your_mistral_api_key
REDIS_URL=redis://localhost:6379/0
```

Optional configuration:

```bash
# Logging
LOG_LEVEL=INFO

# Token limits
MAX_TOKENS=32000
RESERVED_TOKENS=8000

# Model settings
MISTRAL_MODEL=mistral-medium-latest
EMBEDDING_MODEL=mistral-embed
```

## 🏗️ Dependencies

Core dependencies:
- **FastAPI**: Modern web framework for APIs
- **Mistral AI**: Language model and embeddings
- **LangChain**: RAG pipeline components
- **Redis**: Conversation storage
- **ChromaDB**: Vector database for document retrieval
- **Loguru**: Advanced logging

See `pyproject.toml` for the complete dependency list.

## 📈 Performance

- **Response Time**: Typically 2-5 seconds for RAG queries, <1s for simple responses
- **Token Efficiency**: Smart trimming reduces context size by up to 60%
- **Memory Usage**: Redis-based storage with automatic cleanup
- **Scalability**: Stateless design supports horizontal scaling

## 🔒 Security

- **API Key Management**: Secure environment variable handling
- **Input Validation**: Pydantic models for request/response validation
- **Rate Limiting**: Recommended for production deployment
- **CORS**: Configurable cross-origin resource sharing

## 📝 Logging

Structured logging with Loguru:
- **File Rotation**: Automatic log file management
- **Level Control**: Configurable log levels
- **Context Tracking**: Session and request correlation
- **Error Handling**: Comprehensive error tracking

## 🤝 Contributing

1. Follow the existing package structure
2. Add type hints to all functions
3. Update docstrings for new functionality
4. Ensure imports use the app package structure
5. Test your changes thoroughly

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
