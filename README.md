# Turgot

A RAG-powered chatbot for querying French public administration procedures, laws, and official guidelines from Service-Public.fr.
The app is available at [https://turgotchat.fr](https://turgotchat.fr/), with the main branch of the repo deployed.

## Overview

Turgot provides a conversational interface to access information from Service-Public.fr and other official French government sources. The system uses RAG (Retrieval-Augmented Generation) with ChromaDB vector search and Mistral AI to provide accurate, contextual responses with source citations.

## Features

- **Conversational Interface**: Natural language queries about French public administration
- **Sourced Responses**: All answers include citations from official government sources
- **Vector Search**: Fast semantic search across Service-Public.fr database
- **Session Management**: Context-aware conversations with Redis-based session storage
- **Real-time Processing**: Streaming responses for better user experience
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Docker Deployment**: Containerized architecture for easy deployment

## Project Structure

```
turgot/
├── backend/             # FastAPI service with RAG pipeline
│   ├── main.py         # FastAPI application and API endpoints
│   ├── turgot_agent.py # Core RAG agent with LangGraph
│   ├── search_tool.py  # Vector search implementation
│   ├── redis_service.py # Session management
│   └── chroma_db/      # Vector database storage
├── database/            # Data processing and vector store management
│   ├── chroma_db/      # ChromaDB vector database
│   ├── parse_xml_dump.py # XML data processing pipeline
│   └── download.py     # Data download utilities
├── frontend/            # Next.js web application
│   └── src/            # React components and pages
├── nginx/              # Nginx configuration for production
├── scripts/            # Deployment and utility scripts
│   ├── copy-to-server.sh # Server deployment script
│   ├── deploy.sh       # Production deployment
│   └── setup-server.sh # Server setup automation
└── docker-compose.yml  # Multi-service container orchestration
```

## Technical Stack

### Backend

- **Framework**: FastAPI with async support
- **AI/ML**: LangChain/LangGraph, Mistral AI
- **Vector Database**: ChromaDB with persistent storage
- **Caching**: Redis for session management
- **Logging**: Loguru with rotation and retention

### Frontend

- **Framework**: Next.js 14 with TypeScript
- **Styling**: Tailwind CSS with typography plugin
- **UI Components**: Heroicons, React Markdown
- **Build Tools**: ESLint, PostCSS, Sharp

### Data Processing

- **Source**: Service-Public.fr XML dumps
- **Processing**: Python XML parsing with TQDM progress
- **Embeddings**: Mistral AI embedding models
- **Storage**: ChromaDB vector store

### Infrastructure

- **Containerization**: Docker and Docker Compose
- **Web Server**: Nginx with SSL termination
- **Deployment**: Automated scripts for server deployment
- **Monitoring**: Structured logging and health checks

## Quick Start

### Local Development

1. **Clone the repository**:

```bash
git clone <repository-url>
cd turgot
```

2. **Set up environment variables**:

```bash
# Backend
cp backend/.env.example backend/.env
# Edit with your API keys (Mistral, Tavily, Redis URL)

# Frontend
cp frontend/.env.example frontend/.env.local
# Edit with your API URL
```

3. **Start with Docker Compose**:

```bash
docker-compose up --build
```

4. **Access the application**:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Production Deployment

1. **Prepare the server** (run once):

```bash
./scripts/setup-server.sh
```

2. **Deploy to server**:

```bash
./scripts/copy-to-server.sh
```

3. **On the server, run**:

```bash
cd ~/turgot && ./scripts/deploy.sh
```

## Environment Variables

### Backend (.env)

```bash
MISTRAL_API_KEY=your_mistral_api_key
TAVILY_API_KEY=your_tavily_api_key
REDIS_URL=redis://localhost:6379
```

### Frontend (.env.local)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Turgot
NEXT_PUBLIC_APP_DESCRIPTION=Assistant pour l'administration française
```

## Data Management

The system uses Service-Public.fr data:

1. **Download latest data**:

```bash
cd database && python download.py
```

2. **Process and index data**:

```bash
cd database && python parse_xml_dump.py
```

3. **The vector database** is automatically used by the backend service

## API Endpoints

### POST /chat

Main conversational endpoint.

**Request**:

```json
{
  "message": "Comment faire une demande de passeport ?",
  "session_id": "unique-session-id"
}
```

**Response**:

```json
{
  "answer": "Pour faire une demande de passeport, vous devez..."
}
```

## Development

Detailed setup instructions for each component:

- [Backend Development](backend/README.md)
- [Frontend Development](frontend/README.md)
- [Database Management](database/README.md)

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0) license.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

For major changes, please open an issue first to discuss what you would like to change.
