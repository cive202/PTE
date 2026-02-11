import os
import shutil
import subprocess
import json
import re
import uuid
import time
import sys
import difflib
import concurrent.futures
from pathlib import Path

# Add project root to path to import pte_core
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # /home/sushil/developer/pte/PTE
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pte_core.asr.voice2text import voice2text
from pte_core.pause.pause_evaluator import evaluate_pause
from pte_core.pause.hesitation import apply_hesitation_clustering, aggregate_pause_penalty
from pte_core.pause.speech_rate import calculate_speech_rate_scale
from read_aloud.alignment.normalizer import PAUSE_PUNCTUATION, is_punctuation
from pte_core.phoneme.g2p import PhonemeReferenceBuilder
from pte_core.asr.phoneme_recognition import call_phoneme_service
from pte_core.scoring.pronunciation import per, label_from_per, analyze_phoneme_errors
from pte_core.scoring.stress import get_syllable_stress_score, get_syllable_stress_details
from pte_core.scoring.accent_scorer import AccentTolerantScorer
from src.shared.paths import (
    MFA_BASE_DIR as SHARED_MFA_BASE_DIR,
    MFA_RUNTIME_DIR as SHARED_MFA_RUNTIME_DIR,
    ensure_runtime_dirs,
)
from src.shared.services import MFA_DOCKER_IMAGE

# --- Configuration ---
MFA_BASE_DIR = SHARED_MFA_BASE_DIR
MFA_RUNTIME_DIR = SHARED_MFA_RUNTIME_DIR
ensure_runtime_dirs()

# Docker Mount:
# - MFA_BASE_DIR (Host) -> /models (Container)
# - MFA_RUNTIME_DIR (Host) -> /runtime (Container)
DOCKER_IMAGE = MFA_DOCKER_IMAGE

# Accent Configuration
# Paths are relative to MFA_BASE_DIR (Host) which is /data (Container)
ACCENTS_CONFIG = {
    "Indian": {
        "dict_rel": "eng_indian_model/english_india_mfa.dict",
        "model_rel": "eng_indian_model/english_mfa.zip"
    },
    "US_ARPA": {
        "dict_rel": "eng_us_model/english_us_arpa.dict",
        "model_rel": "eng_us_model/english_us_arpa.zip"
    },
    "US_MFA": {
        "dict_rel": "eng_us_model_2/english_us_mfa.dict",
        "model_rel": "eng_us_model_2/english_mfa.zip"
    },
    "UK": {
        "dict_rel": "english_uk_model/english_uk_mfa.dict",
        "model_rel": "english_uk_model/english_mfa.zip"
    },
    "Nigerian": {
        "dict_rel": "eng_nigeria_model/english_nigeria_mfa.dict",
        "model_rel": "eng_nigeria_model/english_mfa.zip"
    },
    "NonNative": {
        "dict_rel": "english_nonnative/english_nonnative_mfa.dict",
        "model_rel": "english_nonnative/english_mfa.zip"
    }
}

# --- Validation Logic (Ported from test_mfa_output.py) ---

# --- Validation Logic (Ported from test_mfa_output.py) ---

def load_dictionary(path):
    """Load MFA dictionary mapping words to phone tuples."""
    pronunciations = {}
    if not os.path.exists(path):
        print(f"Warning: Dictionary not found: {path}")
        return pronunciations
        
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) > 1:
                word = parts[0].lower()
                phones_start_idx = 1
                while phones_start_idx < len(parts):
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
    """Normalize phone string (lowercase, optionally remove stress)."""
    p = p.lower()
    if not keep_stress:
        p = re.sub(r'\d+', '', p)
    return p

def validate_pronunciation(word, observed_phones, dictionary):
    """Validate if observed phones match any valid pronunciation in the dictionary."""
    if word.lower() not in dictionary:
        return False, "OOV", False
        
    valid_prons = dictionary[word.lower()]
    obs_norm = [normalize_phone(p, keep_stress=False) for p in observed_phones if p not in ('sil', 'sp', 'spn')]
    
    if not obs_norm:
        return False, "No phones detected", False

    phoneme_matches = []
    for valid_pron in valid_prons:
        val_norm = [normalize_phone(p, keep_stress=False) for p in valid_pron]
        if obs_norm == val_norm:
            phoneme_matches.append(valid_pron)
            
    if not phoneme_matches:
        return False, "Mismatch", False
        
    # Stress Check
    obs_stress = [normalize_phone(p, keep_stress=True) for p in observed_phones if p not in ('sil', 'sp', 'spn')]
    has_stress_info = any(re.search(r'\d', p) for p in obs_stress)
    
    if not has_stress_info:
        return True, "Exact Match (No Stress Info)", True
        
    for valid_pron in phoneme_matches:
        val_stress = [normalize_phone(p, keep_stress=True) for p in valid_pron]
        if obs_stress == val_stress:
            return True, "Exact Match (With Stress)", True
            
    return True, "Stress Mismatch", False

