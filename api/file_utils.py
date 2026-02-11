"""
File Utilities for PTE Platform.
Handles standardized file naming and path generation for user-uploaded audio files.
"""

import os
import datetime
import uuid
import re
from pathlib import Path

from src.shared.paths import USER_UPLOADS_DIR, ensure_runtime_dirs

# Runtime paths
CORPUS_DIR = Path(USER_UPLOADS_DIR)

# Ensure runtime upload directory exists
ensure_runtime_dirs()

# Feature name constants
FEATURE_READ_ALOUD = 'read_aloud'
FEATURE_REPEAT_SENTENCE = 'repeat_sentence'
FEATURE_DESCRIBE_IMAGE = 'describe_image'
FEATURE_RETELL_LECTURE = 'retell_lecture'
FEATURE_ANSWER_QUESTION = 'answer_question'
FEATURE_SUMMARIZE_DISCUSSION = 'summarize_discussion'
FEATURE_RESPOND_SITUATION = 'respond_situation'


def _normalize_feature_name(feature_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]+", "_", feature_name.lower()).strip("_")
    return normalized or "attempt"


def _generate_attempt_name(feature_name: str) -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short_id = str(uuid.uuid4())[:6]
    feature_slug = _normalize_feature_name(feature_name)
    return f"{feature_slug}_{timestamp}_{short_id}"


def _create_attempt_dir(feature_name: str) -> tuple:
    attempt_name = _generate_attempt_name(feature_name)
    attempt_dir = CORPUS_DIR / attempt_name
    attempt_dir.mkdir(parents=True, exist_ok=True)
    return attempt_name, attempt_dir


def generate_audio_filename(feature_name: str, extension: str = 'wav') -> str:
    """
    Generate standardized filename for audio files.
    
    Args:
        feature_name: read_aloud, describe_image, etc.
        extension: File extension (default: wav)
    
    Returns:
        Filename in format: {feature}_{YYYYMMDD}_{HHMMSS}_{id}.{ext}
    
    Example:
        >>> generate_audio_filename('read_aloud')
        'read_aloud_20260131_143022_a1b2c3.wav'
    """
    attempt_name = _generate_attempt_name(feature_name)
    return f"{attempt_name}.{extension}"


def get_audio_filepath(feature_name: str, extension: str = 'wav') -> str:
    """
    Get full filepath for saving audio.
    
    Args:
        feature_name: read_aloud, describe_image, etc.
        extension: File extension (default: wav)
    
    Returns:
        Absolute path: /path/to/data/user_uploads/{attempt}/{attempt}.wav
    
    Example:
        >>> get_audio_filepath('read_aloud')
        '/home/user/PTE/data/user_uploads/read_aloud_20260131_143022_a1b2c3/read_aloud_20260131_143022_a1b2c3.wav'
    """
    attempt_name, attempt_dir = _create_attempt_dir(feature_name)
    return str(attempt_dir / f"{attempt_name}.{extension}")


def get_text_filepath(feature_name: str) -> str:
    """
    Get filepath for corresponding text file.
    
    Args:
        feature_name: read_aloud, describe_image, etc.
    
    Returns:
        Absolute path: /path/to/data/user_uploads/{attempt}/{attempt}.txt
    """
    attempt_name, attempt_dir = _create_attempt_dir(feature_name)
    return str(attempt_dir / f"{attempt_name}.txt")


def get_temp_filepath(prefix: str = 'temp', extension: str = 'tmp', directory: str = None) -> str:
    """
    Generate temporary file path with unique identifier.
    
    Args:
        prefix: Prefix for temp file (default: temp)
        extension: File extension (default: tmp)
    
    Returns:
        Absolute path: /path/to/data/user_uploads/{attempt}/{prefix}_{uuid}.{ext}
    
    Example:
        >>> get_temp_filepath('upload')
        '/home/user/PTE/data/user_uploads/upload_a3b4c5d6.tmp'
    """
    parent_dir = Path(directory) if directory else CORPUS_DIR
    parent_dir.mkdir(parents=True, exist_ok=True)
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{prefix}_{unique_id}.{extension}"
    return str(parent_dir / filename)


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
        '/home/user/PTE/data/user_uploads/read_aloud_20260131_143022_a1b2c3/read_aloud_20260131_143022_a1b2c3.wav'
        >>> print(text)
        '/home/user/PTE/data/user_uploads/read_aloud_20260131_143022_a1b2c3/read_aloud_20260131_143022_a1b2c3.txt'
    """
    attempt_name, attempt_dir = _create_attempt_dir(feature_name)

    audio_path = str(attempt_dir / f"{attempt_name}.wav")
    text_path = str(attempt_dir / f"{attempt_name}.txt")
    
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
