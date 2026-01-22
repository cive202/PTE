"""Pause detection and evaluation for punctuation marks."""
from .pause_evaluator import evaluate_pause
from .speech_rate import calculate_speech_rate_scale
from .hesitation import apply_hesitation_clustering, aggregate_pause_penalty
from .rules import (
    PAUSE_THRESHOLDS,
    BASE_PAUSE_THRESHOLDS,
    MISSED_PAUSE_PENALTIES,
    MAX_PAUSE_DURATION,
    PAUSE_PUNCTUATION,
    FUNCTION_WORDS,
    SHORT_PAUSE_SOFT_FLOOR,
    HESITATION_CLUSTER_WINDOW,
    MAX_PUNCTUATION_PENALTY,
)

__all__ = [
    "evaluate_pause",
    "calculate_speech_rate_scale",
    "apply_hesitation_clustering",
    "aggregate_pause_penalty",
    "PAUSE_THRESHOLDS",
    "BASE_PAUSE_THRESHOLDS",
    "MISSED_PAUSE_PENALTIES",
    "MAX_PAUSE_DURATION",
    "PAUSE_PUNCTUATION",
    "FUNCTION_WORDS",
    "SHORT_PAUSE_SOFT_FLOOR",
    "HESITATION_CLUSTER_WINDOW",
    "MAX_PUNCTUATION_PENALTY",
]
