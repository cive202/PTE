"""Main API for MFA-based pronunciation assessment."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .aligner import align_with_mfa
from .asr_aligner import align_mfa_to_asr
from .scorer import score_pronunciation_from_phones
from .timing_metrics import (
    calculate_phone_rate,
    calculate_vowel_ratio,
    calculate_word_duration,
    detect_hesitation,
)
from .phoneme_alignment import (
    align_phonemes_with_dp,
    calculate_intelligibility_score as dp_phone_intelligibility,
    consistency_bonus as dp_consistency_bonus,
    extract_errors_and_patterns,
    stress_accuracy as dp_stress_accuracy,
    base_phone,
    PHONEME_SIMILARITY_COST_MULT,
)
from pte_pronunciation import (
    pronunciation_score_0_100,
    pte_pronunciation_band,
    generate_feedback_strings,
)

try:
    from ..phonetics.cmudict import load_cmudict, ensure_cmudict_available
    CMUDICT_AVAILABLE = True
except ImportError:
    CMUDICT_AVAILABLE = False
    load_cmudict = None  # type: ignore
    ensure_cmudict_available = None  # type: ignore

try:
    from .accent_config import INTELLIGIBILITY_FLOOR
    from .intelligibility import assess_intelligibility
    from .speaker_normalization import analyze_speaker_baseline
    ACCENT_FEATURES_AVAILABLE = True
except ImportError:
    ACCENT_FEATURES_AVAILABLE = False
    INTELLIGIBILITY_FLOOR = 0.0  # No floor if not available
    assess_intelligibility = None  # type: ignore
    analyze_speaker_baseline = None  # type: ignore


def assess_pronunciation_mfa(
    wav_path: str,
    reference_text: str,
    *,
    confidence_threshold: float = 0.75,
    acoustic_model: str = " ",
    dictionary: str = "english_us_arpa",
    asr_words: Optional[List[Dict[str, Any]]] = None,
    use_cmudict: bool = True,
    accent_tolerant: bool = True,
    intelligibility_floor: float = 0.55,
) -> List[Dict[str, Any]]:
    """Use MFA to assess pronunciation and return word-level results with phone-level analysis.
    
    MFA is a forced aligner - it provides precise timestamps and phone-level alignment,
    but cannot detect missed words or judge correctness. This function uses phone
    duration analysis to assess pronunciation quality.
    
    Args:
        wav_path: Path to audio file
        reference_text: Reference transcription
        confidence_threshold: Threshold for pronunciation quality score (default: 0.75)
        acoustic_model: MFA acoustic model name
        dictionary: MFA dictionary name
        asr_words: Optional ASR word alignments for MFA+ASR integration
        use_cmudict: Whether to use CMUdict for expected phones (default: True)
        accent_tolerant: Whether to use accent-tolerant scoring (default: True)
        intelligibility_floor: Minimum score for intelligible speech (default: 0.55)
        
    Returns:
        List of dicts with:
            - word: str
            - start: float
            - end: float
            - status: "aligned" | "mispronounced" (based on phone analysis)
            - confidence: float (real quality score from phone analysis, 0.0-1.0)
            - phone_quality_score: float
            - timing_metrics: Dict[str, float]
            - issues: List[str] (e.g., ["vowel_shortened", "consonant_missing"])
    """
    # Run MFA alignment with phone-level data
    alignment_result = align_with_mfa(
        wav_path,
        reference_text,
        acoustic_model=acoustic_model,
        dictionary=dictionary,
        include_phones=True,
    )
    
    mfa_words = alignment_result.get("words", [])
    phones = alignment_result.get("phones", [])
    
    # Group phones by word (simplified - assumes phones are in word order)
    # In practice, you'd need word-to-phone mapping from MFA output
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
            
            # Check if phone overlaps with word
            if phone_start >= word_start and phone_end <= word_end:
                word_phones[word_idx].append(phone)
                phone_idx += 1
            elif phone_start > word_end:
                break
            else:
                phone_idx += 1
    
    # Calculate timing metrics for entire utterance
    timing_metrics = {
        "word_duration": calculate_word_duration(mfa_words),
        "phone_rate": calculate_phone_rate(phones),
        "vowel_ratio": calculate_vowel_ratio(phones),
        "hesitations": detect_hesitation(phones),
    }
    
    # Analyze speaker baseline for accent-tolerant scoring
    baseline: Optional[Dict[str, float]] = None
    if accent_tolerant and ACCENT_FEATURES_AVAILABLE and analyze_speaker_baseline:
        try:
            # Get total duration from phones
            if phones:
                total_duration = max(p.get("end", 0.0) for p in phones)
            else:
                total_duration = 3.0
            
            baseline = analyze_speaker_baseline(phones, mfa_words, total_duration)
        except Exception:
            # Fallback: continue without baseline
            pass
    
    # Assess intelligibility
    intelligibility_result: Optional[Dict[str, Any]] = None
    is_intelligible = False
    if accent_tolerant and ACCENT_FEATURES_AVAILABLE and assess_intelligibility and baseline:
        try:
            intelligibility_result = assess_intelligibility(phones, mfa_words, baseline)
            is_intelligible = intelligibility_result.get("is_intelligible", False)
        except Exception:
            # Fallback: continue without intelligibility check
            pass
    
    # Load CMUdict if requested and available
    cmu_dict = None
    if use_cmudict and CMUDICT_AVAILABLE and ensure_cmudict_available and load_cmudict:
        try:
            if ensure_cmudict_available():
                cmu_dict = load_cmudict()
        except Exception:
            # Fallback: continue without CMUdict
            pass
    
    # Assess pronunciation for each word
    results: List[Dict[str, Any]] = []

    # PTE-style utterance aggregation (computed from per-word DP alignments)
    dp_phone_scores: List[float] = []
    dp_stress_scores: List[float] = []
    all_patterns: Dict[tuple[str, str], int] = {}
    all_errors: List[tuple[str, str]] = []
    final_stop_opportunities = 0
    final_stop_drops = 0
    
    for word_idx, word_align in enumerate(mfa_words):
        word = word_align.get("word", "")
        word_phone_list = word_phones.get(word_idx, [])
        
        # Score pronunciation based on phone durations
        phone_score_result = score_pronunciation_from_phones(
            word,
            word_phone_list,
            reference_phones=None,  # Will be filled from CMUdict if available
            cmu_dict=cmu_dict,
            baseline=baseline,
            accent_tolerant=accent_tolerant,
        )
        
        quality_score = phone_score_result.get("quality_score", 1.0)
        issues = phone_score_result.get("issues", [])
        
        # Apply intelligibility floor if speech is intelligible
        if is_intelligible and accent_tolerant:
            quality_score = max(quality_score, intelligibility_floor)
        
        # Determine status based on quality score
        status = "mispronounced" if quality_score < confidence_threshold else "aligned"
        
        result: Dict[str, Any] = {
            "word": word,
            "start": word_align.get("start"),
            "end": word_align.get("end"),
            "status": status,
            "confidence": quality_score,  # Real quality score, not fake
            "phone_quality_score": quality_score,
            "timing_metrics": timing_metrics,  # Shared across all words
            "issues": issues,
        }

        # --- PTE-style DP phoneme scoring (explainable) ---
        # Only when CMUdict is available and we have observed phones for the word.
        pte_phone = None
        pte_stress = None
        pte_dp_cost = None
        pte_dp_max_cost = None
        try:
            if cmu_dict and word and word_phone_list:
                from phonetics.cmudict import get_word_pronunciation
                from phonetics.phone_mapper import arpabet_to_mfa

                arpabet = get_word_pronunciation(word, cmu_dict)
                if arpabet:
                    # Convert ARPAbet -> MFA base, but preserve stress digits on vowels (AA1, IH0, ...)
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
                        
                        # Calculate intelligibility with expected length
                        pte_phone = dp_phone_intelligibility(alignment_path, meta, expected_len=len(expected_phones))
                        pte_stress = dp_stress_accuracy(alignment_path)
                        pte_dp_cost = float(meta.get("total_cost", dp_cost))
                        pte_dp_max_cost = float(meta.get("max_cost", 1.0))

                        # Extract errors and patterns for feedback
                        word_errors, word_patterns = extract_errors_and_patterns(alignment_path)
                        all_errors.extend(word_errors)

                        # Aggregate scores
                        dp_phone_scores.append(pte_phone)
                        dp_stress_scores.append(pte_stress)

                        # Aggregate patterns
                        for k, v in word_patterns.items():
                            if isinstance(k, tuple) and len(k) == 2:
                                all_patterns[k] = all_patterns.get(k, 0) + int(v or 0)

                        # Final stop drop rate (word-final expected stop deleted)
                        last_expected = base_phone(expected_phones[-1]) if expected_phones else ""
                        if last_expected in {"T", "K", "P", "D", "B", "G"}:
                            final_stop_opportunities += 1
                            if last_expected not in set(observed_phones):
                                final_stop_drops += 1

                        result["pte_alignment"] = alignment_path
        except Exception:
            # Keep base MFA result even if DP scoring fails for a word
            pass

        if pte_phone is not None:
            result["pte_phone_intelligibility"] = pte_phone
        if pte_stress is not None:
            result["pte_stress_accuracy"] = pte_stress
        if pte_dp_cost is not None:
            result["pte_dp_cost"] = pte_dp_cost
        if pte_dp_max_cost is not None:
            result["pte_dp_max_cost"] = pte_dp_max_cost
        
        # Add intelligibility metadata if available
        if intelligibility_result:
            result["intelligibility"] = intelligibility_result.get("confidence", 0.0)
            result["is_intelligible"] = is_intelligible
        
        # Add MFA+ASR alignment if ASR words provided
        if asr_words:
            aligned = align_mfa_to_asr([word_align], asr_words)
            if aligned:
                result.update({
                    "asr_aligned": aligned[0].get("asr_aligned", False),
                    "asr_word": aligned[0].get("asr_word"),
                    "overlap_duration": aligned[0].get("overlap_duration", 0.0),
                    "pronunciation_driven_substitution": aligned[0].get(
                        "pronunciation_driven_substitution", False
                    ),
                })
        
        results.append(result)

    # --- Utterance-level PTE-style pronunciation score (10-90 scale + band + feedback) ---
    if dp_phone_scores:
        phone = sum(dp_phone_scores) / len(dp_phone_scores)
        stress_score = sum(dp_stress_scores) / len(dp_stress_scores) if dp_stress_scores else 1.0

        # Consistency bonus: additive reward for systematic accent patterns
        consistency_bonus_score = dp_consistency_bonus(all_patterns)

        # Rhythm: placeholder here (report_generator will compute from pause penalties if available)
        rhythm = 1.0

        # Calculate PTE-style pronunciation score (10-90 scale)
        score_pte = pronunciation_score_0_100(
            phone=phone,
            stress=stress_score,
            rhythm=rhythm,
            consistency_bonus=consistency_bonus_score,
        )
        band = pte_pronunciation_band(score_pte)

        final_stop_drop_rate = (
            (final_stop_drops / final_stop_opportunities) if final_stop_opportunities > 0 else None
        )

        # Format patterns for feedback (string keys)
        patterns_formatted = {f"{k[0]}->{k[1]}": v for k, v in all_patterns.items()}

        pte_summary: Dict[str, Any] = {
            "phone": phone,
            "stress": stress_score,
            "rhythm": rhythm,
            "consistency_bonus": consistency_bonus_score,
            "score_pte": score_pte,  # PTE scale: 10-90
            "pte_band": band,
            "final_stop_drop_rate": final_stop_drop_rate,
            "patterns": patterns_formatted,
            "errors": all_errors[:10],  # Top 10 errors for feedback
        }
        pte_summary["feedback"] = generate_feedback_strings(pte_summary)

        # Attach summary on every word result (easy downstream merge without schema changes)
        for r in results:
            r["pte_summary"] = pte_summary

    return results
