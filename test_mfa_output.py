import os
import sys
import json
import re
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.absolute()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from pte_core.mfa.textgrid_reader import read_word_textgrid
    from pte_core.mfa.phone_reader import read_phone_textgrid
except ImportError:
    print("Error: pte_core module not found. Make sure you are running from the project root.")
    sys.exit(1)

# --- Configuration ---
DATA_DIR = ROOT_DIR / "PTE_MFA_TESTER_DOCKER"
INPUT_TEXT_FILE = DATA_DIR / "data" / "Cs_degree.txt"
REPORT_FILE = DATA_DIR / "pronunciation_report.json"

ACCENTS = {
    "Indian": {
        "dict": DATA_DIR / "eng_indian_model" / "english_india_mfa.dict",
        "tg": DATA_DIR / "output_indian" / "Cs_degree.TextGrid"
    },
    "Nigerian": {
        "dict": DATA_DIR / "eng_nigeria_model" / "english_nigeria_mfa.dict",
        "tg": DATA_DIR / "output_nigeria" / "Cs_degree.TextGrid"
    },
    "US_ARPA": {
        "dict": DATA_DIR / "eng_us_model" / "english_us_arpa.dict",
        "tg": DATA_DIR / "output_us" / "Cs_degree.TextGrid"
    },
    "US_MFA": {
        "dict": DATA_DIR / "eng_us_model_2" / "english_us_mfa.dict",
        "tg": DATA_DIR / "output_us_mfa" / "Cs_degree.TextGrid"
    },
    "UK": {
        "dict": DATA_DIR / "english_uk_model" / "english_uk_mfa.dict",
        "tg": DATA_DIR / "output_uk" / "Cs_degree.TextGrid"
    }
}

# --- Helpers ---

def load_dictionary(path):
    """Load MFA dictionary into a dict: word -> list of phone tuples.
    Handles both standard CMU-style and MFA probabilistic dictionaries (which have numbers).
    """
    pronunciations = {}
    if not os.path.exists(path):
        print(f"Warning: Dictionary not found: {path}")
        return pronunciations
        
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) > 1:
                word = parts[0].lower()
                
                # Identify where phones start
                # Skip parts that are numbers (probabilities)
                phones_start_idx = 1
                while phones_start_idx < len(parts):
                    # Check if parts[phones_start_idx] is a number
                    try:
                        float(parts[phones_start_idx])
                        phones_start_idx += 1
                    except ValueError:
                        break
                        
                phones = tuple(p.lower() for p in parts[phones_start_idx:])
                if phones:
                    if word not in pronunciations:
                        pronunciations[word] = []
                    pronunciations[word].append(phones)
    return pronunciations

def normalize_phone(p, keep_stress=False):
    """Normalize phone. 
    If keep_stress=False, removes digits.
    Always lowercases.
    """
    p = p.lower()
    if not keep_stress:
        p = re.sub(r'\d+', '', p)
    return p

def get_phones_for_word(word_info, all_phones):
    """Extract phones that overlap with the word interval."""
    w_start = word_info['start']
    w_end = word_info['end']
    word_phones = []
    
    for p in all_phones:
        # Strict containment with small tolerance
        if p['start'] >= w_start - 0.01 and p['end'] <= w_end + 0.01:
            word_phones.append(p['label'])
    return word_phones

def validate_pronunciation(word, observed_phones, dictionary):
    """Check if observed phones match any valid dictionary pronunciation.
    
    Returns:
        is_phoneme_match (bool): Do the sounds match (ignoring stress)?
        msg (str): Status message
        is_stress_match (bool): Do the stress markers match (if available)?
    """
    if word.lower() not in dictionary:
        return False, "OOV", False
        
    valid_prons = dictionary[word.lower()]
    
    # 1. Phoneme Match Check (Ignore Stress)
    obs_norm = [normalize_phone(p, keep_stress=False) for p in observed_phones if p not in ('sil', 'sp', 'spn')]
    
    if not obs_norm:
        return False, "No phones detected", False

    phoneme_matches = [] # List of dictionary prons that match phonetically
    
    for valid_pron in valid_prons:
        val_norm = [normalize_phone(p, keep_stress=False) for p in valid_pron]
        if obs_norm == val_norm:
            phoneme_matches.append(valid_pron)
            
    if not phoneme_matches:
        return False, f"Mismatch: {obs_norm} not in {valid_prons}", False
        
    # 2. Stress Match Check (Among the phonetically valid ones)
    # We check if ANY of the phoneme-matching dictionary entries also match stress-wise
    # with the observed phones.
    
    obs_stress = [normalize_phone(p, keep_stress=True) for p in observed_phones if p not in ('sil', 'sp', 'spn')]
    
    # Check if observed has any stress markers (digits)
    has_stress_info = any(re.search(r'\d', p) for p in obs_stress)
    
    if not has_stress_info:
        # If observed has no stress info (e.g. IPA model without stress), we can't fail stress check
        # We consider it a "Soft Pass" or N/A. Let's return True to be lenient.
        return True, "Exact Match (No Stress Info)", True
        
    for valid_pron in phoneme_matches:
        val_stress = [normalize_phone(p, keep_stress=True) for p in valid_pron]
        if obs_stress == val_stress:
            return True, "Exact Match (With Stress)", True
            
    # If we reached here: Phonemes matched, but Stress didn't match any of the valid candidates
    return True, "Stress Mismatch", False

