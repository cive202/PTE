import warnings
import requests
import os
from typing import Optional

# Configuration for the external Docker service
ASR_SERVICE_URL = os.getenv("PTE_ASR_SERVICE_URL", "http://localhost:8000/asr")

def transcribe_audio(wav_path: str, model_size: str = "medium") -> str:
    """
    Transcribe audio using the external Dockerized Whisper service.
    
    Args:
        wav_path: Path to the audio file.
        model_size: Size of the Whisper model (ignored here as the service is pre-configured).
        
    Returns:
        The transcribed text.
    """
    if not os.path.exists(wav_path):
        warnings.warn(f"Audio file not found: {wav_path}")
        return ""

    try:
        with open(wav_path, 'rb') as f:
            # Send file to API
            response = requests.post(ASR_SERVICE_URL, files={"file": f})
        
        if response.status_code == 200:
            data = response.json()
            return data.get("text", "")
        else:
            warnings.warn(f"ASR Service returned error: {response.status_code} - {response.text}")
            return ""
            
    except requests.exceptions.ConnectionError:
        warnings.warn("Could not connect to ASR Service (is the Docker container running?). Returning empty transcript.")
        return ""
    except Exception as e:
        warnings.warn(f"ASR Request failed: {str(e)}")
        return ""
