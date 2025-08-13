import { getSessionId } from './session';

interface ChatRequest {
  query: string;
  session_id: string;
}

interface Source {
  url: string;
  title: string;
  excerpt: string;
}

interface ChatResponse {
  answer: string;
  main_sources: Array<Source>;
  secondary_sources: Array<Source>;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || (typeof window !== 'undefined' && window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://api.turgotchat.fr');

export const sendMessage = async (message: string): Promise<ChatResponse> => {
  const sessionId = getSessionId();
  
  const response = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ 
      message,
      session_id: sessionId
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to get response from server');
  }

  return response.json();
};

export const clearSession = async (): Promise<void> => {
  const sessionId = getSessionId();
  
  const response = await fetch(`${API_URL}/clear-session`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ 
      session_id: sessionId
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to clear session history');
  }
};

export const getLastUpdate = async (): Promise<string> => {
  const response = await fetch(`${API_URL}/last-update`);
  if (!response.ok) {
    throw new Error('Failed to get last update date');
  }
  const data = await response.json();
  return data.last_update;
};

export const transcribeAudio = async (audioBlob: Blob): Promise<string> => {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'audio.mp3');
  
  const response = await fetch(`${API_URL}/transcribe`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to transcribe audio');
  }

  const data = await response.json();
  return data.text;
}; 