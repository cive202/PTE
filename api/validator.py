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

# --- Configuration ---
# We assume the app runs from project root C:\Users\Acer\DataScience\PTE
MFA_BASE_DIR = PROJECT_ROOT / "PTE_MFA_TESTER_DOCKER"

# Docker Mount: Maps MFA_BASE_DIR (Host) -> /data (Container)
DOCKER_IMAGE = "mmcauliffe/montreal-forced-aligner:latest"

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
    }
}

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

def read_textgrid_words(path):
    """Minimal TextGrid reader for words using pte_core if available."""
    words = []
    if not os.path.exists(path):
        return words
    
    try:
        from pte_core.mfa.textgrid_reader import read_word_textgrid
        return read_word_textgrid(str(path))
    except ImportError:
        pass
        
    return [] # Fallback if pte_core not found

def read_textgrid_phones(path):
    """Read phones from TextGrid."""
    try:
        from pte_core.mfa.phone_reader import read_phone_textgrid
        return read_phone_textgrid(str(path))
    except ImportError:
        return []

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

def run_single_alignment(accent, conf, run_id, docker_input_dir):
    """Run MFA alignment for a single accent in Docker."""
    output_dir_name = f"output_{accent}_{run_id}"
    docker_output_dir = f"/data/data/{output_dir_name}"
    host_output_dir = MFA_BASE_DIR / "data" / output_dir_name
    
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{MFA_BASE_DIR}:/data",
        DOCKER_IMAGE,
        "mfa", "align",
        docker_input_dir,
        f"/data/{conf['dict_rel']}",
        f"/data/{conf['model_rel']}",
        docker_output_dir,
        "--clean", "--quiet"
    ]
    
    try:
        subprocess.run(cmd, check=True, timeout=300)
        tg_file = host_output_dir / "input.TextGrid"
        if tg_file.exists():
            return accent, tg_file
    except Exception as e:
        print(f"Alignment failed for {accent}: {e}")
    return accent, None

