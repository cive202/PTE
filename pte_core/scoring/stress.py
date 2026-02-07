import numpy as np
import librosa

def calculate_energy(y):
    """Calculate RMS energy of an audio segment."""
    if len(y) == 0:
        return 0
    return np.sqrt(np.mean(y**2))

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
        y, sr = librosa.load(audio_path, sr=16000, offset=start_time, duration=end_time-start_time)
        
        # 2. Group Phones into Syllables (Heuristic: Vowel is nucleus)
        vowels = {'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'EH', 'ER', 'EY', 'IH', 'IY', 'OW', 'OY', 'UH', 'UW'}
        
        # Adjust phoneme times to be relative to word start for audio slicing
        rel_phones = []
        for p, s, e in phonemes_with_times:
            rel_phones.append((p, s - start_time, e - start_time, s, e)) # Keep absolute times too
            
        observed_vowels = []
        for p, rel_s, rel_e, abs_s, abs_e in rel_phones:
            # Strip numbers if present (MFA might return AH0)
            p_clean = ''.join([c for c in p if not c.isdigit()])
            if p_clean in vowels:
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
        for i, v in enumerate(observed_vowels):
            v['is_max_stress'] = (i == max_idx)
            v['expected_stress'] = reference_stress_pattern[i]
                
        if max_idx == prim_idx:
            result["score"] = 1.0
            result["match_info"] = "Perfect match"
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