def parse_textgrid(path, target_tier):
    """
    Robust manual TextGrid parser.
    Extracts intervals from the specified tier ('words' or 'phones').
    Returns list of dicts: {'value': text, 'start': float, 'end': float, ...}
    """
    items = []
    if not os.path.exists(path):
        return items

    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        in_target_tier = False
        in_interval = False
        current_item = {}
        
        # Simple state machine
        for line in lines:
            line = line.strip()
            
            # check for tier start
            if line.startswith('name ='):
                if '=' in line:
                    name = line.split('=')[1].strip().strip('"')
                    if name == target_tier:
                        in_target_tier = True
                    # Only reset if we find another name= line (start of next tier)
                    # and we were already in target tier?
                    # Actually, if we are in target tier, and see name=, it means NEXT tier started.
                    elif in_target_tier:
                        in_target_tier = False
            
            if in_target_tier:
                if line.startswith('intervals ['):
                    in_interval = True
                    current_item = {}
                
                if in_interval:
                    if line.startswith('xmin ='):
                        try: current_item['start'] = float(line.split('=')[1].strip())
                        except: pass
                    elif line.startswith('xmax ='):
                        try: current_item['end'] = float(line.split('=')[1].strip())
                        except: pass
                    elif line.startswith('text ='):
                        text = line.split('=')[1].strip().strip('"')
                        # Only keep non-empty text
                        if text:
                            current_item['value'] = text
                            current_item['word'] = text # Alias for words
                            current_item['label'] = text # Alias for phones
                            if 'start' in current_item and 'end' in current_item:
                                items.append(current_item)
                        
                        in_interval = False # End of interval data
                        
    except Exception as e:
        print(f"[DEBUG] Failed to parse TextGrid {path}: {e}")
        
    return items

def read_textgrid_words(path):
    """Read words from TextGrid using manual parser."""
    return parse_textgrid(path, "words")

def read_textgrid_phones(path):
    """Read phones from TextGrid using manual parser."""
    return parse_textgrid(path, "phones")

def get_phones_for_word(word_info, all_phones):
    """Extract phones corresponding to a specific word time range."""
    w_start = word_info['start']
    w_end = word_info['end']
    word_phones = []
    for p in all_phones:
        if p['start'] >= w_start - 0.01 and p['end'] <= w_end + 0.01:
            word_phones.append(p['label'])
    return word_phones

# --- ASR Logic ---

def transcribe_audio(audio_path):
    """
    Use real ASR service via pte_core.
    """
    try:
        result = voice2text(audio_path)
        return result.get("text", "")
    except Exception as e:
        print(f"ASR failed: {e}")
        return ""

def compare_text(reference_text, transcription):
    """
    Compare reference text with transcription using difflib.
    Returns a list of word objects with status: 'correct', 'omitted', 'inserted', 'substituted'.
    Preserves punctuation marks (,.) for pause scoring.
    """
    def tokenize(text, preserve_pause_punct=True):
        if not preserve_pause_punct:
            return [w.strip(".,!?;:\"").lower() for w in text.split()]
        
        # Split by whitespace, then separate trailing pause punctuation
        tokens = []
        for word in text.split():
            clean_word = word.lower()
            # Check for any punctuation in our set at the end of the word
            found_punct = None
            word_part = clean_word
            
            # Simple check for trailing punctuation
            if clean_word and clean_word[-1] in PAUSE_PUNCTUATION:
                found_punct = clean_word[-1]
                word_part = clean_word[:-1]
            
            # Strip other non-pause punctuation
            word_part = word_part.strip("!?;:\"") # Clean leading/trailing
            word_part = re.sub(r"[^a-z0-9']+", "", word_part) # Only keep alphanumeric + apostrophe
            
            if word_part:
                tokens.append(word_part)
            if found_punct:
                tokens.append(found_punct)
        return [t for t in tokens if t]

    ref_words = tokenize(reference_text)
    trans_words = tokenize(transcription, preserve_pause_punct=False) # Transcriptions usually don't have punct
    
    matcher = difflib.SequenceMatcher(None, ref_words, trans_words)
    diff_results = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Words match
            for k, l in zip(range(i1, i2), range(j1, j2)):
                diff_results.append({
                    "word": ref_words[k],
                    "status": "correct",
                    "ref_index": k,
                    "trans_index": l
                })
        elif tag == 'replace':
            # Substitution (Mismatch)
            for k in range(i1, i2):
                diff_results.append({
                    "word": ref_words[k],
                    "status": "omitted",
                    "ref_index": k,
                    "trans_index": None
                })
            for l in range(j1, j2):
                diff_results.append({
                    "word": trans_words[l],
                    "status": "inserted",
                    "ref_index": None,
                    "trans_index": l
                })
        elif tag == 'delete':
            # Words in Ref but not in Trans (Omitted)
            for k in range(i1, i2):
                diff_results.append({
                    "word": ref_words[k],
                    "status": "omitted",
                    "ref_index": k,
                    "trans_index": None
                })
        elif tag == 'insert':
            # Words in Trans but not in Ref (Inserted)
            for l in range(j1, j2):
                diff_results.append({
                    "word": trans_words[l],
                    "status": "inserted",
                    "ref_index": None,
                    "trans_index": l
                })
                
    return diff_results, " ".join(trans_words)

