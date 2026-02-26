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
import hashlib
from pathlib import Path
from typing import Optional

# Add project root to path to import pte_core
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # /home/sushil/developer/pte/PTE
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pte_core.asr.voice2text import voice2text
from pte_core.pause.pause_evaluator import evaluate_pause
from pte_core.pause.hesitation import apply_hesitation_clustering, aggregate_pause_penalty
from pte_core.pause.speech_rate import calculate_speech_rate_scale
from read_aloud.alignment.normalizer import PAUSE_PUNCTUATION, is_punctuation
from pte_core.asr.phoneme_recognition import call_phoneme_service
from pte_core.scoring.pronunciation import per, label_from_per, analyze_phoneme_errors
from pte_core.scoring.stress import get_syllable_stress_score, get_syllable_stress_details
from pte_core.scoring.accent_scorer import AccentTolerantScorer
from src.shared.paths import (
    PROJECT_ROOT as SHARED_PROJECT_ROOT,
    MFA_BASE_DIR as SHARED_MFA_BASE_DIR,
    MFA_RUNTIME_DIR as SHARED_MFA_RUNTIME_DIR,
    ensure_runtime_dirs,
)
from src.shared.services import MFA_DOCKER_IMAGE

# --- Configuration ---
MFA_BASE_DIR = SHARED_MFA_BASE_DIR
MFA_RUNTIME_DIR = SHARED_MFA_RUNTIME_DIR
PROJECT_ROOT = SHARED_PROJECT_ROOT
ensure_runtime_dirs()

# Optional mount-source overrides for the Docker daemon host.
# Needed when this API runs inside a container and shells out to `docker run`.
MFA_DOCKER_MOUNT_BASE_DIR = os.environ.get("PTE_MFA_DOCKER_MOUNT_BASE_DIR")
MFA_DOCKER_MOUNT_RUNTIME_DIR = os.environ.get("PTE_MFA_DOCKER_MOUNT_RUNTIME_DIR")
HOST_PROJECT_ROOT = os.environ.get("PTE_HOST_PROJECT_ROOT")

# Docker Mount:
# - MFA_BASE_DIR (Host) -> /models (Container)
# - MFA_RUNTIME_DIR (Host) -> /runtime (Container)
DOCKER_IMAGE = MFA_DOCKER_IMAGE
CACHE_SCHEMA_VERSION = "read_aloud_cache_v2"
CACHE_PIPELINE_VERSION = "phase2_v1"


def _safe_int_env(value: Optional[str], default: int, minimum: int = 1, maximum: Optional[int] = None) -> int:
    """Parse integer env vars with bounds and fallback."""
    try:
        parsed = int(str(value).strip())
    except Exception:
        return default
    if parsed < minimum:
        parsed = minimum
    if maximum is not None and parsed > maximum:
        parsed = maximum
    return parsed


def _resolve_docker_mount_source(local_path: Path, explicit_mount_path: Optional[str]) -> str:
    """
    Resolve bind-mount source path for docker daemon.

    Priority:
    1) explicit env override (PTE_MFA_DOCKER_MOUNT_*), if provided
    2) map local project-relative path onto PTE_HOST_PROJECT_ROOT, if provided
    3) local path as-is (works when API runs on host directly)
    """
    if explicit_mount_path:
        return explicit_mount_path

    if HOST_PROJECT_ROOT:
        try:
            relative = local_path.resolve().relative_to(PROJECT_ROOT.resolve())
            mapped = Path(HOST_PROJECT_ROOT) / relative
            return str(mapped)
        except Exception:
            pass

    return str(local_path)


