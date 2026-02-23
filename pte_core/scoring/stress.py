import numpy as np
import librosa
import re
import unicodedata


ARPA_VOWELS = {
    'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'EH', 'ER', 'EY', 'IH', 'IY', 'OW', 'OY', 'UH', 'UW'
}

IPA_VOWEL_CHARS = set("aeiouəɚɝɪʊɛæɑɒɔʌɜɐɨʉɵøyɯɤ")
IPA_VOWEL_TOKENS = {
    "a", "e", "i", "o", "u", "ə", "ɚ", "ɝ", "ɪ", "ʊ", "ɛ", "æ", "ɑ", "ɒ", "ɔ", "ʌ", "ɜ", "ɐ",
    "ɨ", "ʉ", "ɵ", "ø", "y", "ɯ", "ɤ", "aɪ", "aʊ", "eɪ", "oʊ", "ɔɪ", "aj", "aw", "ej", "ow", "oj",
}

def calculate_energy(y):
    """Calculate RMS energy of an audio segment."""
    if len(y) == 0:
        return 0
    return np.sqrt(np.mean(y**2))


def _strip_combining_marks(token):
    normalized = unicodedata.normalize("NFD", token)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _normalize_phone_token(token):
    t = str(token or "").strip()
    if not t:
        return ""
    t = _strip_combining_marks(t)
    # Remove common suprasegmentals/diacritics that are irrelevant for vowel detection.
    for mark in ("ː", "ˑ", "˞", "ʰ", "ʲ", "ʷ", "ˠ", "ˤ"):
        t = t.replace(mark, "")
    return t


def _is_arpa_vowel(phone):
    base = re.sub(r'\d+', '', str(phone or "").upper())
    return base in ARPA_VOWELS


def _is_ipa_vowel(phone):
    p = _normalize_phone_token(phone).lower()
    if not p:
        return False
    if p in IPA_VOWEL_TOKENS:
        return True
    return any(ch in IPA_VOWEL_CHARS for ch in p)


def _is_vowel_phone(phone):
    return _is_arpa_vowel(phone) or _is_ipa_vowel(phone)

def get_syllable_stress_details(audio_path, start_time, end_time, phonemes_with_times, reference_stress_pattern):
    """
    Calculate stress score and return detailed timing/energy info.
    
    Args:
        audio_path: Path to wav file
        start_time: Word start time
        end_time: Word end time
        phonemes_with_times: List of (phone, start, end) from MFA
        reference_stress_pattern: String like "010" (0=unstressed, 1=primary, 2=secondary)
        
    Returns:
        dict: {
            "score": float,
            "syllables": list of dicts {phone, start, end, energy, duration, is_stressed},
            "ref_pattern": str,
            "match_info": str
        }
    """
    try:
        # 1. Load Audio Segment
        try:
            y, sr = librosa.load(audio_path, sr=16000, offset=start_time, duration=end_time-start_time)
        except Exception as load_err:
            print(f"librosa.load failed for {audio_path} at {start_time}-{end_time}: {load_err}")
            return {
                "score": 0.5,
                "syllables": [],
                "ref_pattern": reference_stress_pattern,
                "match_info": "Audio load error"
            }
        
        # 2. Group Phones into Syllables (Heuristic: vowel nucleus in ARPA or IPA)
        # Adjust phoneme times to be relative to word start for audio slicing
        rel_phones = []
        for p, s, e in phonemes_with_times:
            rel_phones.append((p, s - start_time, e - start_time, s, e)) # Keep absolute times too
            
        observed_vowels = []
        for p, rel_s, rel_e, abs_s, abs_e in rel_phones:
            if _is_vowel_phone(p):
                # Extract energy and duration
                s_idx = int(rel_s * sr)
                e_idx = int(rel_e * sr)
                if s_idx < 0: s_idx = 0
                if e_idx > len(y): e_idx = len(y)
                
                y_seg = y[s_idx:e_idx]
                energy = calculate_energy(y_seg)
                duration = rel_e - rel_s
                observed_vowels.append({
                    'phone': p,
                    'start': round(abs_s, 3),
                    'end': round(abs_e, 3),
                    'energy': round(float(energy), 4),
                    'duration': round(float(duration), 3)
                })

        # 3. Compare with Reference
        result = {
            "score": 1.0,
            "syllables": observed_vowels,
            "ref_pattern": reference_stress_pattern,
            "match_info": "No reference pattern"
        }

        if not reference_stress_pattern:
            return result
            
        ref_len = len(reference_stress_pattern)
        obs_len = len(observed_vowels)
        
        if obs_len == 0:
            result["score"] = 0.0
            result["match_info"] = "No vowels detected"
            return result
            
        if ref_len != obs_len:
            result["score"] = 0.8
            result["match_info"] = f"Syllable count mismatch (expected {ref_len}, got {obs_len})"
            return result
            
        # 4. Scoring Logic
        try:
            prim_idx = reference_stress_pattern.index('1')
        except ValueError:
            # No primary stress in ref?
            result["match_info"] = "No primary stress in reference"
            return result
            
        # Find vowel with max intensity
        max_intensity = -1
        max_idx = -1
        
        for i, v in enumerate(observed_vowels):
            intensity = v['energy'] * v['duration']
            v['intensity'] = round(float(intensity), 4) # Add intensity to result
            if intensity > max_intensity:
                max_intensity = intensity
                max_idx = i
                
        # Mark observed stress
        observed_pattern_list = ['0'] * len(observed_vowels)
        for i, v in enumerate(observed_vowels):
            v['is_max_stress'] = (i == max_idx)
            v['expected_stress'] = reference_stress_pattern[i]
            if i == max_idx:
                observed_pattern_list[i] = '1'
        
        result['observed_pattern'] = "".join(observed_pattern_list)
                
        # Relaxed Logic: Accept 2 (Secondary Stress) as valid max stress if 1 is expected
        # or if existing logic matches
        expected_stress_at_max = reference_stress_pattern[max_idx]
        
        if max_idx == prim_idx:
            result["score"] = 1.0
            result["match_info"] = "Perfect match"
        elif expected_stress_at_max == '2':
             # Allow secondary stress to carry main emphasis (common in dialects/speech rates)
            result["score"] = 0.9 
            result["match_info"] = "Acceptable variation (Secondary Stress)"
        else:
            result["score"] = 0.5
            result["match_info"] = f"Stress mismatch (expected index {prim_idx}, observed {max_idx})"

        return result

    except Exception as e:
        print(f"Stress calc error: {e}")
        return {
            "score": 1.0,
            "syllables": [],
            "ref_pattern": reference_stress_pattern,
            "match_info": f"Error: {str(e)}"
        }

def get_syllable_stress_score(audio_path, start_time, end_time, phonemes_with_times, reference_stress_pattern):
    """Wrapper for backward compatibility if needed, but we will update usage."""
    res = get_syllable_stress_details(audio_path, start_time, end_time, phonemes_with_times, reference_stress_pattern)
    return res["score"]
