from .pseudo_voice2text import voice2text_word, voice2text_char, voice2text_segment

def voice2text(file_path):
    """
    Master fn that returns the text and all timestamp.
    input:file_path: Path to the audio file
    """
    # Use pseudo data instead of real model
    word_ts = voice2text_word()
    char_ts = voice2text_char()
    segment_ts = voice2text_segment()
    
    # Get the full transcribed text
    full_text = segment_ts[0]['value'] if segment_ts else ''
    
    return {
        'text': full_text,
        'word_timestamps': word_ts,
        'char_timestamps': char_ts,
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
