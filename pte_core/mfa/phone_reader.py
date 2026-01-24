"""Phone-level TextGrid and JSON parsing."""
from __future__ import annotations

import json
from typing import Any, Dict, List

try:
    import textgrid  # type: ignore
except ImportError:
    textgrid = None  # type: ignore


def read_phone_textgrid(path: str) -> List[Dict[str, Any]]:
    """Read phone-level TextGrid and return list of phone alignments.
    
    Args:
        path: Path to TextGrid file
        
    Returns:
        List of dicts: {label, start, end, duration}
        
    Raises:
        ImportError: If textgrid library is not installed
        RuntimeError: If TextGrid cannot be read
    """
    if textgrid is None:
        raise ImportError(
            "textgrid library required. Install with: pip install praat-textgrids"
        )

    try:
        tg = textgrid.TextGrid.fromFile(path)
    except Exception as e:
        raise RuntimeError(f"Failed to read TextGrid: {e}")

    phones: List[Dict[str, Any]] = []
    # Find phone tier (usually named "phones" or "phone")
    phone_tier = None
    for tier in tg.tiers:
        if tier.name.lower() in ("phones", "phone", "phonemes", "phoneme"):
            phone_tier = tier
            break

    # If no phone tier found, try second tier (often phones come after words)
    if phone_tier is None and len(tg.tiers) > 1:
        phone_tier = tg.tiers[1]

    if phone_tier is None:
        return phones

    for interval in phone_tier:
        if interval.mark.strip() and interval.mark.strip() not in ("", "sp", "sil"):
            start = float(interval.minTime)
            end = float(interval.maxTime)
            phones.append(
                {
                    "label": interval.mark.strip(),
                    "start": start,
                    "end": end,
                    "duration": end - start,
                }
            )

    return phones


def read_phone_json(path: str) -> List[Dict[str, Any]]:
    """Read phone-level JSON output from MFA.
    
    MFA can output JSON format with: --output_format json
    
    Args:
        path: Path to JSON file
        
    Returns:
        List of dicts: {label, start, end, duration}
        
    Raises:
        FileNotFoundError: If JSON file doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    phones: List[Dict[str, Any]] = []
    
    # MFA JSON structure: {"tiers": [{"name": "phones", "intervals": [...]}]}
    if isinstance(data, dict) and "tiers" in data:
        for tier in data["tiers"]:
            if tier.get("name", "").lower() in ("phones", "phone", "phonemes", "phoneme"):
                for interval in tier.get("intervals", []):
                    label = interval.get("mark", "").strip()
                    if label and label not in ("", "sp", "sil"):
                        start = float(interval.get("minTime", 0))
                        end = float(interval.get("maxTime", 0))
                        phones.append(
                            {
                                "label": label,
                                "start": start,
                                "end": end,
                                "duration": end - start,
                            }
                        )
                break
    
    return phones
