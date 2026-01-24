"""Repeat Sentence assessment module for PTE.

Reuses the same pronunciation assessment pipeline as read_aloud,
but optimized for single-sentence repetition tasks.
"""

from .pte_pipeline import assess_repeat_sentence, assess_repeat_sentence_simple

__all__ = ["assess_repeat_sentence", "assess_repeat_sentence_simple"]
