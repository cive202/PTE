"""Pause detection rules and thresholds for PTE Read Aloud scoring."""
from __future__ import annotations

# Re-export PAUSE_PUNCTUATION from alignment.normalizer for convenience
from read_aloud.alignment.normalizer import PAUSE_PUNCTUATION

# Base pause thresholds in seconds: (min_pause, max_pause)
# Pearson does not publish exact millisecond targets, so these are product
# heuristics based on punctuation hierarchy in read speech:
# comma < semicolon/colon < sentence-final punctuation.
BASE_PAUSE_THRESHOLDS = {
    ",": (0.25, 0.50),
    ";": (0.35, 0.65),
    ":": (0.35, 0.65),
    ".": (0.60, 1.00),
    "!": (0.60, 1.00),
    "?": (0.60, 1.00),
}

# For backward compatibility
PAUSE_THRESHOLDS = BASE_PAUSE_THRESHOLDS

# Penalty weights for missed pauses (PTE: commas less important)
# Comma missed pause is often neutral, especially for fast speakers
MISSED_PAUSE_PENALTIES = {
    ",": 0.05,
    ";": 0.18,
    ":": 0.18,
    ".": 0.3,
    "!": 0.3,
    "?": 0.3,
}

# Maximum pause duration before full penalty (1.0)
MAX_PAUSE_DURATION = 1.5  # seconds

# Base inter-word gap for speech rate calculation (typical: 0.25s)
BASE_INTER_WORD_GAP = 0.25  # seconds

# Typical within-phrase word boundary gap range in fluent read speech.
BASE_INTER_WORD_GAP_RANGE = (0.08, 0.25)

# Function words that don't require strong pauses after them
FUNCTION_WORDS = {"a", "an", "the", "of", "to", "in", "on", "at", "for", "with", "by", "from", "as", "is", "was", "are", "were"}

# Soft floor for short pause penalty (ignore deviations < 30% of min_pause)
SHORT_PAUSE_SOFT_FLOOR = 0.3  # Ignore small deviations

# Window for hesitation clustering (consecutive pauses within this time are amplified)
HESITATION_CLUSTER_WINDOW = 2.0  # seconds

# Maximum total punctuation penalty contribution to fluency score
MAX_PUNCTUATION_PENALTY = 0.3  # Cap total contribution

# Boundary realization heuristic threshold used when silent pause is weak but
# phrase-final lengthening suggests the speaker still marked a boundary.
BOUNDARY_REALIZATION_THRESHOLD = 0.6
