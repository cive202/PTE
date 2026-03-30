import requests
from src.shared.services import PHONEME_SERVICE_URL

def call_phoneme_service_raw(wav_path, start=None, end=None):
    """
    Call the external CPU-only wav2vec2 service and return the raw JSON body.
    """
    if start is not None and end is not None:
        if (end - start) < 0.08:
            return {"phonemes": [], "_skipped": "segment_too_short"}

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
                timeout=10,
            )
            r.raise_for_status()
            payload = r.json()
            if isinstance(payload, dict):
                return payload
            return {"phonemes": [], "_error": "non_dict_json", "_raw": payload}
    except Exception as e:
        print(f"Phoneme service call failed: {e}")
        return {"phonemes": [], "_error": str(e)}

def call_phoneme_service(wav_path, start=None, end=None):
    """
    Call the external CPU-only wav2vec2 service to get phonemes.
    """
    payload = call_phoneme_service_raw(wav_path, start=start, end=end)
    phonemes = payload.get("phonemes", []) if isinstance(payload, dict) else []
    if isinstance(phonemes, list):
        return phonemes
    return []