def analyze_word_pronunciation(item, word_timestamps, audio_path, base_words, base_tg, builder):
    """
    Helper function to analyze a single word's pronunciation (phonemes + stress).
    Designed to be run in parallel.
    """
    res_entry = item.copy()
    
    # 1. Start/End Times from Transcription
    t_idx = item.get('trans_index')
    if t_idx is not None and t_idx < len(word_timestamps):
        s = word_timestamps[t_idx]['start']
        e = word_timestamps[t_idx]['end']
        res_entry['start'] = round(s, 3)
        res_entry['end'] = round(e, 3)
        
        # 2. Inserted Words (e.g. fillers)
        if item['status'] == 'inserted':
            # Get observed phones only
            try:
                obs_ph = call_phoneme_service(audio_path, s, e)
                res_entry['observed_phones'] = " ".join(obs_ph)
            except Exception:
                res_entry['observed_phones'] = ""
            return res_entry

        # 3. Correct Words (Full Analysis)
        if item['status'] == 'correct':
            ref_word = item['word']
            
            # --- A. Phoneme Analysis (wav2vec2) ---
            try:
                ref_ph = builder.word_to_phonemes(ref_word)
                obs_ph = call_phoneme_service(audio_path, s, e)
                v = per(ref_ph, obs_ph)
                per_score = 1.0 - v # Accuracy
                
                res_entry['phoneme_analysis'] = analyze_phoneme_errors(ref_ph, obs_ph)
                res_entry['observed_phones'] = " ".join(obs_ph)
                res_entry['expected_phones'] = " ".join(ref_ph)
                res_entry['per'] = round(v, 3)
            except Exception as e:
                print(f"Phoneme analysis failed for {ref_word}: {e}")
                per_score = 0.0
                res_entry['per'] = 1.0

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
            combined_score = (0.7 * per_score) + (0.3 * stress_score)
            res_entry['combined_score'] = round(combined_score, 3)
            
            # Decision threshold
            if combined_score < 0.65:
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
    temp_host_dir = MFA_BASE_DIR / "data" / temp_dir_name
    os.makedirs(temp_host_dir, exist_ok=True)
    
    try:
        yield {"type": "progress", "percent": 25, "message": "Checking pronunciation..."}
        # Copy inputs
        shutil.copy(audio_path, temp_host_dir / "input.wav")
        shutil.copy(text_path, temp_host_dir / "input.txt")
        
        # Docker paths
        docker_input_dir = f"/data/data/{temp_dir_name}"
        
        # Load Dictionaries (Local)
        dictionaries = {}
        for accent, conf in target_accents.items():
            dict_path = MFA_BASE_DIR / conf['dict_rel']
            dictionaries[accent] = load_dictionary(dict_path)
            
        # Run Alignment for each accent in parallel
        accent_tgs = {} # accent -> path to TG
        
        yield {"type": "progress", "percent": 30, "message": "Checking pronunciation..."}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(target_accents)) as executor:
            future_to_accent = {
                executor.submit(run_single_alignment, accent, conf, run_id, docker_input_dir): accent 
                for accent, conf in target_accents.items()
            }
            
            for future in concurrent.futures.as_completed(future_to_accent):
                accent, tg_file = future.result()
                if tg_file:
                    accent_tgs[accent] = tg_file
                yield {"type": "progress", "percent": 80, "message": "Checking pronunciation..."}
                
        # --- Step 3: Combine Results & Evaluate Pauses ---
        yield {"type": "progress", "percent": 90, "message": "Finalizing scores..."}
        
        # Use US_ARPA as anchor (or first available)
        if "US_ARPA" in accent_tgs:
            base_tg = accent_tgs["US_ARPA"]
        elif accent_tgs:
            base_tg = list(accent_tgs.values())[0]
        else:
            # If alignment fails completely (e.g. empty audio), fall back to just ASR results
            yield {"type": "result", "data": {
                "words": diff_analysis,
                "transcript": transcript,
                "summary": {
                    "total": len(diff_analysis),
                    "correct": 0,
                    "asr_only": True
                }
            }}
            return
            
        base_words = read_textgrid_words(base_tg)
        builder = PhonemeReferenceBuilder()
        
        final_results_map = [None] * len(diff_analysis) # Preserve order
        pause_evals = []
        
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

        # Execute detailed analysis in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_idx = {
                executor.submit(
                    analyze_word_pronunciation, 
                    item, word_timestamps, audio_path, base_words, base_tg, builder
                ): idx 
                for idx, item in items_to_process
            }
            
            completed_count = 0
            total_items = len(items_to_process)
            
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    res = future.result()
                    final_results_map[idx] = res
                except Exception as exc:
                    print(f"Word analysis exception at index {idx}: {exc}")
                    final_results_map[idx] = diff_analysis[idx].copy() # Fallback
                
                completed_count += 1
                # Update progress more frequently
                if total_items > 0 and completed_count % 5 == 0:
                     prog = 60 + int(30 * (completed_count / total_items))
                     yield {"type": "progress", "percent": prog, "message": f"Analyzed {completed_count}/{total_items} words..."}

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

        final_results = [r for r in final_results_map if r is not None]
        
        # Apply hesitation clustering to pauses
        pause_evals = apply_hesitation_clustering(pause_evals)
        total_pause_penalty = aggregate_pause_penalty(pause_evals)
        
        yield {"type": "result", "data": {
            "words": final_results,
            "transcript": transcript,
            "pauses": pause_evals,
            "speech_rate_scale": round(speech_rate_scale, 2),
            "raw_word_timestamps": word_timestamps,
            "summary": {
                "total": len(final_results),
                "correct": sum(1 for w in final_results if w['status'] == 'correct'),
                "pause_penalty": round(total_pause_penalty, 3),
                "pause_count": len([p for p in pause_evals if p['status'] != 'correct_pause'])
            }
        }}

    finally:
        # Cleanup temp dirs
        try:
            shutil.rmtree(temp_host_dir)
            # Also cleanup output dirs
            for accent in target_accents:
                 output_dir_name = f"output_{accent}_{run_id}"
                 host_output_dir = MFA_BASE_DIR / "data" / output_dir_name
                 if host_output_dir.exists():
                     shutil.rmtree(host_output_dir)
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
