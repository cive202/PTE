"""Configuration constants for accent-tolerant pronunciation scoring."""
from __future__ import annotations

# Maximum penalty for stress errors (as fraction of score)
# Stress errors are common in many accents and should be penalized lightly
STRESS_PENALTY_MAX = 0.3  # Max 30% penalty for stress errors

# Intelligibility floor - minimum score for intelligible speech
# Prevents unfair low scores for fluent non-native speakers
INTELLIGIBILITY_FLOOR = 0.55  # Minimum 55% for intelligible speech

# Duration to analyze for speaker baseline (in seconds)
# First 3-4 seconds used to learn speaker's natural speech patterns
SPEAKER_BASELINE_DURATION = 3.0  # seconds

# Minimum phoneme similarity to accept as accent-equivalent
PHONEME_SIMILARITY_THRESHOLD = 0.6  # 60% similarity minimum

# Speech rate bounds for intelligibility (phones per second)
MIN_SPEECH_RATE = 5.0  # Too slow indicates problems
MAX_SPEECH_RATE = 20.0  # Too fast indicates problems

# Vowel quality threshold (even if accent-shifted)
# Minimum similarity for vowels to be considered "maintained"
VOWEL_QUALITY_THRESHOLD = 0.6

# Pause duration threshold for intelligibility (seconds)
# Excessive pauses indicate disfluency
MAX_AVERAGE_PAUSE = 0.5  # seconds
