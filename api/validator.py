import os
import shutil
import subprocess
import json
import re
import uuid
import time
import sys
import difflib
from pathlib import Path

# Add project root to path to import pte_core
# Add project root to path to import pte_core
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pte_core.asr.pseudo_voice2text import voice2text_segment

# --- Configuration ---
# We assume the app runs from project root
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
    # "Nigerian": {
    #     "dict_rel": "eng_nigeria_model/english_nigeria_mfa.dict",
    #     "model_rel": "eng_nigeria_model/english_mfa.zip"
    # },
    # "US_ARPA": {
    #     "dict_rel": "eng_us_model/english_us_arpa.dict",
    #     "model_rel": "eng_us_model/english_us_arpa.zip"
    # },
    # "US_MFA": {
    #     "dict_rel": "eng_us_model_2/english_us_mfa.dict",
    #     "model_rel": "eng_us_model_2/english_mfa.zip"
    # },
    # "UK": {
    #     "dict_rel": "english_uk_model/english_uk_mfa.dict",
    #     "model_rel": "english_uk_model/english_mfa.zip"
    # }
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

ASR_SERVICE_URL = "http://localhost:8000/transcribe"
USE_MOCK_ASR = False  # Set to True for testing without Docker

def transcribe_audio(audio_path):
    """
    Transcribe audio using Whisper ASR from Docker service.
    Falls back to mock data if USE_MOCK_ASR is True or service is unavailable.
    """
    if USE_MOCK_ASR:
        # Fallback to mock data for testing
        segments = voice2text_segment()
        if segments:
            return segments[0]["value"]
        return ""
    
    try:
        import requests
        
        with open(audio_path, 'rb') as audio_file:
            files = {'audio': ('audio.wav', audio_file, 'audio/wav')}
            response = requests.post(ASR_SERVICE_URL, files=files, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('text', '').strip()
        else:
            print(f"ASR service error: {response.status_code} - {response.text}")
            # Fallback to mock
            segments = voice2text_segment()
            return segments[0]["value"] if segments else ""
            
    except requests.exceptions.ConnectionError:
        print("ASR service not available, using mock data")
        segments = voice2text_segment()
        return segments[0]["value"] if segments else ""
    except Exception as e:
        print(f"Transcription failed: {e}")
        segments = voice2text_segment()
        return segments[0]["value"] if segments else ""

def compare_text(reference_text, transcription):
    """
    Compare reference text with transcription using difflib.
    Returns a list of word objects with status: 'correct', 'omitted', 'inserted', 'substituted'.
    """
    # Tokenize (simple split for now, remove punctuation)
    def tokenize(text):
        return [w.strip(".,!?;:\"").lower() for w in text.split()]

    ref_words = tokenize(reference_text)
    trans_words = tokenize(transcription)
    
    matcher = difflib.SequenceMatcher(None, ref_words, trans_words)
    diff_results = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Words match
            for k in range(i1, i2):
                diff_results.append({
                    "word": ref_words[k],
                    "status": "correct",
                    "ref_index": k
                })
        elif tag == 'replace':
            # Substitution (Mismatch)
            for k in range(i1, i2):
                diff_results.append({
                    "word": ref_words[k],
                    "status": "omitted", # or "substituted"
                    "ref_index": k
                })
            for k in range(j1, j2):
                diff_results.append({
                    "word": trans_words[k],
                    "status": "inserted",
                    "ref_index": None
                })
        elif tag == 'delete':
            # Words in Ref but not in Trans (Omitted)
            for k in range(i1, i2):
                diff_results.append({
                    "word": ref_words[k],
                    "status": "omitted",
                    "ref_index": k
                })
        elif tag == 'insert':
            # Words in Trans but not in Ref (Inserted)
            for k in range(j1, j2):
                diff_results.append({
                    "word": trans_words[k],
                    "status": "inserted",
                    "ref_index": None
                })
                
    return diff_results, " ".join(trans_words)

# --- Alignment Workflow ---

# Global cache for dictionaries
CACHED_DICTIONARIES = {}

def get_dictionary(accent):
    """Get dictionary from cache or load it."""
    if accent in CACHED_DICTIONARIES:
        return CACHED_DICTIONARIES[accent]
    
    conf = ACCENTS_CONFIG.get(accent)
    if not conf:
        return {}
        
    dict_path = MFA_BASE_DIR / conf['dict_rel']
    print(f"Loading dictionary for {accent} from {dict_path}...")
    d = load_dictionary(dict_path)
    CACHED_DICTIONARIES[accent] = d
    return d

def align_and_validate(audio_path, text_path):
    """
    1. Transcribe with Pseudo-ASR to check content.
    2. Create a temp dir in PTE_MFA_TESTER_DOCKER/data
    3. Copy audio/text there.
    4. Run Docker alignment for all accents.
    5. Validate and return report combining ASR and MFA results.
    """
    
    # --- Step 1: ASR Transcription & Content Check ---
    with open(text_path, 'r', encoding='utf-8') as f:
        reference_text = f.read().strip()
        
    transcript = transcribe_audio(audio_path)
    diff_analysis, transcript_clean = compare_text(reference_text, transcript)
    
    # Identify which words (indices) in the reference are "correct" content-wise.
    # We will only run pronunciation checks on these.
    valid_ref_indices = {item['ref_index'] for item in diff_analysis if item['status'] == 'correct'}
    
    # --- Step 2: MFA Alignment (as before) ---
    
    # Unique ID for this run
    run_id = str(uuid.uuid4())[:8]
    temp_dir_name = f"run_{run_id}"
    temp_host_dir = MFA_BASE_DIR / "data" / temp_dir_name
    os.makedirs(temp_host_dir, exist_ok=True)
    
    try:
        # Copy inputs
        shutil.copy(audio_path, temp_host_dir / "input.wav")
        shutil.copy(text_path, temp_host_dir / "input.txt")
        
        # Docker paths
        docker_input_dir = f"/data/data/{temp_dir_name}"
        
        # Load Dictionaries (Cached)
        dictionaries = {}
        for accent in ACCENTS_CONFIG:
            dictionaries[accent] = get_dictionary(accent)
            
        # Run Alignment for each accent
        accent_tgs = {} # accent -> path to TG
        
        for accent, conf in ACCENTS_CONFIG.items():
            print(f"Aligning {accent}...")
            
            output_dir_name = f"output_{accent}_{run_id}"
            docker_output_dir = f"/data/data/{output_dir_name}"
            host_output_dir = MFA_BASE_DIR / "data" / output_dir_name
            
            # Docker Command
            # Note: Mounting MFA_BASE_DIR to /data
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
                subprocess.run(cmd, check=True, timeout=120) # 2 min timeout
                
                # Check output
                tg_file = host_output_dir / "input.TextGrid"
                if tg_file.exists():
                    accent_tgs[accent] = tg_file
            except subprocess.CalledProcessError as e:
                print(f"Alignment failed for {accent}: {e}")
            except Exception as e:
                print(f"Error running docker: {e}")
                
        # --- Step 3: Combine Results ---
        
        # Use US_MFA as anchor (or first available)
        if "US_MFA" in accent_tgs:
            base_tg = accent_tgs["US_MFA"]
        elif accent_tgs:
            base_tg = list(accent_tgs.values())[0]
        else:
            # If alignment fails completely (e.g. empty audio), fall back to just ASR results
             return {
                "words": diff_analysis,
                "transcript": transcript,
                "summary": {
                    "total": len(diff_analysis),
                    "correct": 0,
                    "asr_only": True
                }
            }
            
        base_words = read_textgrid_words(base_tg)
        
        # We need to map MFA results back to our diff_analysis
        # MFA base_words should roughly correspond to the reference text tokens
        # But diff_analysis has insertions mixed in.
        
        # Strategy:
        # 1. Iterate through diff_analysis.
        # 2. If status is 'correct', look up the word in MFA results (using ref_index).
        # 3. If MFA says it's mispronounced, update status to 'pronunciation_error'.
        
        final_results = []
        
        for item in diff_analysis:
            res_entry = item.copy()
            
            if item['status'] == 'correct' and item['ref_index'] is not None:
                # Check pronunciation
                idx = item['ref_index']
                
                # Sanity check: ensure MFA index exists
                if idx < len(base_words):
                    word_text = base_words[idx]['word']
                    
                    # Validate Pronunciation
                    is_pronounced_correctly = False
                    stress_ok = False
                    
                    for accent, tg_path in accent_tgs.items():
                        acc_words = read_textgrid_words(tg_path)
                        acc_phones = read_textgrid_phones(tg_path)
                        
                        if idx < len(acc_words):
                             observed = get_phones_for_word(acc_words[idx], acc_phones)
                             valid, msg, s_ok = validate_pronunciation(word_text, observed, dictionaries[accent])
                             if valid:
                                 is_pronounced_correctly = True
                                 if s_ok:
                                     stress_ok = True
                    
                    if is_pronounced_correctly:
                         res_entry['status'] = 'correct'
                         if not stress_ok:
                             res_entry['stress_error'] = True
                    else:
                         res_entry['status'] = 'mispronounced'
                else:
                    # If index out of bounds in MFA (rare), keep as correct or mark unknown
                    pass
            
            final_results.append(res_entry)
            
        return {
            "words": final_results,
            "transcript": transcript,
            "summary": {
                "total": len(final_results),
                "correct": sum(1 for w in final_results if w['status'] == 'correct')
            }
        }

    finally:
        # Cleanup temp dirs
        try:
            shutil.rmtree(temp_host_dir)
            # Also cleanup output dirs
            for accent in ACCENTS_CONFIG:
                 output_dir_name = f"output_{accent}_{run_id}"
                 host_output_dir = MFA_BASE_DIR / "data" / output_dir_name
                 if host_output_dir.exists():
                     shutil.rmtree(host_output_dir)
        except Exception as e:
            print(f"Cleanup error: {e}")
