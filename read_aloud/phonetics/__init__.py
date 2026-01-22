"""Phonetics package for pronunciation dictionaries and phone mapping."""
from .cmudict import (
    ensure_cmudict_available,
    get_word_phonemes,
    get_word_pronunciation,
    load_cmudict,
    text_to_phonemes,
)
from .phone_mapper import arpabet_to_mfa, convert_phone_sequence

__all__ = [
    "load_cmudict",
    "get_word_pronunciation",
    "get_word_phonemes",
    "text_to_phonemes",
    "ensure_cmudict_available",
    "arpabet_to_mfa",
    "convert_phone_sequence",
]
