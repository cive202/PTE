"""Pause detection rules and thresholds for PTE Read Aloud scoring."""
from __future__ import annotations

# Re-export PAUSE_PUNCTUATION from alignment.normalizer for convenience
from ..alignment.normalizer import PAUSE_PUNCTUATION

# Base pause thresholds in seconds: (min_pause, max_pause)
# These will be scaled based on speech rate
BASE_PAUSE_THRESHOLDS = {
    ",": (0.3, 0.5),   # Comma: 0.3s to 0.5s
    ".": (0.6, 1.0),   # Period: 0.6s to 1.0s
}

# For backward compatibility
PAUSE_THRESHOLDS = BASE_PAUSE_THRESHOLDS

# Penalty weights for missed pauses (PTE: commas less important)
# Comma missed pause is often neutral, especially for fast speakers
MISSED_PAUSE_PENALTIES = {
    ",": 0.05,  # Comma missed pause: very low penalty (reduced from 0.1)
    ".": 0.3,   # Period missed pause: medium penalty
}

# Maximum pause duration before full penalty (1.0)
MAX_PAUSE_DURATION = 1.5  # seconds

# Base inter-word gap for speech rate calculation (typical: 0.25s)
BASE_INTER_WORD_GAP = 0.25  # seconds

# Function words that don't require strong pauses after them
FUNCTION_WORDS = {"a", "an", "the", "of", "to", "in", "on", "at", "for", "with", "by", "from", "as", "is", "was", "are", "were"}

# Soft floor for short pause penalty (ignore deviations < 30% of min_pause)
SHORT_PAUSE_SOFT_FLOOR = 0.3  # Ignore small deviations

# Window for hesitation clustering (consecutive pauses within this time are amplified)
HESITATION_CLUSTER_WINDOW = 2.0  # seconds

# Maximum total punctuation penalty contribution to fluency score
MAX_PUNCTUATION_PENALTY = 0.3  # Cap total contribution
