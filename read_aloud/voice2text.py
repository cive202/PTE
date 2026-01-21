import nemo.collections.asr as nemo_asr

asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name="nvidia/parakeet-tdt-0.6b-v2")


def voice2text(file_path):
    """
    Master fn that returns the text and all timestamp.
    input:file_path: Path to the audio file
    """
    output = asr_model.transcribe([file_path], timestamps=True)
    # by default, timestamps are enabled for char, word and segment level
    word_timestamps = output[0].timestamp['word']  # word level timestamps for first sample
    segment_timestamps = output[0].timestamp['segment']  # segment level timestamps
    char_timestamps = output[0].timestamp['char']  # char level timestamps
    
    # Get the full transcribed text
    full_text = output[0].text if hasattr(output[0], 'text') else ' '.join([seg['segment'] for seg in segment_timestamps])
    
    return {
        'text': full_text,
        'word_timestamps': word_timestamps,
        'char_timestamps': char_timestamps,
        'segment_timestamps': segment_timestamps
    }


def words_timestamps(file_path):
    """
    Returns word-level timestamps in format: {start: , end: , word: }
    """
    output = asr_model.transcribe([file_path], timestamps=True)
    word_timestamps = output[0].timestamp['word']
    
    # Transform to requested format
    result = []
    for item in word_timestamps:
        result.append({
            'start': item.get('start', item.get('start_time', 0.0)),
            'end': item.get('end', item.get('end_time', 0.0)),
            'word': item.get('word', item.get('text', ''))
        })
    return result


def char_timestamps(file_path):
    """
    Returns character-level timestamps in format: {start: , end: , char: }
    """
    output = asr_model.transcribe([file_path], timestamps=True)
    char_timestamps = output[0].timestamp['char']
    
    # Transform to requested format
    result = []
    for item in char_timestamps:
        result.append({
            'start': item.get('start', item.get('start_time', 0.0)),
            'end': item.get('end', item.get('end_time', 0.0)),
            'char': item.get('char', item.get('text', item.get('character', '')))
        })
    return result


def text_with_timestamps(file_path):
    """
    Returns segment-level timestamps in format: {start: , end: , segment: }
    """
    output = asr_model.transcribe([file_path], timestamps=True)
    segment_timestamps = output[0].timestamp['segment']
    
    # Transform to requested format
    result = []
    for item in segment_timestamps:
        result.append({
            'start': item.get('start', item.get('start_time', 0.0)),
            'end': item.get('end', item.get('end_time', 0.0)),
            'segment': item.get('segment', item.get('text', ''))
        })
    return result


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