def analyze_pauses(textgrid_path, ref_text):
    """Analyze pauses using US_MFA timing."""
    if not os.path.exists(textgrid_path):
        return []

    words = read_word_textgrid(str(textgrid_path))
    words.sort(key=lambda x: x['start'])
    
    pauses = []
    
    # Simple punctuation check in ref text
    # This is a heuristic mapping; for robust mapping we'd need Needleman-Wunsch
    # Here we assume linear alignment for simplicity as per previous context
    
    for i in range(len(words) - 1):
        current_word = words[i]
        next_word = words[i+1]
        
        gap = next_word['start'] - current_word['end']
        
        if gap > 0.3:
            pauses.append({
                "type": "Hesitation",
                "duration": gap,
                "after_word": current_word['word'],
                "context": f"{current_word['word']} ... {next_word['word']}"
            })
            
    return pauses

def detect_missing_words(textgrid_path):
    """Detect words with negligible duration (forced alignment artifacts)."""
    if not os.path.exists(textgrid_path):
        return []
        
    words = read_word_textgrid(str(textgrid_path))
    missing = []
    
    for w in words:
        duration = w['end'] - w['start']
        if duration < 0.05:
            missing.append({
                "word": w['word'],
                "duration": duration,
                "start": w['start']
            })
    return missing

# --- Main ---

def main():
    print("=== PTE MFA Validation Pipeline ===")
    
    if not os.path.exists(INPUT_TEXT_FILE):
        print(f"Error: Input file not found: {INPUT_TEXT_FILE}")
        return

    with open(INPUT_TEXT_FILE, "r", encoding="utf-8") as f:
        ref_text_content = f.read().strip()
        # Simple tokenization for reference
        ref_words = [w.strip(".,!?;:\"").lower() for w in ref_text_content.split()]

    print(f"Reference Text: {ref_text_content[:50]}...")
    
    # Load Dictionaries
    dicts = {}
    print("Loading dictionaries...")
    for accent, paths in ACCENTS.items():
        dicts[accent] = load_dictionary(paths['dict'])

    # Validation Results
    word_results = {} # word_index -> {word, status, matches: []}
    
    # We iterate based on the US_MFA textgrid words as the "anchor" 
    # (assuming it aligns with ref_text mostly)
    # Ideally we should align ref_text to TextGrids, but we'll use US_MFA as base
    
    us_mfa_path = ACCENTS["US_MFA"]["tg"]
    if not os.path.exists(us_mfa_path):
         print("Critical: US_MFA TextGrid not found. Cannot proceed with base alignment.")
         return
         
    base_words = read_word_textgrid(str(us_mfa_path))
    
    for i, w_obj in enumerate(base_words):
        word_text = w_obj['word']
        word_results[i] = {
            "word": word_text,
            "correct": False,
            "accent_matches": [],
            "details": {}
        }
        
        # Check against all accents
        for accent, paths in ACCENTS.items():
            tg_path = paths['tg']
            if not os.path.exists(tg_path):
                continue
                
            # Read accent TG
            acc_words = read_word_textgrid(str(tg_path))
            acc_phones = read_phone_textgrid(str(tg_path))
            
            # Find corresponding word in this accent's TG
            # Simple index matching (assuming all aligners output same number of intervals)
            # Warning: If alignment failed for some words, indices might shift. 
            # But MFA typically outputs all words even if duration is 0.
            if i < len(acc_words):
                acc_w_obj = acc_words[i]
                
                # Double check word match
                if acc_w_obj['word'].lower() != word_text.lower():
                     word_results[i]["details"][accent] = "Word Mismatch (Alignment Drift)"
                     continue
                
                # Extract phones
                observed = get_phones_for_word(acc_w_obj, acc_phones)
                
                # Validate
                is_valid, msg, stress_ok = validate_pronunciation(word_text, observed, dicts[accent])
                
                word_results[i]["details"][accent] = {
                    "valid": is_valid,
                    "phones": observed,
                    "msg": msg,
                    "stress_match": stress_ok
                }
                
                if is_valid:
                    word_results[i]["correct"] = True
                    word_results[i]["accent_matches"].append(accent)
                    
                    # Track stress match
                    # If ANY accent matches phonemes, we check if ANY accent matched stress too
                    # We initialize stress_match as False, and upgrade to True if we find a perfect match
                    if "stress_correct" not in word_results[i]:
                        word_results[i]["stress_correct"] = False
                    
                    if stress_ok:
                        word_results[i]["stress_correct"] = True

    # Compile Lists
    correct_words = []
    wrong_words = []
    stress_error_words = [] # Correct Phonemes but Wrong Stress
    
    for idx, res in word_results.items():
        if res["correct"]:
            correct_words.append(res["word"])
            # Check stress
            if not res.get("stress_correct", False):
                stress_error_words.append({
                    "word": res["word"],
                    "details": "Phonemes correct, but Stress mismatched"
                })
        else:
            wrong_words.append(res["word"])
            
    # Pause & Missing Analysis (using US_MFA)
    pauses = analyze_pauses(us_mfa_path, ref_text_content)
    missing = detect_missing_words(us_mfa_path)
    
    # Report
    report = {
        "summary": {
            "total_words": len(word_results),
            "correct_count": len(correct_words),
            "wrong_count": len(wrong_words),
            "stress_error_count": len(stress_error_words),
            "accuracy": len(correct_words) / len(word_results) if word_results else 0
        },
        "correct_words": correct_words,
        "wrong_words": wrong_words,
        "stress_errors": stress_error_words,
        "missing_words_detected": missing,
        "pause_analysis": pauses,
        "detailed_results": word_results
    }
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    print("\n=== Validation Complete ===")
    print(f"Total Words: {len(word_results)}")
    print(f"Correct: {len(correct_words)}")
    print(f"Wrong: {len(wrong_words)}")
    print(f"Stress Errors: {len(stress_error_words)}")
    print(f"Missing (Duration < 0.05s): {len(missing)}")
    print(f"Pauses/Hesitations: {len(pauses)}")
    print(f"Report saved to: {REPORT_FILE}")

if __name__ == "__main__":
    main()
