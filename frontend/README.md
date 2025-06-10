# Colbert Frontend

The web interface for Colbert, built with Next.js 14 and TypeScript.

## Overview

The frontend provides a responsive chat interface that allows users to:

- Ask questions about French public administration procedures
- Receive AI-powered responses with source citations
- Navigate through conversation history with session management
- Access the service on both desktop and mobile devices
- Interact through a modern, accessible interface

## Technical Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS with typography plugin
- **UI Components**:
  - Heroicons for icons
  - React Markdown for response rendering
  - Custom components for chat interface
- **Build Tools**:
  - ESLint for code linting
  - PostCSS for CSS processing
  - Sharp for image optimization
- **Deployment**: Docker containerization

## Project Structure

```
frontend/
├── src/
│   ├── app/              # Next.js app directory
│   ├── components/       # React components
│   └── lib/             # Utility functions
├── public/              # Static assets
├── Dockerfile           # Container configuration
├── package.json         # Dependencies and scripts
├── tailwind.config.js   # Tailwind CSS configuration
├── tsconfig.json        # TypeScript configuration
└── next.config.mjs      # Next.js configuration
```

## Setup

### Prerequisites

- Node.js 18+
- npm or yarn

The application will be available at http://localhost:3000

## Features

### Chat Interface

- **Real-time Messaging**: Instant responses from the AI assistant
- **Session Management**: Conversation context preserved across interactions
- **Markdown Support**: Rich text rendering for formatted responses
- **Source Citations**: Clickable links to official government sources
- **Responsive Design**: Optimized for desktop, tablet, and mobile

## Docker Deployment

### Build Container

```bash
docker build -t colbert-frontend .
```

### Run Container

```bash
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=https://api.colbertchat.fr \
  colbert-frontend
```

### Docker Compose

The frontend is configured to work with the full stack via docker-compose.yml:

```bash
# Start all services
docker-compose up --build

# Frontend only
docker-compose up frontend
```

## API Integration

The frontend communicates with the backend through:

### POST /chat

```typescript
interface ChatRequest {
  message: string;
  session_id: string;
}

interface ChatResponse {
  answer: string;
}
```

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0) license.
