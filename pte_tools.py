"""
PTE Tools - Shared Utilities for PTE Assessment Modules.

This module exposes core functionalities (ASR, MFA, Content Matching) 
to be reused across different PTE tasks (Read Aloud, Repeat Sentence, Describe Image, etc.).
"""
import sys
import os
from pathlib import Path

# --- Path Setup ---
# Define paths relative to this file (assumed to be in project root)
ROOT_DIR = Path(__file__).parent.absolute()
PTE_CORE_DIR = ROOT_DIR / "pte_core"
READ_ALOUD_DIR = ROOT_DIR / "read_aloud"

# 1. Add ROOT_DIR to path to allow fully qualified imports of pte_core
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 2. Add READ_ALOUD_DIR to path is NO LONGER NEEDED as we use qualified imports.
#    (e.g., 'from read_aloud.scorer...')


# --- Core Tools (from pte_core) ---

# ASR (Automatic Speech Recognition)
# We import from pte_core explicitly
from pte_core.asr.voice2text import (
    voice2text, 
    words_timestamps, 
    char_timestamps, 
    text_with_timestamps
)

# MFA (Pronunciation Assessment)
from pte_core.mfa.pronunciation import assess_pronunciation_mfa

# Audio Quality
from pte_core.audio_quality import is_audio_clear


# --- Shared Task Components (currently hosted in read_aloud) ---

# Content Alignment (Word Level Matcher)
from read_aloud.scorer.word_level_matcher import word_level_matcher

# Report Generator
from read_aloud.report_generator import generate_final_report

# WavLM Fallback (for noisy audio)
from read_aloud.wavlm_pronunciation import assess_pronunciation_wavlm

# CMUdict / Phonetics (if needed directly)
from pte_core.phonetics.cmudict import load_cmudict


__all__ = [
    "voice2text",
    "words_timestamps",
    "assess_pronunciation_mfa",
    "is_audio_clear",
    "word_level_matcher",
    "generate_final_report",
    "assess_pronunciation_wavlm",
    "load_cmudict"
]
