"""
File Utilities for PTE Platform
Handles standardized file naming and path generation for audio files.
"""

import os
import datetime
import uuid
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus"

# Ensure corpus directory exists
os.makedirs(CORPUS_DIR, exist_ok=True)

# Feature name constants
FEATURE_READ_ALOUD = 'read_aloud'
FEATURE_REPEAT_SENTENCE = 'repeat_sentence'
FEATURE_DESCRIBE_IMAGE = 'describe_image'
FEATURE_RETELL_LECTURE = 'retell_lecture'
FEATURE_ANSWER_QUESTION = 'answer_question'
FEATURE_SUMMARIZE_DISCUSSION = 'summarize_discussion'
FEATURE_RESPOND_SITUATION = 'respond_situation'


def generate_audio_filename(feature_name: str, extension: str = 'wav') -> str:
    """
    Generate standardized filename for audio files.
    
    Args:
        feature_name: read_aloud, describe_image, etc.
        extension: File extension (default: wav)
    
    Returns:
        Filename in format: {feature}_{YYYYMMDD}_{HHMMSS}.{ext}
    
    Example:
        >>> generate_audio_filename('read_aloud')
        'read_aloud_20260131_143022.wav'
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{feature_name}_{timestamp}.{extension}"


def get_audio_filepath(feature_name: str, extension: str = 'wav') -> str:
    """
    Get full filepath for saving audio.
    
    Args:
        feature_name: read_aloud, describe_image, etc.
        extension: File extension (default: wav)
    
    Returns:
        Absolute path: /path/to/corpus/{feature}_{timestamp}.wav
    
    Example:
        >>> get_audio_filepath('read_aloud')
        '/home/user/PTE/corpus/read_aloud_20260131_143022.wav'
    """
    filename = generate_audio_filename(feature_name, extension)
    return str(CORPUS_DIR / filename)


def get_text_filepath(feature_name: str) -> str:
    """
    Get filepath for corresponding text file.
    
    Args:
        feature_name: read_aloud, describe_image, etc.
    
    Returns:
        Absolute path: /path/to/corpus/{feature}_{timestamp}.txt
    """
    filename = generate_audio_filename(feature_name, 'txt')
    return str(CORPUS_DIR / filename)


def get_temp_filepath(prefix: str = 'temp', extension: str = 'tmp') -> str:
    """
    Generate temporary file path with unique identifier.
    
    Args:
        prefix: Prefix for temp file (default: temp)
        extension: File extension (default: tmp)
    
    Returns:
        Absolute path: /path/to/corpus/{prefix}_{uuid}.{ext}
    
    Example:
        >>> get_temp_filepath('upload')
        '/home/user/PTE/corpus/upload_a3b4c5d6.tmp'
    """
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{prefix}_{unique_id}.{extension}"
    return str(CORPUS_DIR / filename)


def get_paired_paths(feature_name: str) -> tuple:
    """
    Get both audio and text file paths for a feature.
    
    Args:
        feature_name: read_aloud, describe_image, etc.
    
    Returns:
        Tuple of (audio_path, text_path)
    
    Example:
        >>> audio, text = get_paired_paths('read_aloud')
        >>> print(audio)
        '/home/user/PTE/corpus/read_aloud_20260131_143022.wav'
        >>> print(text)
        '/home/user/PTE/corpus/read_aloud_20260131_143022.txt'
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{feature_name}_{timestamp}"
    
    audio_path = str(CORPUS_DIR / f"{base_name}.wav")
    text_path = str(CORPUS_DIR / f"{base_name}.txt")
    
    return audio_path, text_path


if __name__ == "__main__":
    # Test the functions
    print("Testing file_utils.py...")
    print(f"Audio file: {generate_audio_filename('read_aloud')}")
    print(f"Text file: {generate_audio_filename('read_aloud', 'txt')}")
    print(f"Full path: {get_audio_filepath('describe_image')}")
    print(f"Temp file: {get_temp_filepath('upload')}")
    
    audio, text = get_paired_paths('read_aloud')
    print(f"Paired - Audio: {audio}")
    print(f"Paired - Text: {text}")
