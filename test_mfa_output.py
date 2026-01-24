
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
from pte_core.phonetics.cmudict import load_cmudict, ensure_cmudict_available

def run_test_from_output():
    # Paths
    base_dir = Path(r"c:\Users\Acer\DataScience\PTE\PTE_MFA_TESTER_DOCKER")
    wav_path = base_dir / "data" / "Education.wav"
    text_path = base_dir / "data" / "Education.txt"
    textgrid_path = base_dir / "output" / "Education.TextGrid"

    print(f"Reading TextGrid from: {textgrid_path}")
    
    # Read words and phones
    try:
        mfa_words = read_word_textgrid(str(textgrid_path))
        phones = read_phone_textgrid(str(textgrid_path))
    except Exception as e:
        print(f"Error reading TextGrid: {e}")
        return

    print(f"Found {len(mfa_words)} words and {len(phones)} phones.")
    if len(mfa_words) > 0:
        print(f"Sample words: {mfa_words[:3]}")
        # Check for alignment failure
        unk_count = sum(1 for w in mfa_words if w.get("word") == "<unk>")
        if unk_count > len(mfa_words) * 0.5:
            print("\n!!! CRITICAL WARNING !!!")
            print(f"High number of <unk> words detected ({unk_count}/{len(mfa_words)}).")
            print("This indicates that MFA failed to align the text.")
            print("Possible causes:")
            print("1. Dictionary mismatch: The dictionary phones (IPA?) might not match the Acoustic Model (ARPABET?).")
            print("2. Out-of-Vocabulary: Words in text are not in the dictionary.")
            print("3. Audio quality issues preventing alignment.")
            print("The scoring results below will be invalid.\n")

    if len(phones) > 0:
        print(f"Sample phones: {phones[:3]}")

    # Read reference text (though we mostly use the TextGrid words for now)
    try:
        with open(text_path, "r", encoding="utf-8") as f:
            reference_text = f.read().strip()
    except Exception as e:
        print(f"Error reading text file: {e}")
        reference_text = ""

    # --- Logic adapted from assess_pronunciation_mfa ---
    
    # Group phones by word
    word_phones: Dict[int, List[Dict[str, Any]]] = {}
    phone_idx = 0
    
    for word_idx, word_align in enumerate(mfa_words):
        word_start = word_align.get("start")
        word_end = word_align.get("end")
        
        if word_start is None or word_end is None:
            continue
        
        word_phones[word_idx] = []
        while phone_idx < len(phones):
            phone = phones[phone_idx]
            phone_start = phone.get("start", 0.0)
            phone_end = phone.get("end", 0.0)
            
            # Check if phone overlaps with word (simple overlap check)
            # Use a small epsilon for float comparison if needed, but simple comparison usually works for TextGrid
            if phone_start >= word_start - 0.001 and phone_end <= word_end + 0.001:
                word_phones[word_idx].append(phone)
                phone_idx += 1
            elif phone_start > word_end:
                break
            else:
                phone_idx += 1
    
    # Calculate timing metrics
    timing_metrics = {
        "word_duration": calculate_word_duration(mfa_words),
        "phone_rate": calculate_phone_rate(phones),
        "vowel_ratio": calculate_vowel_ratio(phones),
        "hesitations": detect_hesitation(phones),
    }

    # Load CMUdict
    cmu_dict = None
    if ensure_cmudict_available():
        try:
            cmu_dict = load_cmudict()
            print("CMUdict loaded successfully.")
        except Exception as e:
            print(f"Error loading CMUdict: {e}")
    else:
        print("ensure_cmudict_available returned False")
    
    # Assess pronunciation
    results: List[Dict[str, Any]] = []
    dp_phone_scores: List[float] = []
    dp_stress_scores: List[float] = []
    all_patterns: Dict[tuple[str, str], int] = {}
    all_errors: List[tuple[str, str]] = []
    final_stop_opportunities = 0
    final_stop_drops = 0
    
    accent_tolerant = True
    confidence_threshold = 0.75 # Default
    
    print("\nProcessing words...")
    for word_idx, word_align in enumerate(mfa_words):
        word = word_align.get("word", "")
        word_phone_list = word_phones.get(word_idx, [])
        
        # Basic scoring
        phone_score_result = score_pronunciation_from_phones(
            word,
            word_phone_list,
            reference_phones=None,
            cmu_dict=cmu_dict,
            baseline=None,
            accent_tolerant=accent_tolerant,
        )
        
        quality_score = phone_score_result.get("quality_score", 1.0)
        issues = phone_score_result.get("issues", [])
        status = "mispronounced" if quality_score < confidence_threshold else "aligned"
        
        result: Dict[str, Any] = {
            "word": word,
            "start": word_align.get("start"),
            "end": word_align.get("end"),
            "status": status,
            "confidence": quality_score,
            "issues": issues,
        }

        # DP Phoneme Scoring
        pte_phone = None
        pte_stress = None
        
        if cmu_dict and word and word_phone_list:
            try:
                from pte_core.phonetics.cmudict import get_word_pronunciation
                from pte_core.phonetics.phone_mapper import arpabet_to_mfa

                arpabet = get_word_pronunciation(word, cmu_dict)
                if arpabet:
                    expected_phones: List[str] = []
                    for p in arpabet:
                        p_up = p.upper()
                        digit = p_up[-1] if p_up and p_up[-1] in "012" else ""
                        mfa_base = arpabet_to_mfa(p_up)
                        expected_phones.append(f"{mfa_base}{digit}" if digit else mfa_base)

                    observed_phones = [
                        base_phone(p.get("label", "")) for p in word_phone_list
                        if p.get("label", "").strip().upper() not in ("SP", "SIL", "")
                    ]

                    if expected_phones and observed_phones:
                        alignment_path, dp_cost, meta = align_phonemes_with_dp(
                            expected_phones,
                            observed_phones,
                            word=word,
                            accent_tolerant=accent_tolerant,
                        )
                        
                        pte_phone = dp_phone_intelligibility(alignment_path, meta, expected_len=len(expected_phones))
                        pte_stress = dp_stress_accuracy(alignment_path)
                        
                        word_errors, word_patterns = extract_errors_and_patterns(alignment_path)
                        all_errors.extend(word_errors)
                        
                        dp_phone_scores.append(pte_phone)
                        dp_stress_scores.append(pte_stress)
                        
                        for k, v in word_patterns.items():
                            if isinstance(k, tuple) and len(k) == 2:
                                all_patterns[k] = all_patterns.get(k, 0) + int(v or 0)
                        
                        # Stop drop check
                        last_expected = base_phone(expected_phones[-1]) if expected_phones else ""
                        if last_expected in {"T", "K", "P", "D", "B", "G"}:
                            final_stop_opportunities += 1
                            if last_expected not in set(observed_phones):
                                final_stop_drops += 1
            except Exception as e:
                print(f"Error processing word '{word}': {e}")
        
        results.append(result)

    # Summarize
    if dp_phone_scores:
        phone = sum(dp_phone_scores) / len(dp_phone_scores)
        stress_score = sum(dp_stress_scores) / len(dp_stress_scores) if dp_stress_scores else 1.0
        consistency_bonus_score = dp_consistency_bonus(all_patterns)
        rhythm = 1.0 # Placeholder
        
        score_pte = pronunciation_score_0_100(
            phone=phone,
            stress=stress_score,
            rhythm=rhythm,
            consistency_bonus=consistency_bonus_score,
        )
        band = pte_pronunciation_band(score_pte)
        
        print("\n=== PTE Scoring Results ===")
        print(f"Overall PTE Score: {score_pte} (Band: {band})")
        print(f"Phone Intelligibility: {phone:.2f}")
        print(f"Stress Accuracy: {stress_score:.2f}")
        print(f"Consistency Bonus: {consistency_bonus_score:.2f}")
        
        if final_stop_opportunities > 0:
            drop_rate = final_stop_drops / final_stop_opportunities
            print(f"Final Stop Drop Rate: {drop_rate:.2%}")
        
        print("\n=== Word Details ===")
        for res in results[:15]: # Show first 15 words
             print(f"{res['word']}: {res['status']} (Quality: {res['confidence']:.2f}) Issues: {res.get('issues', [])}")
        
        print("\n=== Top Errors ===")
        from collections import Counter
        error_counts = Counter(all_errors)
        for err, count in error_counts.most_common(5):
             print(f"{err[0]} -> {err[1]}: {count} times")

    else:
        print("No pronunciation scores calculated (possibly missing CMUdict or no words aligned).")

if __name__ == "__main__":
    run_test_from_output()
