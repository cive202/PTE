"""ASR (Automatic Speech Recognition) integration and utilities."""
from .lazy_loader import get_words_timestamps, get_char_timestamps, get_segment_timestamps

__all__ = ["get_words_timestamps", "get_char_timestamps", "get_segment_timestamps"]
