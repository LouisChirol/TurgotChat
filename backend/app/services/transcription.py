"""
Transcription service using Mistral Voxtral API
"""

import json
import os
import subprocess
import tempfile

from fastapi import HTTPException
from loguru import logger


class TranscriptionService:
    """Service for transcribing audio using Mistral Voxtral API"""
    
    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY environment variable not set")
        
        self.model = "voxtral-mini-2507"
        self.endpoint = "https://api.mistral.ai/v1/audio/transcriptions"
    
    def transcribe_audio(self, audio_data: bytes, audio_format: str = "mp3") -> str:
        """
        Transcribe audio data using Voxtral API
        
        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format (mp3, wav, etc.)
            
        Returns:
            Transcribed text
            
        Raises:
            HTTPException: If transcription fails
        """
        try:
            # Create temporary file for audio data
            with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            try:
                # Call Voxtral API using curl
                curl_cmd = [
                    "curl", "-X", "POST", self.endpoint,
                    "-H", f"Authorization: Bearer {self.api_key}",
                    "-F", f"model={self.model}",
                    "-F", f"file=@{temp_file_path}",
                    "-F", "response_format=json"
                ]
                
                logger.info(f"Calling Voxtral API for transcription with model {self.model}")
                result = subprocess.run(curl_cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"Voxtral API call failed: {result.stderr}")
                    raise HTTPException(
                        status_code=500,
                        detail="Erreur lors de la transcription audio"
                    )
                
                # Parse response
                try:
                    response_json = json.loads(result.stdout)
                    transcribed_text = response_json.get("text", "")
                    
                    if not transcribed_text:
                        logger.warning("Voxtral API returned empty transcription")
                        raise HTTPException(
                            status_code=422,
                            detail="Impossible de transcrire l'audio. Veuillez réessayer."
                        )
                    
                    logger.info(f"Transcription successful: {len(transcribed_text)} characters")
                    return transcribed_text
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Voxtral API response: {e}")
                    logger.error(f"Raw response: {result.stdout}")
                    raise HTTPException(
                        status_code=500,
                        detail="Erreur lors du traitement de la réponse de transcription"
                    )
                    
            finally:
                # Always clean up temporary file for privacy
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    logger.debug(f"Cleaned up temporary audio file: {temp_file_path}")
                    
        except HTTPException:
            # Re-raise HTTPExceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error during transcription: {str(e)}")
            logger.exception("Full traceback:")
            raise HTTPException(
                status_code=500,
                detail="Erreur inattendue lors de la transcription"
            )
    
    def validate_audio_format(self, audio_format: str) -> bool:
        """Validate if the audio format is supported"""
        supported_formats = ["mp3", "wav", "m4a", "ogg", "flac"]
        return audio_format.lower() in supported_formats 