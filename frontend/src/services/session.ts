import { v4 as uuidv4 } from 'uuid';

const SESSION_ID_KEY = 'colbert_session_id';
const SESSION_TIMEOUT = 60 * 60 * 1000; // 30 minutes in milliseconds
const LAST_ACTIVITY_KEY = 'colbert_last_activity';
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const createSession = async (): Promise<string> => {
    try {
        const response = await fetch(`${API_BASE_URL}/session/new`, {
            method: 'POST',
        });
        const data = await response.json();
        localStorage.setItem(SESSION_ID_KEY, data.session_id);
        localStorage.setItem(LAST_ACTIVITY_KEY, Date.now().toString());
        return data.session_id;
    } catch (error) {
        console.error('Error creating session:', error);
        throw error;
    }
};

export const getSessionId = (): string => {
    let sessionId = localStorage.getItem(SESSION_ID_KEY);
    const lastActivity = localStorage.getItem(LAST_ACTIVITY_KEY);
    
    // Check if session exists and is not expired
    if (sessionId && lastActivity) {
        const timeSinceLastActivity = Date.now() - parseInt(lastActivity);
        if (timeSinceLastActivity > SESSION_TIMEOUT) {
            // Session expired, create new one
            clearSession();
            sessionId = null;
        } else {
            // Update last activity
            localStorage.setItem(LAST_ACTIVITY_KEY, Date.now().toString());
        }
    }
    
    if (!sessionId) {
        sessionId = uuidv4();
        localStorage.setItem(SESSION_ID_KEY, sessionId);
        localStorage.setItem(LAST_ACTIVITY_KEY, Date.now().toString());
    }
    
    return sessionId;
};

export const endSession = async (sessionId: string): Promise<void> => {
    try {
        await fetch(`${API_BASE_URL}/session/${sessionId}`, {
            method: 'DELETE',
        });
        localStorage.removeItem(SESSION_ID_KEY);
        localStorage.removeItem(LAST_ACTIVITY_KEY);
    } catch (error) {
        console.error('Error ending session:', error);
        throw error;
    }
};

export const clearSession = (): void => {
    localStorage.removeItem(SESSION_ID_KEY);
    localStorage.removeItem(LAST_ACTIVITY_KEY);
}; 