def _as_bool_env(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_docker_ready() -> tuple[bool, str]:
    """Check whether Docker CLI + daemon are ready for MFA runs."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False, "Docker CLI is not installed."
    try:
        result = subprocess.run(
            [docker_bin, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
        if result.returncode == 0:
            return True, ""
        return False, "Docker daemon is unavailable."
    except Exception as exc:
        return False, f"Docker check failed: {exc}"


def _resolve_mfa_num_jobs() -> int:
    """Resolve MFA --num_jobs from env or CPU heuristic (safe default: 2-4 on multi-core)."""
    override = os.environ.get("PTE_MFA_NUM_JOBS")
    if override and override.strip():
        return _safe_int_env(override, default=1, minimum=1, maximum=16)

    cpu_count = os.cpu_count() or 1
    if cpu_count <= 2:
        return 1
    return min(4, max(2, cpu_count // 2))


def _resolve_word_analysis_workers() -> int:
    """
    Resolve workers for word analysis.
    Default stays single-worker for reliability; users can opt in via env.
    """
    raw = str(os.environ.get("PTE_WORD_ANALYSIS_WORKERS", "")).strip().lower()
    if not raw:
        return 1
    if raw == "auto":
        cpu_count = os.cpu_count() or 1
        return min(4, max(1, cpu_count // 2))
    return _safe_int_env(raw, default=1, minimum=1, maximum=8)


def _resolve_mfa_runner_mode() -> tuple[str, Optional[str]]:
    """
    Return MFA runner mode.
    - docker_run: fresh container per request (current default)
    - docker_exec: execute inside persistent running container
    """
    container_name = str(os.environ.get("PTE_MFA_CONTAINER_NAME", "")).strip()
    if container_name:
        return "docker_exec", container_name
    return "docker_run", None


def _result_cache_enabled() -> bool:
    return _as_bool_env(os.environ.get("PTE_READ_ALOUD_CACHE_ENABLED", "1"))


def _result_cache_max_age_seconds() -> int:
    # Default 7 days
    return _safe_int_env(os.environ.get("PTE_READ_ALOUD_CACHE_MAX_AGE_SECONDS"), default=604800, minimum=0)


def _result_cache_dir() -> Path:
    cache_dir = MFA_RUNTIME_DIR / "result_cache" / "read_aloud"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _sha256_file(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _path_signature(path: Path) -> str:
    """Stable file signature used in cache keys."""
    try:
        st = path.stat()
        return f"{st.st_size}:{int(st.st_mtime)}"
    except Exception:
        return "missing"


def _build_result_cache_key(audio_path: str, reference_text: str, accent_keys: list[str]) -> str:
    model_signatures = {}
    for accent in accent_keys:
        conf = ACCENTS_CONFIG.get(accent) or {}
        dict_path = MFA_BASE_DIR / conf.get("dict_rel", "")
        model_path = MFA_BASE_DIR / conf.get("model_rel", "")
        model_signatures[accent] = {
            "dict_rel": conf.get("dict_rel"),
            "dict_sig": _path_signature(dict_path) if conf.get("dict_rel") else "missing",
            "model_rel": conf.get("model_rel"),
            "model_sig": _path_signature(model_path) if conf.get("model_rel") else "missing",
        }

    payload = {
        "schema": CACHE_SCHEMA_VERSION,
        "pipeline": CACHE_PIPELINE_VERSION,
        "audio_sha256": _sha256_file(audio_path),
        "reference_text": reference_text.strip(),
        "accents": accent_keys,
        "docker_image": DOCKER_IMAGE,
        "models": model_signatures,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_cached_result(cache_key: str) -> Optional[dict]:
    cache_file = _result_cache_dir() / f"{cache_key}.json"
    if not cache_file.exists():
        return None

    max_age = _result_cache_max_age_seconds()
    if max_age > 0:
        age = time.time() - cache_file.stat().st_mtime
        if age > max_age:
            return None

    try:
        with open(cache_file, "r", encoding="utf-8") as in_file:
            payload = json.load(in_file)
    except Exception as exc:
        print(f"[CACHE] Failed to read cache file {cache_file}: {exc}")
        return None

    if payload.get("schema") != CACHE_SCHEMA_VERSION:
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    return result


def _store_cached_result(cache_key: str, result: dict) -> None:
    cache_dir = _result_cache_dir()
    cache_file = cache_dir / f"{cache_key}.json"
    temp_file = cache_dir / f"{cache_key}.tmp"

    payload = {
        "schema": CACHE_SCHEMA_VERSION,
        "pipeline": CACHE_PIPELINE_VERSION,
        "created_at": int(time.time()),
        "result": result,
    }
    with open(temp_file, "w", encoding="utf-8") as out_file:
        json.dump(payload, out_file, ensure_ascii=False)
    os.replace(temp_file, cache_file)


MFA_DOCKER_BASE_SOURCE = _resolve_docker_mount_source(MFA_BASE_DIR, MFA_DOCKER_MOUNT_BASE_DIR)
MFA_DOCKER_RUNTIME_SOURCE = _resolve_docker_mount_source(MFA_RUNTIME_DIR, MFA_DOCKER_MOUNT_RUNTIME_DIR)

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


def get_phone_intervals_for_word(word_info, all_phones, tolerance=0.01):
    """Return phone intervals that fall inside a word's MFA time range."""
    if not word_info:
        return []
    w_start = word_info.get('start')
    w_end = word_info.get('end')
    if w_start is None or w_end is None:
        return []
    intervals = []
    for p in all_phones:
        p_start = p.get('start')
        p_end = p.get('end')
        if p_start is None or p_end is None:
            continue
        if p_start >= w_start - tolerance and p_end <= w_end + tolerance:
            intervals.append(p)
    return intervals


def _normalize_word_key(word):
    return re.sub(r"[^a-z0-9']+", "", str(word or "").lower())


def build_ref_word_to_mfa_map(diff_analysis, base_words):
    """
    Map each reference-token occurrence in diff_analysis to the corresponding MFA word.

    This avoids "first lexical match wins" bugs for repeated words.
    """
    occurrences = {}
    for bw in base_words:
        key = _normalize_word_key(bw.get('word'))
        if key:
            occurrences.setdefault(key, []).append(bw)

    seen_counts = {}
    mapped = {}
    for idx, item in enumerate(diff_analysis):
        if is_punctuation(item.get('word', '')):
            continue
        if item.get('ref_index') is None:
            continue
        key = _normalize_word_key(item.get('word'))
        if not key:
            continue
        words = occurrences.get(key, [])
        used = seen_counts.get(key, 0)
        if used < len(words):
            mapped[idx] = words[used]
            seen_counts[key] = used + 1
    return mapped

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


def build_asr_only_result(
    diff_analysis,
    transcript,
    speech_rate_scale,
    word_timestamps,
    run_id,
    note,
    mfa_runner_mode=None,
    mfa_num_jobs=None,
    cache_key=None,
):
    """Build a consistent ASR-only fallback payload."""
    correct_count = sum(1 for w in diff_analysis if w['status'] == 'correct' and not is_punctuation(w['word']))
    total_words = sum(1 for w in diff_analysis if not is_punctuation(w['word']))
    return {
        "words": diff_analysis,
        "transcript": transcript,
        "pauses": [],
        "speech_rate_scale": round(speech_rate_scale, 2),
        "raw_word_timestamps": word_timestamps,
        "meta": {
            "mfa_run_id": run_id,
            "mfa_output_root": str(MFA_RUNTIME_DIR / run_id / "output"),
            "mfa_output_dirs": {},
            "mfa_runner_mode": mfa_runner_mode,
            "mfa_num_jobs": mfa_num_jobs,
            "cache": {
                "hit": False,
                "key": cache_key,
                "schema": CACHE_SCHEMA_VERSION,
                "pipeline": CACHE_PIPELINE_VERSION,
            },
        },
        "summary": {
            "total": total_words,
            "correct": correct_count,
            "pause_penalty": 0,
            "pause_count": 0,
            "asr_only": True,
            "note": note,
            "cached": False,
        },
    }

def run_single_alignment_gen(accent, conf, run_id, docker_input_dir, error_sink=None):
    """
    Generator that runs MFA alignment and yields progress updates to keep connection alive.
    Yields: {"type": "progress", ...} or {"type": "result", "data": (accent, tg_path)}
    """
    import time
    docker_output_dir = f"/runtime/{run_id}/output/{accent}"
    host_output_dir = MFA_RUNTIME_DIR / run_id / "output" / accent
    mfa_num_jobs = _resolve_mfa_num_jobs()
    runner_mode, persistent_container = _resolve_mfa_runner_mode()
    align_args = [
        "mfa", "align",
        docker_input_dir,
        f"/models/{conf['dict_rel']}",
        f"/models/{conf['model_rel']}",
        docker_output_dir,
        "--clean", "--quiet",
        "--beam", "100",
        "--retry_beam", "400",
        "--num_jobs", str(mfa_num_jobs),
    ]
    if runner_mode == "docker_exec" and persistent_container:
        cmd = ["docker", "exec", persistent_container] + align_args
    else:
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{MFA_DOCKER_BASE_SOURCE}:/models",
            "-v", f"{MFA_DOCKER_RUNTIME_SOURCE}:/runtime",
            DOCKER_IMAGE,
        ] + align_args
    
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
        print(f"[MFA] Runner: {runner_mode}, num_jobs={mfa_num_jobs}")
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
                    try:
                        host_output_dir.mkdir(parents=True, exist_ok=True)
                        (host_output_dir / "mfa_stderr.log").write_text(stderr_text, encoding="utf-8")
                    except Exception:
                        pass
                    if isinstance(error_sink, dict):
                        error_sink[accent] = stderr_text[:1000]
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
        if isinstance(error_sink, dict):
            error_sink[accent] = str(e)
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