def calculate_pauses(word_timestamps, threshold=0.5):
    """
    Calculate pauses between words.
    threshold: minimum duration in seconds to be considered a pause.
    """
    pauses = []
    for i in range(len(word_timestamps) - 1):
        current_word_end = word_timestamps[i]['end']
        next_word_start = word_timestamps[i+1]['start']
        duration = next_word_start - current_word_end
        if duration > threshold:
            pauses.append({
                "start": current_word_end,
                "end": next_word_start,
                "duration": round(duration, 2),
                "after_word": word_timestamps[i]['value']
            })
    return pauses

def transcribe_audio_with_details(audio_path):
    """
    Use real ASR service via pte_core.
    Returns full result dict with text and word_timestamps.
    """
    try:
        return voice2text(audio_path)
    except Exception as e:
        print(f"ASR failed: {e}")
        return {"text": "", "word_timestamps": []}

def run_single_alignment_gen(accent, conf, run_id, docker_input_dir):
    """
    Generator that runs MFA alignment and yields progress updates to keep connection alive.
    Yields: {"type": "progress", ...} or {"type": "result", "data": (accent, tg_path)}
    """
    import time
    output_dir_name = f"output_{accent}"
    docker_output_dir = f"/runtime/{run_id}/output/{accent}"
    host_output_dir = MFA_RUNTIME_DIR / run_id / "output" / accent
    
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{MFA_BASE_DIR}:/models",
        "-v", f"{MFA_RUNTIME_DIR}:/runtime",
        DOCKER_IMAGE,
        "mfa", "align",
        docker_input_dir,
        f"/models/{conf['dict_rel']}",
        f"/models/{conf['model_rel']}",
        docker_output_dir,
        "--clean", "--quiet",
        "--beam", "100",
        "--retry_beam", "400",
        "--num_jobs", "1"
    ]
    
    process = None
    try:
        # Use Popen to allow polling/heartbeats
        process = subprocess.Popen(
            cmd, 
            stdin=subprocess.DEVNULL,  # Prevent hanging on input requests
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        start_time = time.time()
        print(f"[MFA] Starting alignment for accent: {accent}, run_id: {run_id}")
        print(f"[MFA] Command: {' '.join(cmd)}")
        
        while True:
            try:
                # Wait for 2 seconds
                stdout, stderr = process.communicate(timeout=2)
                # If we get here without TimeoutExpired, process finished
                elapsed = int(time.time() - start_time)
                
                if process.returncode == 0:
                    print(f"[MFA] Alignment for {accent} completed successfully in {elapsed}s")
                    tg_file = host_output_dir / "input.TextGrid"
                    if tg_file.exists():
                        print(f"[MFA] TextGrid found at {tg_file}")
                        yield {"type": "result", "data": (accent, tg_file)}
                    else:
                        print(f"[MFA] ERROR: TextGrid not found at {tg_file}")
                        yield {"type": "result", "data": (accent, None)}
                else:
                    stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else 'No stderr'
                    print(f"[MFA] FAILED for {accent}: exit code {process.returncode}, elapsed: {elapsed}s")
                    print(f"[MFA] stderr: {stderr_text[:1000]}")
                    yield {"type": "result", "data": (accent, None)}
                break
                
            except subprocess.TimeoutExpired:
                # Still running - yield heartbeat
                elapsed = int(time.time() - start_time)
                
                # Increased timeout to 240 seconds (4 minutes)
                if elapsed > 240:
                    print(f"[MFA] TIMEOUT after {elapsed}s for {accent}, killing process")
                    process.kill()
                    yield {"type": "result", "data": (accent, None)}
                    break
                
                # Log progress every 30 seconds
                if elapsed % 30 == 0:
                    print(f"[MFA] Still running for {accent}: {elapsed}s elapsed")
                    
                yield {"type": "progress", "percent": 30 + int((elapsed/180)*40), "message": f"Aligning ({elapsed}s)..."}
                
    except Exception as e:
        print(f"[MFA] Exception during alignment for {accent}: {e}")
        import traceback
        traceback.print_exc()
        yield {"type": "result", "data": (accent, None)}
    finally:
        if process and process.poll() is None:
            print(f"[MFA] Cleaning up process for {accent}")
            process.kill()

def run_single_alignment(accent, conf, run_id, docker_input_dir):
    """Wrapper for backward compatibility (blocking)."""
    for msg in run_single_alignment_gen(accent, conf, run_id, docker_input_dir):
        if msg['type'] == 'result':
            return msg['data']
    return accent, None


def analyze_word_pronunciation(item, word_timestamps, audio_path, base_words, base_tg, builder, scorer, accent):
    """
    Helper function to analyze a single word's pronunciation (phonemes + stress).
    Designed to be run in parallel.
    Uses AccentTolerantScorer for nuanced scoring.
    """
    res_entry = item.copy()
    
    # PRIORITY 1: Use MFA phoneme-level timestamps (MAXIMUM PRECISION)
    # Get exact start of first phoneme and exact end of last phoneme
    s, e = None, None
    target_word = item['word'].lower()
    
    if base_words and base_tg:
        # Find the word in MFA alignment
        matched_word = None
        for bw in base_words:
            if bw['word'].lower() == target_word:
                matched_word = bw
                break
        
        if matched_word:
            # Get all phonemes from the TextGrid
            all_phones = read_textgrid_phones(base_tg)
            
            # Extract phonemes for this specific word
            word_phones = get_phones_for_word(matched_word, all_phones)
            
            # If we have phonemes, use FIRST phoneme start and LAST phoneme end
            if word_phones:
                # Find actual phoneme intervals within word boundaries
                w_start = matched_word['start']
                w_end = matched_word['end']
                
                phoneme_intervals = []
                for p in all_phones:
                    # Phoneme must be within word boundaries
                    if p['start'] >= w_start - 0.01 and p['end'] <= w_end + 0.01:
                        phoneme_intervals.append(p)
                
                if phoneme_intervals:
                    # PRECISE: First phoneme start, last phoneme end
                    s = phoneme_intervals[0]['start']
                    e = phoneme_intervals[-1]['end']
                else:
                    # Fallback to word boundaries if no phonemes found
                    s, e = w_start, w_end
            else:
                # No phonemes, use word boundaries
                s, e = matched_word['start'], matched_word['end']
    
    # PRIORITY 2: Fall back to ASR timestamps if MFA doesn't have this word
    if s is None:
        t_idx = item.get('trans_index')
        if t_idx is not None and t_idx < len(word_timestamps):
            s = word_timestamps[t_idx]['start']
            e = word_timestamps[t_idx]['end']
    
    # Assign timestamps if found
    if s is not None and e is not None:
        res_entry['start'] = round(s, 3)
        res_entry['end'] = round(e, 3)
        
        # 3. Inserted Words (e.g. fillers)
        if item['status'] == 'inserted':
            # Get observed phones only
            try:
                obs_ph = call_phoneme_service(audio_path, s, e)
                res_entry['observed_phones'] = " ".join(obs_ph)
            except Exception:
                res_entry['observed_phones'] = ""
            return res_entry

        # 4. Correct Words (Full Analysis)
        if item['status'] == 'correct':
            ref_word = item['word']
            
            # --- A. Phoneme Analysis (Accent Tolerant) ---
            word_score_obj = None
            try:
                # Get expected phonemes from CMUDict
                ref_ph = builder.word_to_phonemes(ref_word)
                
                # Get observed phonemes from MFA TextGrid (instead of wav2vec2)
                # If MFA succeeded, use MFA phones. If not, try wav2vec2 (fallback)
                obs_ph = []
                using_mfa_phones = False
                
                if base_tg:
                    all_mfa_phones = read_textgrid_phones(base_tg)
                    # Extract phonemes within this word's time boundaries
                    for p in all_mfa_phones:
                        # Phoneme must be within word boundaries (with small tolerance)
                        if p['start'] >= s - 0.01 and p['end'] <= e + 0.01:
                            # MFA uses ARPA symbols
                            obs_ph.append(p['label'])
                    
                    if obs_ph:
                        using_mfa_phones = True
                
                # Fallback to Wav2Vec2 if MFA didn't give phonemes for this word
                if not obs_ph:
                     obs_ph = call_phoneme_service(audio_path, s, e)
                
                if obs_ph:
                    # Score using AccentTolerantScorer
                    word_score_obj = scorer.score_word(ref_ph, obs_ph, accent)
                    
                    # Map to old structure for compatibility
                    # 'per' was 0.0 (good) to 1.0 (bad)
                    # new accuracy is 0-100 (good)
                    # so per = 1.0 - (accuracy / 100)
                    accuracy = word_score_obj['accuracy']
                    per_equivalent = 1.0 - (accuracy / 100.0)
                    
                    res_entry['per'] = round(per_equivalent, 3)
                    res_entry['phoneme_analysis'] = word_score_obj['alignment'] # List of (exp, spk, score)
                    res_entry['observed_phones'] = " ".join(obs_ph)
                    res_entry['expected_phones'] = " ".join(ref_ph)
                    
                    # Store new detailed score
                    res_entry['accuracy_score'] = accuracy
                else:
                    # No phonemes found - default to perfect score? Or fail?
                    # If word matched in ASR but no phones, assume OK
                    res_entry['per'] = 0.0
                    res_entry['accuracy_score'] = 100.0
                    
            except Exception as e:
                print(f"Phoneme analysis failed for {ref_word}: {e}")
                res_entry['per'] = 0.0  # Default to perfect on error
                res_entry['accuracy_score'] = 100.0

            # --- B. Stress Analysis (MFA + CMUDict) ---
            stress_score = 1.0
            try:
                # Find corresponding MFA word alignment for timings
                mfa_word_info = None
                for w in base_words:
                    overlap_start = max(s, w['start'])
                    overlap_end = min(e, w['end'])
                    overlap = max(0, overlap_end - overlap_start)
                    # 50% overlap rule
                    if overlap > 0.5 * (e - s):
                        mfa_word_info = w
                        break
                
                if mfa_word_info:
                    # Get MFA phone timings
                    all_mfa_phones = read_textgrid_phones(base_tg)
                    word_phones_with_times = []
                    for p in all_mfa_phones:
                        # Match phones within the word's time boundaries
                        if p['start'] >= mfa_word_info['start'] - 0.01 and p['end'] <= mfa_word_info['end'] + 0.01:
                            word_phones_with_times.append((p['label'], p['start'], p['end']))
                    
                    # Get Reference Stress Pattern & Calculate Score
                    stress_pattern = builder.get_stress_pattern(ref_word) if hasattr(builder, 'get_stress_pattern') else None
                    stress_details = get_syllable_stress_details(audio_path, s, e, word_phones_with_times, stress_pattern)
                    
                    stress_score = stress_details.get('score', 1.0)
                    res_entry['stress_details'] = stress_details
                    
                    # Store MFA timings for UI visualization
                    res_entry['mfa_timings'] = [
                            {'phone': p, 'start': round(ps, 3), 'end': round(pe, 3)} 
                            for p, ps, pe in word_phones_with_times
                    ]
            except Exception as e:
                print(f"Stress analysis failed for {ref_word}: {e}")
                
            res_entry['stress_score'] = round(stress_score, 3)


            # --- C. Combined Score ---
            # New scoring: use accuracy_score (0-100) directly if available
            accuracy_score = res_entry.get('accuracy_score', 100.0)
            
            # Weighted combination: 70% Phoneme Accuracy + 30% Stress
            # stress_score is 0.0-1.0, so multiply by 100
            combined_score_val = (0.7 * accuracy_score) + (0.3 * stress_score * 100)
            
            # Normalize to 0.0-1.0 for compatibility with rest of system (though UI might expect %)
            # The system seems to use 0.0-1.0 elsewhere for 'combined_score'
            # Let's keep combined_score as 0.0-1.0
            combined_score = combined_score_val / 100.0
            
            res_entry['combined_score'] = round(combined_score, 3)
            
            # Decision threshold (Relaxed from 0.65)
            if combined_score < 0.55:
                res_entry['status'] = 'mispronounced'
            
            return res_entry

    return res_entry

def align_and_validate_gen(audio_path, text_path, accents=None):
    """
    Generator version of align_and_validate for real-time progress updates.
    Yields: {"type": "progress", "percent": int, "message": str}
    Finally yields: {"type": "result", "data": dict}
    """
    # Use specified accents or default to US_ARPA only (optimization)
    if accents:
        target_accents = {a: ACCENTS_CONFIG[a] for a in accents if a in ACCENTS_CONFIG}
    else:
        # Default to US_ARPA only for performance
        target_accents = {"US_ARPA": ACCENTS_CONFIG["US_ARPA"]}
    
    # --- Step 1: ASR Transcription & Content Check ---
    yield {"type": "progress", "percent": 5, "message": "Analyzing audio..."}
    with open(text_path, 'r', encoding='utf-8') as f:
        reference_text = f.read().strip()
        
    yield {"type": "progress", "percent": 10, "message": "Analyzing audio..."}
    asr_result = transcribe_audio_with_details(audio_path)
    transcript = asr_result.get("text", "")
    word_timestamps = asr_result.get("word_timestamps", [])
    
    yield {"type": "progress", "percent": 15, "message": "Evaluating content..."}
    speech_rate_scale = calculate_speech_rate_scale(word_timestamps)
    
    # Identify pauses at punctuation marks
    pause_evaluations = []
    
    # Find word-to-word gaps first
    word_only_timestamps = [w for w in word_timestamps if w.get('value')]
    
    # Map reference punctuation to timestamps
    # This is a bit complex: we need to find which punctuation in diff_analysis
    # falls between which words in word_timestamps.
    
    # For now, let's use the simple gaps between transcribed words 
    # and map them back to punctuation in the reference.
    
    yield {"type": "progress", "percent": 20, "message": "Evaluating content..."}
    diff_analysis, transcript_clean = compare_text(reference_text, transcript)
    
    # Identify which words (indices) in the reference are "correct" content-wise.
    # We will only run pronunciation checks on these.
    valid_ref_indices = {item['ref_index'] for item in diff_analysis if item['status'] == 'correct'}
    
    # --- Step 2: MFA Alignment ---
    
    # Unique ID for this run
    run_id = str(uuid.uuid4())[:8]
    temp_dir_name = f"run_{run_id}"
    temp_host_dir = MFA_RUNTIME_DIR / run_id / "input"
    os.makedirs(temp_host_dir, exist_ok=True)
    
    try:
        yield {"type": "progress", "percent": 25, "message": "Checking pronunciation..."}
        # Copy inputs
        shutil.copy(audio_path, temp_host_dir / "input.wav")
        shutil.copy(text_path, temp_host_dir / "input.txt")
        
        # Docker paths
        docker_input_dir = f"/runtime/{run_id}/input"
        
        # Load Dictionaries (Local)
        dictionaries = {}
        for accent, conf in target_accents.items():
            dict_path = MFA_BASE_DIR / conf['dict_rel']
            dictionaries[accent] = load_dictionary(dict_path)
            
        # Run Alignment (Sequential implementation for reliability)
        accent_tgs = {} # accent -> path to TG
        
        # Run MFA alignment (60-90 seconds)
        print(f"[DEBUG] Running MFA for {list(target_accents.keys())}...")
        
        try:
             yield {"type": "progress", "percent": 30, "message": "Running MFA alignment (may take 60-90s)..."}
        except Exception as e:
             print(f"[DEBUG] Failed to yield progress: {e}")

        # Sequential Loop instead of ThreadPoolExecutor
        for accent, conf in target_accents.items():
            print(f"[DEBUG] Processing accent: {accent}")
            try:
                # Run alignment using generator to keep connection alive with heartbeats
                tg_file = None
                for msg in run_single_alignment_gen(accent, conf, run_id, docker_input_dir):
                    if msg['type'] == 'progress':
                        # Re-yield progress to keep client connection alive
                        try:
                            yield msg
                        except BaseException as e:
                            print(f"[DEBUG] Failed to yield heartbeat: {e}")
                            # If client disconnects here, we might want to stop MFA
                            if isinstance(e, GeneratorExit):
                                raise e
                    elif msg['type'] == 'result':
                        res_accent, tg_file = msg['data']
                
                print(f"[DEBUG] Validated run_single_alignment result: {accent}, {tg_file}")
                
                if tg_file:
                    accent_tgs[accent] = tg_file
            except Exception as e:
                print(f"[DEBUG] Error running alignment for {accent}: {e}")
                if isinstance(e, GeneratorExit):
                    raise e

                try:
                    print(f"[DEBUG] Yielding progress update...")
                    yield {"type": "progress", "percent": 80, "message": "Checking pronunciation..."}
                    print(f"[DEBUG] Yield success")
                except BaseException as e:
                     print(f"[DEBUG] CRITICAL: Failed to yield progress update: {e} ({type(e)})")
                     # Re-raise generator exit but log it first
                     if isinstance(e, GeneratorExit):
                         raise e

        print(f"[DEBUG] All MFA alignments done. accent_tgs: {list(accent_tgs.keys())}")
        
        # --- Step 3: Combine Results & Evaluate Pauses ---
        try:
             yield {"type": "progress", "percent": 90, "message": "Finalizing scores..."}
        except BaseException as e:
            print(f"[DEBUG] Failed to yield finalizing progress: {e}")
            pass
        
        # Use US_ARPA as anchor (or first available)
        if "US_ARPA" in accent_tgs:
            base_tg = accent_tgs["US_ARPA"]
        elif accent_tgs:
            base_tg = list(accent_tgs.values())[0]
        else:
            print(f"[DEBUG] MFA failed for all accents. Falling back to ASR results.")
            # If alignment fails completely (e.g. empty audio), fall back to just ASR results
            # Still provide useful word-level feedback based on ASR comparison
            correct_count = sum(1 for w in diff_analysis if w['status'] == 'correct' and not is_punctuation(w['word']))
            total_words = sum(1 for w in diff_analysis if not is_punctuation(w['word']))
            
            try:
                yield {"type": "result", "data": {
                    "words": diff_analysis,
                    "transcript": transcript,
                    "pauses": [],
                    "speech_rate_scale": round(speech_rate_scale, 2),
                    "raw_word_timestamps": word_timestamps,
                    "meta": {
                        "mfa_run_id": run_id,
                        "mfa_output_root": str(MFA_RUNTIME_DIR / run_id / "output"),
                        "mfa_output_dirs": {},
                    },
                    "summary": {
                        "total": total_words,
                        "correct": correct_count,
                        "pause_penalty": 0,
                        "pause_count": 0,
                        "asr_only": True,
                        "note": "Phoneme-level analysis unavailable. Showing ASR-based results."
                    }
                }}
            except BaseException as e:
                print(f"[DEBUG] Failed to yield ASR fallback result: {e}")
            return
            
        print(f"[DEBUG] Using base_tg: {base_tg}")
        base_words = read_textgrid_words(base_tg)

        print(f"[DEBUG] base_words count: {len(base_words)}")
        builder = PhonemeReferenceBuilder()
        
        # Initialize Scorer
        scorer = AccentTolerantScorer()
        
        # Determine accent to use for scoring
        # Use first accent from requested list, or fallback
        scoring_accent = "Non-Native English"
        if accents and len(accents) > 0:
            scoring_accent = accents[0]
            # Map simplified names back to full names if needed?
            # validator uses "Indian", "Nigerian" keys.
            # Scorer expects "Indian English", "Nigerian English".
            # Let's map them.
            accent_map = {
                "Indian": "Indian English",
                "Nigerian": "Nigerian English",
                "UK": "United Kingdom",
                "NonNative": "Non-Native English",
                "US_ARPA": "Non-Native English", # US usually default/standard
                "US_MFA": "Non-Native English"
            }
            scoring_accent = accent_map.get(scoring_accent, "Non-Native English")
            
        print(f"[DEBUG] Using scoring accent: {scoring_accent}")
        
        final_results_map = [None] * len(diff_analysis) # Preserve order
        pause_evals = []
        
        print(f"[DEBUG] Starting parallel word analysis for {len(diff_analysis)} items")
        # 3A. Parallel Word Analysis
        # Filter items that need analysis (correct or inserted)
        items_to_process = []
        for i, item in enumerate(diff_analysis):
            if is_punctuation(item['word']):
                # Handle punctuation/pauses separately in main thread
                continue
            if item['status'] in ('correct', 'inserted') or item.get('trans_index') is not None:
                 items_to_process.append((i, item))
            else:
                 # Omitted or others without trans_index, just copy
                 final_results_map[i] = item.copy()

        # Execute detailed analysis sequentially to avoid C++ input stream errors
        completed_count = 0
        total_items = len(items_to_process)
        
        # Use ThreadPoolExecutor with timeout for each word
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            for idx, item in items_to_process:
                try:
                    # Submit the task with a timeout
                    future = executor.submit(
                        analyze_word_pronunciation,
                        item, word_timestamps, audio_path, base_words, base_tg, builder, scorer, scoring_accent
                    )
                    # Wait up to 45 seconds for this word
                    res = future.result(timeout=45)
                    final_results_map[idx] = res
                except concurrent.futures.TimeoutError:
                    print(f"[WARNING] Word analysis timeout at index {idx} (word: {item.get('word')})")
                    # Keep the item with timestamps but skip detailed analysis
                    fallback = diff_analysis[idx].copy()
                    if 'start' in item and 'end' in item:
                        fallback['start'] = item['start']
                        fallback['end'] = item['end']
                    final_results_map[idx] = fallback
                except Exception as exc:
                    print(f"Word analysis exception at index {idx}: {exc}")
                    final_results_map[idx] = diff_analysis[idx].copy() # Fallback
                
                completed_count += 1
                # Update progress periodically
                if total_items > 0 and completed_count % max(1, total_items // 5) == 0:
                     prog = 60 + int(30 * (completed_count / total_items))
                     try:
                         yield {"type": "progress", "percent": prog, "message": f"Analyzed {completed_count}/{total_items} words..."}
                     except Exception:
                         pass

        # Send one update after completion
        yield {"type": "progress", "percent": 90, "message": "Analysis complete."}
        print(f"[DEBUG] Parallel word analysis complete. Completed: {completed_count}")
        # 3B. Pause Evaluation (Sequential, fast)
        yield {"type": "progress", "percent": 95, "message": "Evaluating pauses..."}
        
        # Fill in any missing items (pauses/punctuation)
        for i, item in enumerate(diff_analysis):
            if final_results_map[i] is None:
                final_results_map[i] = item.copy()
                
            res_entry = final_results_map[i]
            
            # If punctuation, evaluate pause
            if is_punctuation(item['word']):
                # Find valid previous and next words
                prev_word_idx = -1
                next_word_idx = -1
                prev_word_text = "START"
                
                # Check previous words in final_results_map
                for k in range(i-1, -1, -1):
                    prev_item = final_results_map[k]
                    if prev_item and prev_item.get('status') == 'correct' and not is_punctuation(prev_item['word']):
                        prev_word_idx = prev_item.get('trans_index')
                        if prev_word_idx is not None and prev_word_idx < len(word_timestamps):
                            prev_word_text = word_timestamps[prev_word_idx].get('word', '')
                        break
                
                # Check next words
                for k in range(i+1, len(diff_analysis)):
                    next_item = diff_analysis[k] # Use original analysis for lookahead mapping
                    if next_item['status'] == 'correct' and not is_punctuation(next_item['word']):
                        next_word_idx = next_item.get('trans_index', -1)
                        break
                
                pause_duration = None
                p_start = None
                p_end = None
                
                if prev_word_idx != -1 and next_word_idx != -1 and prev_word_idx < len(word_timestamps) and next_word_idx < len(word_timestamps):
                    p_start = word_timestamps[prev_word_idx]['end']
                    p_end = word_timestamps[next_word_idx]['start']
                    pause_duration = p_end - p_start
                
                p_eval = evaluate_pause(
                    punct=item['word'],
                    pause_duration=pause_duration,
                    prev_end=p_start,
                    next_start=p_end,
                    speech_rate_scale=speech_rate_scale,
                    prev_word=prev_word_text
                )
                p_eval['prev_word'] = prev_word_text
                p_eval['duration'] = round(pause_duration, 2) if pause_duration else 0.0
                pause_evals.append(p_eval)
                res_entry['pause_eval'] = p_eval
                res_entry['status'] = p_eval['status']

        print(f"[DEBUG] Pause evaluation complete. Generating final result...")
        final_results = [r for r in final_results_map if r is not None]
        print(f"[DEBUG] final_results count: {len(final_results)}")
        
        # Apply hesitation clustering to pauses
        pause_evals = apply_hesitation_clustering(pause_evals)
        total_pause_penalty = aggregate_pause_penalty(pause_evals)
        
        print(f"[DEBUG] Yielding final result...")
        
        # Read TextGrid content for debug visibility
        textgrid_content = ""
        try:
            if base_tg and os.path.exists(base_tg):
                with open(base_tg, 'r', encoding='utf-8') as f:
                    textgrid_content = f.read()
        except Exception as e:
            print(f"Failed to read TextGrid for debug: {e}")

        yield {"type": "result", "data": {
            "textgrid_content": textgrid_content,
            "words": final_results,
            "transcript": transcript,
            "pauses": pause_evals,
            "speech_rate_scale": round(speech_rate_scale, 2),
            "raw_word_timestamps": word_timestamps,
            "meta": {
                "mfa_run_id": run_id,
                "mfa_output_root": str(MFA_RUNTIME_DIR / run_id / "output"),
                "mfa_output_dirs": {
                    accent: str(path.parent) for accent, path in accent_tgs.items()
                },
            },
            "summary": {
                "total": len(final_results),
                "correct": sum(1 for w in final_results if w['status'] == 'correct'),
                "pause_penalty": round(total_pause_penalty, 3),
                "pause_count": len([p for p in pause_evals if p['status'] != 'correct_pause'])
            }
        }}

    except Exception as gen_err:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Generator failed: {gen_err}")
        # Yield an error so the client knows what happened instead of silent death
        yield {"type": "error", "message": f"Processing failed: {str(gen_err)}"}
        
    finally:
        # Cleanup temp dirs
        try:
            # shutil.rmtree(temp_host_dir)
            # Also cleanup output dirs
            for accent in target_accents:
                 output_dir_name = f"output_{accent}"
                 host_output_dir = MFA_RUNTIME_DIR / run_id / "output" / accent
                 # if host_output_dir.exists():
                 #     shutil.rmtree(host_output_dir)
        except Exception as e:
            print(f"Cleanup error: {e}")

# --- Alignment Workflow ---

def align_and_validate(audio_path, text_path, accents=None):
    """
    Synchronous version of align_and_validate_gen.
    """
    gen = align_and_validate_gen(audio_path, text_path, accents=accents)
    final_result = None
    for update in gen:
        if update['type'] == 'result':
            final_result = update['data']
    return final_result

# --- Helper Functions ---
