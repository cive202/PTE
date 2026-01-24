"""MFA (Montreal Forced Aligner) package for pronunciation assessment.

This package provides phone-level pronunciation analysis using MFA forced alignment.
MFA is a forced aligner (not a recognizer) - it provides precise timestamps and
phone-level alignment, but cannot detect missed words or judge correctness.
"""

from .pronunciation import assess_pronunciation_mfa
from .aligner import align_with_mfa

__all__ = ["assess_pronunciation_mfa", "align_with_mfa"]
