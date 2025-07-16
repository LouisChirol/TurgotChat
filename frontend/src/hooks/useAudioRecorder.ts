import { useCallback, useRef, useState } from 'react';
import { transcribeAudio } from '../services/api';

interface UseAudioRecorderReturn {
  isRecording: boolean;
  isTranscribing: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<string | null>;
  error: string | null;
  clearError: () => void;
}

export const useAudioRecorder = (): UseAudioRecorderReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const startRecording = useCallback(async () => {
    try {
      clearError();
      
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        } 
      });

      // Create MediaRecorder with MP3 format
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus' // We'll convert to MP3 on the backend
      });

      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        // Stop all tracks to release microphone
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);

    } catch (err) {
      console.error('Error starting recording:', err);
      if (err instanceof Error) {
        if (err.name === 'NotAllowedError') {
          setError('Accès au microphone refusé. Veuillez autoriser l\'accès au microphone.');
        } else if (err.name === 'NotFoundError') {
          setError('Aucun microphone trouvé. Veuillez connecter un microphone.');
        } else {
          setError('Erreur lors de l\'accès au microphone: ' + err.message);
        }
      } else {
        setError('Erreur inattendue lors de l\'accès au microphone');
      }
    }
  }, [clearError]);

  const stopRecording = useCallback(async (): Promise<string | null> => {
    if (!mediaRecorderRef.current || !isRecording) {
      return null;
    }

    try {
      return new Promise((resolve) => {
        mediaRecorderRef.current!.onstop = async () => {
          setIsRecording(false);
          
          if (audioChunksRef.current.length === 0) {
            setError('Aucun audio enregistré');
            resolve(null);
            return;
          }

          try {
            setIsTranscribing(true);
            
            // Create audio blob
            const audioBlob = new Blob(audioChunksRef.current, { 
              type: 'audio/webm;codecs=opus' 
            });

            // Transcribe audio
            const transcribedText = await transcribeAudio(audioBlob);
            
            setIsTranscribing(false);
            resolve(transcribedText);

          } catch (err) {
            setIsTranscribing(false);
            console.error('Error transcribing audio:', err);
            if (err instanceof Error) {
              setError('Erreur lors de la transcription: ' + err.message);
            } else {
              setError('Erreur inattendue lors de la transcription');
            }
            resolve(null);
          }
        };

        mediaRecorderRef.current.stop();
      });

    } catch (err) {
      setIsRecording(false);
      console.error('Error stopping recording:', err);
      setError('Erreur lors de l\'arrêt de l\'enregistrement');
      return null;
    }
  }, [isRecording]);

  return {
    isRecording,
    isTranscribing,
    startRecording,
    stopRecording,
    error,
    clearError,
  };
}; 