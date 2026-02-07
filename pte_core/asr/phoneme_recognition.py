import requests
import json
import os

PHONEME_SERVICE_URL = os.environ.get("PHONEME_SERVICE_URL", "http://localhost:8001/phonemes")

def call_phoneme_service(wav_path, start=None, end=None):
    """
    Call the external CPU-only wav2vec2 service to get phonemes.
    """
    if start is not None and end is not None:
        if (end - start) < 0.08:
             return [] # Skip too short segments

    try:
        with open(wav_path, "rb") as f:
            data = {}
            if start is not None:
                data["start"] = start
            if end is not None:
                data["end"] = end
                
            r = requests.post(
                PHONEME_SERVICE_URL,
                files={"audio": f},
                data=data,
                timeout=10 # Short timeout for segments
            )
            r.raise_for_status()
            return r.json().get("phonemes", [])
    except Exception as e:
        print(f"Phoneme service call failed: {e}")
        return []
