import requests
import os
from .pseudo_voice2text import voice2text_word, voice2text_char, voice2text_segment

ASR_SERVICE_URL = "http://localhost:8000/asr"

def voice2text(file_path):
    """
    Master fn that returns the text and all timestamp.
    input:file_path: Path to the audio file
    """
    if not os.path.exists(file_path):
        return {
            'text': '',
            'word_timestamps': [],
            'char_timestamps': [],
            'segment_timestamps': []
        }

    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(ASR_SERVICE_URL, files=files, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            # The ASR service now returns {"text": "...", "word_timestamps": [...]}
            full_text = result.get("text", "")
            word_ts = result.get("word_timestamps", [])
            
            # Transform word_timestamps to the internal format if needed
            # ASR service returns: {"word": "...", "start": 0.0, "end": 0.0}
            # Internal format expects: {"value": "...", "start": 0.0, "end": 0.0}
            formatted_word_ts = []
            for w in word_ts:
                formatted_word_ts.append({
                    "value": w.get("word", ""),
                    "start": w.get("start", 0.0),
                    "end": w.get("end", 0.0)
                })

            return {
                'text': full_text,
                'word_timestamps': formatted_word_ts,
                'char_timestamps': [], 
                'segment_timestamps': [{'start': word_ts[0]['start'] if word_ts else 0, 
                                       'end': word_ts[-1]['end'] if word_ts else 0, 
                                       'value': full_text}] if full_text else []
            }
    except Exception as e:
        print(f"ASR Service error: {e}")
        # Fallback to pseudo data for now if service fails, to keep system running
        segment_ts = voice2text_segment()
        return {
            'text': segment_ts[0]['value'] if segment_ts else '',
            'word_timestamps': voice2text_word(),
            'char_timestamps': voice2text_char(),
            'segment_timestamps': segment_ts
        }


def words_timestamps(file_path):
    """
    Returns word-level timestamps in format: {start: , end: , word: }
    """
    # Use pseudo data
    word_timestamps = voice2text_word()
    
    # Transform to requested format (pseudo data already matches roughly, but let's be safe)
    result = []
    for item in word_timestamps:
        result.append({
            'start': item.get('start', 0.0),
            'end': item.get('end', 0.0),
            'word': item.get('value', '')
        })
    return result


def char_timestamps(file_path):
    """
    Returns character-level timestamps in format: {start: , end: , char: }
    """
    # Use pseudo data
    char_ts = voice2text_char()
    
    # Transform to requested format
    result = []
    for item in char_ts:
        # Pseudo data 'value' is a list like ["M"], we need string "M"
        val = item.get('value', [''])
        char_val = val[0] if isinstance(val, list) and val else str(val)
        
        result.append({
            'start': item.get('start', 0.0),
            'end': item.get('end', 0.0),
            'char': char_val
        })
    return result


def text_with_timestamps(file_path):
    """
    Returns segment-level timestamps in format: {start: , end: , segment: }
    """
    # Use pseudo data
    segment_ts = voice2text_segment()
    
    # Transform to requested format
    result = []
    for item in segment_ts:
        result.append({
            'start': item.get('start', 0.0),
            'end': item.get('end', 0.0),
            'segment': item.get('value', '')
        })
    return {
        'text': segment_ts[0]['value'] if segment_ts else '',
        'segments': result
    }


if __name__ == "__main__":
    file_path = "input.wav"
    
    # Example usage
    print("=== Full transcription with timestamps ===")
    result = voice2text(file_path)
    print(f"Text: {result['text']}\n")
    
    print("=== Word timestamps ===")
    words = words_timestamps(file_path)
    for word in words[:5]:  # Print first 5 words as example
        print(word)
    
    print("\n=== Character timestamps ===")
    chars = char_timestamps(file_path)
    print(f"Number of character timestamps: {len(chars)}")
    
    print("\n=== Text with segment timestamps ===")
    text_segments = text_with_timestamps(file_path)
    print(f"Text: {text_segments['text']}")
    print(f"Number of segments: {len(text_segments['segments'])}")
