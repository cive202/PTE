
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
ROOT_DIR = Path(__file__).parent.absolute()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pte_core.mfa.textgrid_reader import read_word_textgrid
from pte_core.mfa.phone_reader import read_phone_textgrid
from pte_core.mfa.timing_metrics import (
    calculate_phone_rate,
    calculate_vowel_ratio,
    calculate_word_duration,
    detect_hesitation,
)
from pte_core.mfa.scorer import score_pronunciation_from_phones
from pte_core.mfa.phoneme_alignment import (
    align_phonemes_with_dp,
    calculate_intelligibility_score as dp_phone_intelligibility,
    consistency_bonus as dp_consistency_bonus,
    extract_errors_and_patterns,
    stress_accuracy as dp_stress_accuracy,
    base_phone,
)
from read_aloud.pte_pronunciation import (
    pronunciation_score_0_100,
    pte_pronunciation_band,
    generate_feedback_strings,
)
from pte_core.phonetics.cmudict import ensure_cmudict_available

def load_custom_dict(path: str, has_probs: bool = True) -> Dict[str, List[List[str]]]:
    """Load MFA dictionary.
    
    Args:
        path: Path to dictionary file
        has_probs: If True, skips 4 probability columns. If False, assumes plain CMUdict format.
    
    Returns:
        Dict mapping word -> list of pronunciations (each is a list of phones)
    """
    custom_dict = {}
    print(f"Loading custom dictionary from: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                # If has_probs, we need at least word + 4 probs + 1 phone = 6 parts
                # If no probs, we need at least word + 1 phone = 2 parts
                min_len = 6 if has_probs else 2
                
                if len(parts) >= min_len:
                    word = parts[0]
                    
                    if has_probs:
                        # Skip 4 probability columns (indices 1, 2, 3, 4)
                        # Phones start at index 5
                        phones = parts[5:]
                    else:
                        # Standard CMUdict: Word Phone1 Phone2 ...
                        phones = parts[1:]
                        
                    # Normalize to lowercase immediately
                    phones = [p.lower() for p in phones]
                    
                    if word not in custom_dict:
                        custom_dict[word] = []
                    custom_dict[word].append(phones)
        print(f"Loaded {len(custom_dict)} words.")
        return custom_dict
    except Exception as e:
        print(f"Error loading custom dictionary: {e}")
        return {}

def run_test_from_output():
    base_dir = Path(r"c:\Users\Acer\DataScience\PTE\PTE_MFA_TESTER_DOCKER")
    
    # Define Accents and their paths
    accents = {
        "Indian": {
            "textgrid": base_dir / "output_indian" / "Education.TextGrid",
            "dict": base_dir / "eng_indian_model" / "english_india_mfa.dict",
            "has_probs": True
        },
        "Nigerian": {
            "textgrid": base_dir / "output_nigeria" / "Education.TextGrid",
            "dict": base_dir / "eng_nigeria_model" / "english_nigeria_mfa.dict",
            "has_probs": True
        },
        "US_ARPA": {
            "textgrid": base_dir / "output_us" / "Education.TextGrid",
            "dict": base_dir / "eng_us_model" / "english_us_arpa.dict",
            "has_probs": False
        },
        "US_MFA": {
            "textgrid": base_dir / "output_us_mfa" / "Education.TextGrid",
            "dict": base_dir / "eng_us_model_2" / "english_us_mfa.dict",
            "has_probs": True
        },
        "UK": {
            "textgrid": base_dir / "output_uk" / "Education.TextGrid",
            "dict": base_dir / "english_uk_model" / "english_uk_mfa.dict",
            "has_probs": True
        }
        # NonNative Removed as per request
    }

    # Load all dictionaries
    loaded_dicts = {}
    for accent, paths in accents.items():
        if paths["dict"].exists():
            loaded_dicts[accent] = load_custom_dict(str(paths["dict"]), has_probs=paths.get("has_probs", True))
        else:
            print(f"Warning: Dictionary not found for {accent}")
            loaded_dicts[accent] = {}

    # Load all TextGrids
    loaded_textgrids = {}
    word_list = [] # To keep order
    
    for accent, paths in accents.items():
        if paths["textgrid"].exists():
            try:
                # Read words and phones for this accent
                mfa_words = read_word_textgrid(str(paths["textgrid"]))
                phones = read_phone_textgrid(str(paths["textgrid"]))
                
                # Group phones by word for this accent
                word_phones = {}
                
                # Robust O(N*M) extraction to guarantee no skips
                for word_idx, word_align in enumerate(mfa_words):
                    word_start = word_align.get("start")
                    word_end = word_align.get("end")
                    if word_start is None: continue
                    
                    # Capture word list from first successful load
                    if not word_list and accent == "Indian": 
                        word_list = [w.get("word") for w in mfa_words]
                    elif not word_list and accent == "US_ARPA": # Fallback
                        word_list = [w.get("word") for w in mfa_words]
                        
                    current_phones = []
                    # Check every phone (safe but slower, optimization not needed for small files)
                    for p in phones:
                        p_start = p.get("start", 0.0)
                        p_end = p.get("end", 0.0)
                        
                        # Use loose overlap check: phone mid-point inside word, or substantial overlap
                        # MFA phones are strictly contained within word boundaries usually
                        # Use epsilon for float comparison
                        epsilon = 0.001
                        if p_start >= word_start - epsilon and p_end <= word_end + epsilon:
                             if p.get("label", "").strip().upper() not in ("SP", "SIL", ""):
                                 current_phones.append(base_phone(p.get("label", "")).lower())
                    
                    word_phones[word_align.get("word")] = current_phones
                
                loaded_textgrids[accent] = word_phones
            except Exception as e:
                print(f"Error reading TextGrid for {accent}: {e}")

    # Cross-Validate
    json_report = []
    print("\nRunning Multi-Accent Validation...")
    
    # Use word list from Indian alignment as base (or any available)
    # If list is empty, try to get unique words from all grids
    if not word_list:
        all_words = set()
        for grid in loaded_textgrids.values():
            all_words.update(grid.keys())
        word_list = sorted(list(all_words))

    
    # Custom Normalization for Non-Native Artifacts and US ARPABET mapping
    def clean_phone(p_label):
        p = base_phone(p_label).lower()
        # Remove backslash artifacts from NonNative model (e.g., \sw -> sw, \:f -> f)
        if p.startswith("\\"):
            p = p.replace("\\", "")
            # Handle specific weird artifacts if needed, e.g. :f -> f
            if ":" in p: p = p.split(":")[1]
            if "." in p: p = p.replace(".", "")
        return p

    # Custom mapping for US ARPABET -> IPA (Simplified for this specific text)
    # This ensures "eh" == "ɛ", "sh" == "ʃ", etc.
    arpa_to_ipa = {
        "aa": "ɑ", "ae": "æ", "ah": "ə", "ao": "ɔ", "aw": "aʊ", "ay": "aɪ",
        "eh": "ɛ", "er": "ɝ", "ey": "eɪ", "ih": "ɪ", "iy": "i", "ow": "oʊ",
        "oy": "ɔɪ", "uh": "ʊ", "uw": "u",
        "ch": "tʃ", "dh": "ð", "dx": "ɾ", "jh": "dʒ", "ng": "ŋ", 
        "sh": "ʃ", "th": "θ", "zh": "ʒ", "y": "j", "hh": "h"
    }
    
    def normalize_us_phone(p):
        # Strip digits first: eh1 -> eh
        base = "".join([c for c in p if not c.isdigit()])
        # Map to IPA if possible, else return as is
        return arpa_to_ipa.get(base, base)

    
    for word in word_list:
        if not word: continue
        
        matches = []
        accent_details = {}
        
        # Check against ALL accents
        for accent, textgrid_phones in loaded_textgrids.items():
            # Get Spoken Phones & Clean them
            raw_spoken = textgrid_phones.get(word, [])
            spoken = [clean_phone(p) for p in raw_spoken]
            
            # Get Expected Phones & Clean them
            dictionary = loaded_dicts.get(accent, {})
            raw_expected_list = dictionary.get(word, [])
            
            expected_list = []
            for raw_exp in raw_expected_list:
                cleaned_exp = []
                for p in raw_exp:
                    cp = clean_phone(p)
                    # Apply ARPABET->IPA mapping ONLY for US model
                    if accent == "US_ARPA":
                        cp = normalize_us_phone(cp)
                    cleaned_exp.append(cp)
                expected_list.append(cleaned_exp)
            
            # Special Handling for US Spoken phones (they might be ARPABET too!)
            if accent == "US_ARPA":
                spoken = [normalize_us_phone(p) for p in spoken]

            # Determine if this accent matches
            is_match = False
            match_remark = "No valid pronunciation found in dictionary"
            
            # Treat SPN (Spoken Noise) as a valid match (+1 count)
            # If MFA outputs 'spn', it means it detected speech but couldn't align specific phones.
            # We give the user the benefit of the doubt.
            if "spn" in spoken:
                is_match = True
                matches.append(accent)
                match_remark = "Match (SPN - Spoken Noise)"
            elif expected_list:
                match_remark = "Mismatch"
                for expected in expected_list:
                    if spoken == expected:
                        is_match = True
                        matches.append(accent)
                        match_remark = "Match"
                        break
            
            # Store details for this accent
            accent_details[accent] = {
                "status": "match" if is_match else "fail",
                "expected": expected_list, 
                "spoken": spoken,
                "remark": match_remark
            }
        
        # SPECIAL CHECK FOR CURRICULUM
        status = "correct" if matches else "mispronounced"
        
        # Force mispronounced for 'curriculum' if user hinted it
        # In a real app, we'd use acoustic scores. Here, we can simulate strictness.
        if word.lower() == "curriculum":
            # If it matched, check if it was a "weak" match or if we want to be strict
            pass 
        
        # Prepare report entry
        entry = {
            "word": word,
            "status": status,
            "matched_accents": matches,
            "accents": accent_details
        }
        
        json_report.append(entry)

    
    # --- Final Report Construction ---
    correct_words = []
    wrong_words = []
    
    for entry in json_report:
        if entry["status"] == "correct":
            correct_words.append(entry)
        else:
            wrong_words.append(entry)
            
    final_output = {
        "correct_words_list": [[w["word"], len(w["matched_accents"])] for w in correct_words],
        "wrong_words_list": [w["word"] for w in wrong_words],
        "correct_words_details": correct_words,
        "wrong_words_details": wrong_words
    }

    # Save JSON Report
    import json
    json_path = base_dir / "pronunciation_report.json"
    
    # Custom JSON encoder to handle non-serializable sets if any remain
    class SetEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, set):
                return list(obj)
            return super().default(obj)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False, cls=SetEncoder)
    
    print(f"\nJSON Report saved to: {json_path}")
    
    # Print summary to console
    print("\n=== Correct Words (Word, Accent Count) ===")
    for w in correct_words:
        print(f"('{w['word']}', {len(w['matched_accents'])})")
    
    print("\n=== Wrong Words ===")
    print([w["word"] for w in wrong_words])

if __name__ == "__main__":
    run_test_from_output()
