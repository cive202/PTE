import warnings
import os
import requests
from typing import List

# Configuration for the external Docker service
GRAMMAR_SERVICE_URL = os.getenv("PTE_GRAMMAR_SERVICE_URL", "http://localhost:8000/grammar")

def check_grammar(text: str) -> List[str]:
    """
    Check the text for grammar issues using the external Dockerized LanguageTool service.
    
    Args:
        text: The text to check.
        
    Returns:
        A list of error messages.
    """
    if not text or not text.strip():
        return []

    try:
        response = requests.post(GRAMMAR_SERVICE_URL, json={"text": text})
        
        if response.status_code == 200:
            data = response.json()
            return data.get("matches", [])
        else:
            warnings.warn(f"Grammar Service returned error: {response.status_code} - {response.text}")
            return []
            
    except requests.exceptions.ConnectionError:
        warnings.warn("Could not connect to Grammar Service (is the Docker container running?). Skipping grammar check.")
        return []
    except Exception as e:
        warnings.warn(f"Grammar check failed: {str(e)}")
        return []
