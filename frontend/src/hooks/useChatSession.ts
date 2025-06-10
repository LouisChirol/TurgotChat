import { useState, useEffect } from 'react';
import { createSession, getSessionId, endSession } from '../services/session';

export const useChatSession = () => {
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<Error | null>(null);

    useEffect(() => {
        const initializeSession = async () => {
            try {
                setIsLoading(true);
                const existingSessionId = getSessionId();
                
                if (!existingSessionId) {
                    const newSessionId = await createSession();
                    setSessionId(newSessionId);
                } else {
                    setSessionId(existingSessionId);
                }
            } catch (err) {
                setError(err as Error);
            } finally {
                setIsLoading(false);
            }
        };

        initializeSession();

        return () => {
            if (sessionId) {
                endSession(sessionId).catch(console.error);
            }
        };
    }, []);

    const clearSession = async () => {
        if (sessionId) {
            try {
                await endSession(sessionId);
                setSessionId(null);
            } catch (err) {
                setError(err as Error);
            }
        }
    };

    return {
        sessionId,
        isLoading,
        error,
        clearSession,
    };
}; 