def analyze_word_pronunciation(
    item,
    word_timestamps,
    audio_path,
    matched_word,
    all_mfa_phones,
    builder,
    scorer,
    accent,
):
    """
    Analyze a single word pronunciation using cached MFA structures when available.
    """
    res_entry = item.copy()

    # PRIORITY 1: Use occurrence-aware MFA word match
    s, e = None, None
    word_phone_intervals = []

    if matched_word:
        word_phone_intervals = get_phone_intervals_for_word(matched_word, all_mfa_phones)
        if word_phone_intervals:
            s = word_phone_intervals[0]['start']
            e = word_phone_intervals[-1]['end']
        else:
            s = matched_word.get('start')
            e = matched_word.get('end')

    # PRIORITY 2: Fall back to ASR timestamps
    if s is None:
        t_idx = item.get('trans_index')
        if t_idx is not None and t_idx < len(word_timestamps):
            s = word_timestamps[t_idx].get('start')
            e = word_timestamps[t_idx].get('end')

    if s is not None and e is not None:
        res_entry['start'] = round(s, 3)
        res_entry['end'] = round(e, 3)

        # Inserted word: only collect observed phones
        if item['status'] == 'inserted':
            try:
                obs_ph = call_phoneme_service(audio_path, s, e)
                res_entry['observed_phones'] = " ".join(obs_ph)
            except Exception:
                res_entry['observed_phones'] = ""
            return res_entry

        # Correct word: full analysis
        if item['status'] == 'correct':
            ref_word = item['word']
            fallback_accuracy = 60.0  # Neutral fallback: not perfect, not auto-fail

            # --- A. Phoneme Analysis ---
            try:
                ref_ph = builder.word_to_phonemes(ref_word)
                obs_ph = [p.get('label', '') for p in word_phone_intervals if p.get('label')]

                if not obs_ph:
                    obs_ph = call_phoneme_service(audio_path, s, e)

                res_entry['expected_phones'] = " ".join(ref_ph)

                if obs_ph:
                    word_score_obj = scorer.score_word(ref_ph, obs_ph, accent)
                    accuracy = float(word_score_obj.get('accuracy', fallback_accuracy))
                    per_equivalent = 1.0 - (accuracy / 100.0)

                    res_entry['per'] = round(per_equivalent, 3)
                    res_entry['phoneme_analysis'] = word_score_obj.get('alignment', [])
                    res_entry['observed_phones'] = " ".join(obs_ph)
                    res_entry['accuracy_score'] = accuracy
                else:
                    res_entry['per'] = round(1.0 - (fallback_accuracy / 100.0), 3)
                    res_entry['accuracy_score'] = fallback_accuracy
                    res_entry['analysis_confidence'] = "low"
                    res_entry['analysis_note'] = "No phonemes detected for this segment."

            except Exception as e:
                print(f"Phoneme analysis failed for {ref_word}: {e}")
                res_entry['per'] = round(1.0 - (fallback_accuracy / 100.0), 3)
                res_entry['accuracy_score'] = fallback_accuracy
                res_entry['analysis_confidence'] = "low"
                res_entry['analysis_note'] = "Phoneme analysis unavailable due to processing error."

            # --- B. Stress Analysis ---
            stress_score = 0.5  # Neutral default instead of perfect
            try:
                if word_phone_intervals:
                    word_phones_with_times = [
                        (p.get('label', ''), p.get('start'), p.get('end'))
                        for p in word_phone_intervals
                        if p.get('start') is not None and p.get('end') is not None
                    ]
                    stress_pattern = (
                        builder.get_stress_pattern(ref_word)
                        if hasattr(builder, 'get_stress_pattern')
                        else None
                    )
                    stress_details = get_syllable_stress_details(
                        audio_path,
                        s,
                        e,
                        word_phones_with_times,
                        stress_pattern,
                    )
                    stress_score = float(stress_details.get('score', stress_score))
                    res_entry['stress_details'] = stress_details
                    res_entry['mfa_timings'] = [
                        {'phone': p, 'start': round(ps, 3), 'end': round(pe, 3)}
                        for p, ps, pe in word_phones_with_times
                    ]
                else:
                    res_entry['stress_details'] = {
                        "score": stress_score,
                        "syllables": [],
                        "ref_pattern": builder.get_stress_pattern(ref_word) if hasattr(builder, 'get_stress_pattern') else None,
                        "match_info": "Insufficient phone evidence for stress analysis.",
                    }
            except Exception as e:
                print(f"Stress analysis failed for {ref_word}: {e}")

            res_entry['stress_score'] = round(stress_score, 3)

            # --- C. Combined Score ---
            accuracy_score = float(res_entry.get('accuracy_score', fallback_accuracy))
            combined_score_val = (0.7 * accuracy_score) + (0.3 * stress_score * 100)
            combined_score = combined_score_val / 100.0
            res_entry['combined_score'] = round(combined_score, 3)

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
    if not target_accents:
        target_accents = {"US_ARPA": ACCENTS_CONFIG["US_ARPA"]}
    accent_keys = list(target_accents.keys())
    
    # --- Step 1: ASR Transcription & Content Check ---
    yield {"type": "progress", "percent": 5, "message": "Analyzing audio..."}
    with open(text_path, 'r', encoding='utf-8') as f:
        reference_text = f.read().strip()

    cache_key = None
    if _result_cache_enabled():
        try:
            cache_key = _build_result_cache_key(audio_path, reference_text, accent_keys)
            cached_result = _load_cached_result(cache_key)
            if cached_result:
                cached_meta = cached_result.setdefault("meta", {})
                cached_meta["cache"] = {
                    "hit": True,
                    "key": cache_key,
                    "schema": CACHE_SCHEMA_VERSION,
                    "pipeline": CACHE_PIPELINE_VERSION,
                }
                cached_summary = cached_result.setdefault("summary", {})
                cached_summary["cached"] = True
                yield {"type": "progress", "percent": 12, "message": "Loaded cached analysis."}
                yield {"type": "result", "data": cached_result}
                return
        except Exception as exc:
            print(f"[CACHE] Cache lookup failed: {exc}")

    yield {"type": "progress", "percent": 10, "message": "Analyzing audio..."}
    asr_result = transcribe_audio_with_details(audio_path)
    transcript = asr_result.get("text", "")
    word_timestamps = asr_result.get("word_timestamps", [])
    
    yield {"type": "progress", "percent": 15, "message": "Evaluating content..."}
    speech_rate_scale = calculate_speech_rate_scale(word_timestamps)
    
    yield {"type": "progress", "percent": 20, "message": "Evaluating content..."}
    diff_analysis, _ = compare_text(reference_text, transcript)
    
    # --- Step 2: MFA Alignment ---
    
    # Unique ID for this run
    run_id = str(uuid.uuid4())[:8]
    mfa_num_jobs = _resolve_mfa_num_jobs()
    mfa_runner_mode, _ = _resolve_mfa_runner_mode()
    mfa_disabled = _as_bool_env(os.environ.get("PTE_SKIP_MFA"))
    docker_ready, docker_reason = _is_docker_ready()
    using_builtin_mfa_runner = getattr(run_single_alignment_gen, "__module__", "") == __name__
    if mfa_disabled or (using_builtin_mfa_runner and not docker_ready):
        reason = "MFA disabled by PTE_SKIP_MFA." if mfa_disabled else docker_reason
        print(f"[DEBUG] Skipping MFA: {reason}")
        yield {"type": "progress", "percent": 30, "message": "MFA unavailable; using ASR fallback."}
        yield {
            "type": "result",
            "data": build_asr_only_result(
                diff_analysis,
                transcript,
                speech_rate_scale,
                word_timestamps,
                run_id,
                f"Phoneme-level analysis unavailable: {reason}",
                mfa_runner_mode=mfa_runner_mode,
                mfa_num_jobs=mfa_num_jobs,
                cache_key=cache_key,
            ),
        }
        return

    run_host_dir = MFA_RUNTIME_DIR / run_id
    temp_host_dir = run_host_dir / "input"
    output_host_dir = run_host_dir / "output"
    os.makedirs(temp_host_dir, exist_ok=True)
    os.makedirs(output_host_dir, exist_ok=True)
    # MFA docker image can run as a non-root user; keep runtime dirs writable.
    for path_obj in (run_host_dir, temp_host_dir, output_host_dir):
        try:
            os.chmod(path_obj, 0o777)
        except Exception:
            pass
    
    try:
        yield {"type": "progress", "percent": 25, "message": "Checking pronunciation..."}
        # Copy inputs
        shutil.copy(audio_path, temp_host_dir / "input.wav")
        shutil.copy(text_path, temp_host_dir / "input.txt")
        
        # Docker paths
        docker_input_dir = f"/runtime/{run_id}/input"
        
        # Run Alignment (Sequential implementation for reliability)
        accent_tgs = {} # accent -> path to TG
        mfa_errors = {} # accent -> summarized stderr/exception
        
        # Run MFA alignment (60-90 seconds)
        print(
            f"[DEBUG] Running MFA for {list(target_accents.keys())} "
            f"(runner={mfa_runner_mode}, num_jobs={mfa_num_jobs})..."
        )
        
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
                try:
                    alignment_iter = run_single_alignment_gen(
                        accent,
                        conf,
                        run_id,
                        docker_input_dir,
                        error_sink=mfa_errors,
                    )
                except TypeError:
                    # Backward-compatible path for tests/mocks with the legacy signature.
                    alignment_iter = run_single_alignment_gen(accent, conf, run_id, docker_input_dir)

                for msg in alignment_iter:
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
            error_context = ""
            if mfa_errors:
                first_accent = sorted(mfa_errors.keys())[0]
                first_error = str(mfa_errors.get(first_accent, "")).strip()
                if first_error:
                    error_context = (
                        f" MFA stderr ({first_accent}): {first_error[:280]} "
                        f"(see {MFA_RUNTIME_DIR / run_id / 'output' / first_accent / 'mfa_stderr.log'})."
                    )
            try:
                yield {
                    "type": "result",
                    "data": build_asr_only_result(
                        diff_analysis,
                        transcript,
                        speech_rate_scale,
                        word_timestamps,
                        run_id,
                        "Phoneme-level analysis unavailable. Showing ASR-based results." + error_context,
                        mfa_runner_mode=mfa_runner_mode,
                        mfa_num_jobs=mfa_num_jobs,
                        cache_key=cache_key,
                    ),
                }
            except BaseException as e:
                print(f"[DEBUG] Failed to yield ASR fallback result: {e}")
            return
            
        print(f"[DEBUG] Using base_tg: {base_tg}")
        base_words = read_textgrid_words(base_tg)
        all_mfa_phones = read_textgrid_phones(base_tg)
        ref_to_mfa_map = build_ref_word_to_mfa_map(diff_analysis, base_words)

        print(f"[DEBUG] base_words count: {len(base_words)}")
        print(f"[DEBUG] base phones count: {len(all_mfa_phones)}")
        # Lazy import to keep API startup fast (G2P can trigger NLTK downloads).
        from pte_core.phoneme.g2p import PhonemeReferenceBuilder
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
        
        analysis_workers = _resolve_word_analysis_workers()
        word_timeout_seconds = _safe_int_env(
            os.environ.get("PTE_WORD_ANALYSIS_TIMEOUT_SECONDS"),
            default=45,
            minimum=5,
            maximum=120,
        )
        print(
            f"[DEBUG] Starting word analysis for {len(diff_analysis)} items "
            f"(workers={analysis_workers}, timeout={word_timeout_seconds}s)"
        )
        # 3A. Word Analysis
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

        def _word_fallback(idx, item):
            fallback = diff_analysis[idx].copy()
            if 'start' in item and 'end' in item:
                fallback['start'] = item['start']
                fallback['end'] = item['end']
            return fallback

        completed_count = 0
        total_items = len(items_to_process)

        if analysis_workers <= 1 or total_items <= 1:
            # Default path: explicit sequential execution for thread-unsafe analyzers.
            for idx, item in items_to_process:
                try:
                    final_results_map[idx] = analyze_word_pronunciation(
                        item,
                        word_timestamps,
                        audio_path,
                        ref_to_mfa_map.get(idx),
                        all_mfa_phones,
                        builder,
                        scorer,
                        scoring_accent,
                    )
                except Exception as exc:
                    print(f"Word analysis exception at index {idx}: {exc}")
                    final_results_map[idx] = _word_fallback(idx, item)

                completed_count += 1
                if total_items > 0 and completed_count % max(1, total_items // 5) == 0:
                    prog = 60 + int(30 * (completed_count / total_items))
                    try:
                        yield {"type": "progress", "percent": prog, "message": f"Analyzed {completed_count}/{total_items} words..."}
                    except Exception:
                        pass
        else:
            # Optional opt-in: threaded execution for faster analysis on stable environments.
            effective_workers = min(analysis_workers, total_items)
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers)
            futures = []
            had_timeout = False
            try:
                for idx, item in items_to_process:
                    future = executor.submit(
                        analyze_word_pronunciation,
                        item,
                        word_timestamps,
                        audio_path,
                        ref_to_mfa_map.get(idx),
                        all_mfa_phones,
                        builder,
                        scorer,
                        scoring_accent,
                    )
                    futures.append((idx, item, future))

                for idx, item, future in futures:
                    try:
                        final_results_map[idx] = future.result(timeout=word_timeout_seconds)
                    except concurrent.futures.TimeoutError:
                        had_timeout = True
                        future.cancel()
                        print(f"[WARNING] Word analysis timeout at index {idx} (word: {item.get('word')})")
                        final_results_map[idx] = _word_fallback(idx, item)
                    except Exception as exc:
                        print(f"Word analysis exception at index {idx}: {exc}")
                        final_results_map[idx] = _word_fallback(idx, item)

                    completed_count += 1
                    if total_items > 0 and completed_count % max(1, total_items // 5) == 0:
                        prog = 60 + int(30 * (completed_count / total_items))
                        try:
                            yield {"type": "progress", "percent": prog, "message": f"Analyzed {completed_count}/{total_items} words..."}
                        except Exception:
                            pass
            finally:
                executor.shutdown(wait=not had_timeout, cancel_futures=had_timeout)

        # Send one update after completion
        yield {"type": "progress", "percent": 90, "message": "Analysis complete."}
        print(f"[DEBUG] Word analysis complete. Completed: {completed_count}")
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
                prev_word_idx = None
                next_word_idx = None
                prev_word_text = "START"
                
                # Check previous words in final_results_map
                for k in range(i-1, -1, -1):
                    prev_item = final_results_map[k]
                    if prev_item and not is_punctuation(prev_item['word']):
                        prev_word_idx = prev_item.get('trans_index')
                        if prev_word_idx is not None and 0 <= prev_word_idx < len(word_timestamps):
                            prev_word_text = (
                                word_timestamps[prev_word_idx].get('value')
                                or word_timestamps[prev_word_idx].get('word')
                                or ""
                            )
                            break
                
                # Check next words
                for k in range(i+1, len(diff_analysis)):
                    next_item = final_results_map[k]
                    if next_item and not is_punctuation(next_item['word']):
                        candidate_idx = next_item.get('trans_index')
                        if candidate_idx is not None and 0 <= candidate_idx < len(word_timestamps):
                            next_word_idx = candidate_idx
                            break
                
                pause_duration = None
                p_start = None
                p_end = None
                
                if (
                    prev_word_idx is not None
                    and next_word_idx is not None
                    and prev_word_idx < len(word_timestamps)
                    and next_word_idx < len(word_timestamps)
                ):
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

        result_payload = {
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
                "mfa_runner_mode": mfa_runner_mode,
                "mfa_num_jobs": mfa_num_jobs,
                "cache": {
                    "hit": False,
                    "key": cache_key,
                    "schema": CACHE_SCHEMA_VERSION,
                    "pipeline": CACHE_PIPELINE_VERSION,
                },
            },
            "summary": {
                "total": len(final_results),
                "correct": sum(1 for w in final_results if w['status'] == 'correct'),
                "pause_penalty": round(total_pause_penalty, 3),
                "pause_count": len([p for p in pause_evals if p['status'] != 'correct_pause']),
                "cached": False,
            }
        }

        if cache_key and _result_cache_enabled():
            try:
                _store_cached_result(cache_key, result_payload)
            except Exception as exc:
                print(f"[CACHE] Failed to store result cache: {exc}")

        yield {"type": "result", "data": result_payload}

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
            for _accent in target_accents:
                # host_output_dir = MFA_RUNTIME_DIR / run_id / "output" / _accent
                # if host_output_dir.exists():
                #     shutil.rmtree(host_output_dir)
                pass
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
