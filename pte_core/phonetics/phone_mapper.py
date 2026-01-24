"""ARPAbet to MFA phone mapping utilities."""
from __future__ import annotations

from typing import List


# ARPAbet to MFA phone mapping table
# Most phones are 1:1, but stress markers and some phones may differ
# This mapping is based on common MFA phone sets - verify with actual MFA output
ARPABET_TO_MFA: dict[str, str] = {
    # Vowels (with stress markers)
    "AA0": "AA", "AA1": "AA", "AA2": "AA",
    "AE0": "AE", "AE1": "AE", "AE2": "AE",
    "AH0": "AH", "AH1": "AH", "AH2": "AH",
    "AO0": "AO", "AO1": "AO", "AO2": "AO",
    "AW0": "AW", "AW1": "AW", "AW2": "AW",
    "AY0": "AY", "AY1": "AY", "AY2": "AY",
    "EH0": "EH", "EH1": "EH", "EH2": "EH",
    "ER0": "ER", "ER1": "ER", "ER2": "ER",
    "EY0": "EY", "EY1": "EY", "EY2": "EY",
    "IH0": "IH", "IH1": "IH", "IH2": "IH",
    "IY0": "IY", "IY1": "IY", "IY2": "IY",
    "OW0": "OW", "OW1": "OW", "OW2": "OW",
    "OY0": "OY", "OY1": "OY", "OY2": "OY",
    "UH0": "UH", "UH1": "UH", "UH2": "UH",
    "UW0": "UW", "UW1": "UW", "UW2": "UW",
    # Consonants (generally 1:1)
    "B": "B",
    "CH": "CH",
    "D": "D",
    "DH": "DH",
    "F": "F",
    "G": "G",
    "HH": "HH",
    "JH": "JH",
    "K": "K",
    "L": "L",
    "M": "M",
    "N": "N",
    "NG": "NG",
    "P": "P",
    "R": "R",
    "S": "S",
    "SH": "SH",
    "T": "T",
    "TH": "TH",
    "V": "V",
    "W": "W",
    "Y": "Y",
    "Z": "Z",
    "ZH": "ZH",
    # Special cases
    "AX": "AH",  # Schwa often maps to AH in MFA
    "AXR": "ER",  # R-colored schwa
}


def arpabet_to_mfa(arpabet_phone: str) -> str:
    """Convert ARPAbet phone symbol to MFA phone label.
    
    Handles stress markers by normalizing to base phone.
    Most phones are 1:1, but stress markers are stripped.
    
    Args:
        arpabet_phone: ARPAbet phone symbol (e.g., "AY1", "B", "AH0")
        
    Returns:
        MFA phone label (e.g., "AY", "B", "AH")
    """
    # Check direct mapping first
    if arpabet_phone in ARPABET_TO_MFA:
        return ARPABET_TO_MFA[arpabet_phone]
    
    # Try stripping stress marker (0, 1, 2)
    if len(arpabet_phone) > 2 and arpabet_phone[-1] in "012":
        base_phone = arpabet_phone[:-1]
        if base_phone in ARPABET_TO_MFA:
            return ARPABET_TO_MFA[base_phone]
        # If base phone not in mapping, return as-is (may be valid MFA phone)
        return base_phone
    
    # If no mapping found, return as-is (may already be MFA format)
    return arpabet_phone


def convert_phone_sequence(arpabet_phones: List[str]) -> List[str]:
    """Convert entire phone sequence from ARPAbet to MFA format.
    
    Args:
        arpabet_phones: List of ARPAbet phone symbols
        
    Returns:
        List of MFA phone labels
    """
    return [arpabet_to_mfa(phone) for phone in arpabet_phones]


def preserve_stress_marker(arpabet_phone: str) -> str:
    """Preserve stress marker for phones that need it.
    
    Some analysis may need to know which vowels are stressed.
    This function returns the phone with stress marker preserved.
    
    Args:
        arpabet_phone: ARPAbet phone with stress marker
        
    Returns:
        Phone label with stress marker (e.g., "AY1" stays "AY1")
    """
    return arpabet_phone
