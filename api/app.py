import os
import sys
import datetime
import subprocess
import json
import re
import threading
import uuid
import shutil
import requests
import random
from pathlib import Path
from urllib.parse import urlencode
from flask import Flask, render_template, request, jsonify, Response, send_from_directory

# Ensure project root is in path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.validator import align_and_validate, align_and_validate_gen
from api.image_evaluator import get_random_image, get_image_catalog, infer_chart_type, evaluate_description
from api.lecture_evaluator import (
    get_random_lecture,
    get_lecture_by_id,
    get_lecture_categories,
    get_lecture_catalog,
    evaluate_lecture,
)
from api.writing_evaluator import (
    get_swt_task,
    get_essay_task,
    get_email_task,
    get_writing_topics,
    get_writing_difficulties,
    get_writing_catalog,
    evaluate_summarize_written_text,
    evaluate_write_essay,
    evaluate_write_email,
)
from pte_core.asr.phoneme_recognition import call_phoneme_service
from pte_core.scoring.accent_scorer import AccentTolerantScorer
from api.file_utils import (
    get_paired_paths,
    get_temp_filepath,
    FEATURE_READ_ALOUD,
    FEATURE_REPEAT_SENTENCE,
    FEATURE_DESCRIBE_IMAGE,
    FEATURE_RETELL_LECTURE
)
from api.tts_handler import (
    synthesize_speech,
    get_tts_capabilities,
    list_voices,
    normalize_provider,
    normalize_speed_token,
    get_default_voice,
)
from src.shared.paths import (
    IMAGES_DIR as SHARED_IMAGES_DIR,
    LECTURES_DIR as SHARED_LECTURES_DIR,
    REPEAT_SENTENCE_AUDIO_DIR as SHARED_REPEAT_SENTENCE_AUDIO_DIR,
    READ_ALOUD_REFERENCE_FILE,
    REPEAT_SENTENCE_REFERENCE_FILE,
    ensure_runtime_dirs,
    USER_UPLOADS_DIR,
)
from src.shared.services import GRAMMAR_SERVICE_URL

app = Flask(__name__)
IMAGES_DIR = os.fspath(SHARED_IMAGES_DIR)
LECTURES_DIR = os.fspath(SHARED_LECTURES_DIR)
REPEAT_SENTENCE_AUDIO_DIR = os.fspath(SHARED_REPEAT_SENTENCE_AUDIO_DIR)
REPEAT_SENTENCE_JSON = os.fspath(REPEAT_SENTENCE_REFERENCE_FILE)
READ_ALOUD_JSON = os.fspath(READ_ALOUD_REFERENCE_FILE)
ensure_runtime_dirs()

# ============================================================================
# JOB QUEUE SYSTEM
# ============================================================================
JOB_STORE = {}  # {job_id: {status, result, error, audio_path, text_path}}
IMAGE_JOB_STORE = {}  # {job_id: {status, result, error, image_id, audio_path}}
LECTURE_JOB_STORE = {}  # {job_id: {status, result, error, lecture_id, audio_path}}
KEEP_UPLOAD_ARTIFACTS = os.environ.get("PTE_KEEP_UPLOAD_ARTIFACTS", "1").lower() not in {"0", "false", "no"}
WORD_PRACTICE_ACCENT_MAP = {
    "Indian": "Indian English",
    "Nigerian": "Nigerian English",
    "UK": "United Kingdom",
    "NonNative": "Non-Native English",
    "US_ARPA": "Non-Native English",
    "US_MFA": "Non-Native English",
}
_WORD_PRACTICE_BUILDER = None
_WORD_PRACTICE_SCORER = None


def _get_word_practice_builder():
    global _WORD_PRACTICE_BUILDER
    if _WORD_PRACTICE_BUILDER is None:
        # Lazy import to avoid slow NLTK/G2P downloads during Flask startup.
        from pte_core.phoneme.g2p import PhonemeReferenceBuilder
        _WORD_PRACTICE_BUILDER = PhonemeReferenceBuilder()
    return _WORD_PRACTICE_BUILDER


def _get_word_practice_scorer():
    global _WORD_PRACTICE_SCORER
    if _WORD_PRACTICE_SCORER is None:
        _WORD_PRACTICE_SCORER = AccentTolerantScorer()
    return _WORD_PRACTICE_SCORER


def _map_word_practice_accent(raw_accent):
    return WORD_PRACTICE_ACCENT_MAP.get(raw_accent, "Non-Native English")


def _as_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_tts_request(feature: str = "default"):
    capabilities = get_tts_capabilities(feature=feature)
    default_provider = str(capabilities.get("default_provider", "edge"))
    default_speed = str(capabilities.get("default_speed", "x1.0"))
    default_voice = str(capabilities.get("default_voice", get_default_voice(feature=feature)))

    provider = request.args.get("provider", default_provider)
    speed = request.args.get("speed", default_speed)
    voice = request.args.get("voice", default_voice)
    rate = request.args.get("rate")
    pitch = request.args.get("pitch")

    resolved_provider = normalize_provider(provider)
    resolved_speed = normalize_speed_token(speed)
    resolved_voice = str(voice or default_voice).strip()
    resolved_rate = str(rate or "").strip() or None
    resolved_pitch = str(pitch or "").strip() or None
    return {
        "provider": resolved_provider,
        "speed": resolved_speed,
        "voice": resolved_voice,
        "rate": resolved_rate,
        "pitch": resolved_pitch,
    }


def _build_retell_audio_url(lecture_id: str, tts_params: dict) -> str:
    query = {
        "provider": tts_params.get("provider", "edge"),
        "speed": tts_params.get("speed", "x1.0"),
        "voice": tts_params.get("voice", ""),
    }
    if tts_params.get("rate"):
        query["rate"] = tts_params["rate"]
    if tts_params.get("pitch"):
        query["pitch"] = tts_params["pitch"]
    encoded = urlencode(query)
    return f"/retell-lecture/audio/{lecture_id}?{encoded}"


def _maybe_cleanup(paths, force=False):
    if KEEP_UPLOAD_ARTIFACTS and not force:
        return
    for candidate in paths:
        try:
            if candidate and os.path.exists(candidate):
                os.remove(candidate)
        except Exception:
            pass


def _persist_attempt_payload(audio_path, payload, filename):
    if not isinstance(payload, dict):
        return
    try:
        attempt_dir = Path(audio_path).resolve().parent
        analysis_dir = attempt_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        target = analysis_dir / filename
        with open(target, "w", encoding="utf-8") as out_file:
            json.dump(payload, out_file, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _persist_attempt_artifacts(audio_path, analysis_payload, filename="analysis_result.json"):
    if not isinstance(analysis_payload, dict):
        return

    _persist_attempt_payload(audio_path, analysis_payload, filename)

    try:
        attempt_dir = Path(audio_path).resolve().parent
        words = analysis_payload.get("words", [])
        if isinstance(words, list):
            phoneme_rows = []
            for row in words:
                if isinstance(row, dict) and (
                    row.get("observed_phones")
                    or row.get("phoneme_analysis")
                    or row.get("expected_phones")
                ):
                    phoneme_rows.append(row)
            if phoneme_rows:
                _persist_attempt_payload(
                    audio_path,
                    {"count": len(phoneme_rows), "words": phoneme_rows},
                    "phoneme_data.json",
                )

        textgrid_content = analysis_payload.get("textgrid_content")
        if textgrid_content:
            mfa_dir = attempt_dir / "mfa"
            mfa_dir.mkdir(parents=True, exist_ok=True)
            (mfa_dir / "input.TextGrid").write_text(textgrid_content, encoding="utf-8")

        meta = analysis_payload.get("meta")
        if isinstance(meta, dict):
            source_root = meta.get("mfa_output_root")
            if source_root:
                source_path = Path(source_root)
                if source_path.exists() and source_path.is_dir():
                    target_root = attempt_dir / "mfa"
                    target_root.mkdir(parents=True, exist_ok=True)
                    for accent_dir in source_path.iterdir():
                        if not accent_dir.is_dir():
                            continue
                        destination = target_root / accent_dir.name
                        if destination.exists():
                            shutil.rmtree(destination)
                        shutil.copytree(accent_dir, destination)
    except Exception:
        pass


def _persist_writing_result(task_slug, payload):
    if not isinstance(payload, dict):
        return
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        short_id = str(uuid.uuid4())[:6]
        safe_slug = re.sub(r"[^a-z0-9_]+", "_", str(task_slug).lower()).strip("_") or "writing"
        attempt_dir = Path(USER_UPLOADS_DIR) / f"{safe_slug}_{timestamp}_{short_id}"
        analysis_dir = attempt_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        target = analysis_dir / "writing_result.json"
        with open(target, "w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, ensure_ascii=False, indent=2)
    except Exception:
        pass

def run_mfa_job(job_id, audio_path, text_path):
    """Background worker for MFA alignment using the main engine."""
    try:
        JOB_STORE[job_id]['status'] = 'processing'
        
        # Get accent from job store
        accent = JOB_STORE[job_id].get('accent', 'US_ARPA')
        
        # Use the main engine from validator.py
        result = align_and_validate(audio_path, text_path, accents=[accent])
        _persist_attempt_artifacts(audio_path, result, filename="check_result.json")
        
        JOB_STORE[job_id]['status'] = 'complete'
        JOB_STORE[job_id]['result'] = result
    except Exception as e:
        import traceback
        traceback.print_exc()
        JOB_STORE[job_id]['status'] = 'failed'
        JOB_STORE[job_id]['error'] = str(e)
    finally:
        _maybe_cleanup([audio_path, text_path])

def run_image_evaluation_job(job_id, image_id, audio_path):
    """Background worker for image description evaluation with MFA phone analysis."""
    try:
        IMAGE_JOB_STORE[job_id]['status'] = 'processing'
        
        # Transcribe audio using the main engine's ASR
        from pte_core.asr.voice2text import voice2text
        asr_result = voice2text(audio_path)
        transcription = asr_result.get('text', '').strip()
        word_timestamps = asr_result.get('word_timestamps', [])
        
        # Create temporary text file for MFA alignment
        temp_text_path = audio_path.replace('.wav', '_transcript.txt')
        with open(temp_text_path, 'w', encoding='utf-8') as f:
            f.write(transcription)
        
        # Run MFA alignment to get phone-level data
        from api.validator import align_and_validate
        accent = IMAGE_JOB_STORE[job_id].get('accent', 'US_ARPA')
        mfa_result = align_and_validate(audio_path, temp_text_path, accents=[accent])
        _persist_attempt_artifacts(audio_path, mfa_result, filename="image_mfa_result.json")
        
        # Evaluate description (pass MFA words so pronunciation score is computed)
        mfa_words = mfa_result.get('words', []) if mfa_result else []
        result = evaluate_description(image_id, transcription, mfa_words=mfa_words)
        
        # Include enhanced transcription details for UI overlay
        result['transcription_details'] = {
            'text': transcription,
            'words': mfa_words,
            'mfa_summary': mfa_result.get('summary', {}) if mfa_result else {}
        }
        
        IMAGE_JOB_STORE[job_id]['status'] = 'complete'
        IMAGE_JOB_STORE[job_id]['result'] = result
        _persist_attempt_payload(audio_path, result, "image_evaluation_result.json")
    except Exception as e:
        import traceback
        traceback.print_exc()
        IMAGE_JOB_STORE[job_id]['status'] = 'failed'
        IMAGE_JOB_STORE[job_id]['error'] = str(e)
    finally:
        _maybe_cleanup([audio_path, temp_text_path if 'temp_text_path' in locals() else None])

def run_lecture_evaluation_job(job_id, lecture_id, audio_path):
    """Background worker for lecture evaluation with MFA phone analysis."""
    try:
        LECTURE_JOB_STORE[job_id]['status'] = 'processing'
        
        # Transcribe audio using the main engine's ASR
        from pte_core.asr.voice2text import voice2text
        asr_result = voice2text(audio_path)
        transcription = asr_result.get('text', '').strip()
        word_timestamps = asr_result.get('word_timestamps', [])
        
        # Create temporary text file for MFA alignment
        temp_text_path = audio_path.replace('.wav', '_transcript.txt')
        with open(temp_text_path, 'w', encoding='utf-8') as f:
            f.write(transcription)
        
        # Run MFA alignment to get phone-level data
        from api.validator import align_and_validate
        accent = LECTURE_JOB_STORE[job_id].get('accent', 'US_ARPA')
        mfa_result = align_and_validate(audio_path, temp_text_path, accents=[accent])
        _persist_attempt_artifacts(audio_path, mfa_result, filename="lecture_mfa_result.json")
        
        # Evaluate summary
        result = evaluate_lecture(lecture_id, transcription)
        
        # Use MFA words directly (they already contain timing and status)
        mfa_words = mfa_result.get('words', []) if mfa_result else []
        
        # Include enhanced transcription details for UI overlay
        result['transcription_details'] = {
            'text': transcription,
            'words': mfa_words,
            'mfa_summary': mfa_result.get('summary', {}) if mfa_result else {}
        }
        
        LECTURE_JOB_STORE[job_id]['status'] = 'complete'
        LECTURE_JOB_STORE[job_id]['result'] = result
        _persist_attempt_payload(audio_path, result, "lecture_evaluation_result.json")
    except Exception as e:
        import traceback
        traceback.print_exc()
        LECTURE_JOB_STORE[job_id]['status'] = 'failed'
        LECTURE_JOB_STORE[job_id]['error'] = str(e)
    finally:
        _maybe_cleanup([audio_path, temp_text_path if 'temp_text_path' in locals() else None])

# ============================================================================
# UTILITY
# ============================================================================
def convert_to_wav(input_path, output_path):
    """Convert audio to 16kHz mono WAV using ffmpeg."""
    try:
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-ac', '1',
            '-ar', '16000',
            output_path
        ]
        # Added timeout to prevent hanging and capture stderr for debugging
        result = subprocess.run(
            cmd, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            timeout=10
        )
        return True
    except subprocess.TimeoutExpired:
        print(f"Conversion timed out for {input_path}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Conversion failed: {e}")
        # Print stderr if available
        if e.stderr:
            print(f"FFmpeg Error: {e.stderr.decode('utf-8', errors='ignore')}")
        return False
    except Exception as e:
        print(f"Conversion error: {e}")
        return False

# ============================================================================
# ROUTES - MAIN DASHBOARD
# ============================================================================
@app.route('/')
def dashboard():
    """Main dashboard showing all available tasks."""
    return render_template('dashboard.html')

# ============================================================================
# ROUTES - GRAMMAR PROXY
# ============================================================================
@app.route('/api/grammar', methods=['POST'])
def check_grammar():
    """Proxy request to Docker Grammar Service."""
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "No text provided"}), 400
            
        response = requests.post(GRAMMAR_SERVICE_URL, json=data, timeout=10)
        return (response.text, response.status_code, response.headers.items())
    except Exception as e:
        return jsonify({"error": f"Grammar service unreachable: {str(e)}"}), 503

@app.route('/api/tts/options', methods=['GET'])
def tts_options():
    feature = request.args.get("feature", "default")
    locale = request.args.get("locale")
    force_refresh = _as_bool(request.args.get("refresh"))

    capabilities = get_tts_capabilities(feature=feature)
    provider = request.args.get("provider", capabilities.get("default_provider", "edge"))
    try:
        provider = normalize_provider(provider)
    except ValueError:
        provider = str(capabilities.get("default_provider", "edge"))

    requested_locale = locale or capabilities.get("default_locale")
    voices = list_voices(
        provider=provider,
        locale=requested_locale,
        feature=feature,
        force_refresh=force_refresh,
    )
    return jsonify(
        {
            "feature": feature,
            "provider": provider,
            "capabilities": capabilities,
            "voices": voices,
            "voice_count": len(voices),
        }
    )


@app.route('/api/tts/voices', methods=['GET'])
def tts_voices():
    feature = request.args.get("feature", "default")
    capabilities = get_tts_capabilities(feature=feature)
    provider = request.args.get("provider", capabilities.get("default_provider", "edge"))
    locale = request.args.get("locale")
    force_refresh = _as_bool(request.args.get("refresh"))

    try:
        provider = normalize_provider(provider)
        voices = list_voices(
            provider=provider,
            locale=locale,
            feature=feature,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Voice listing failed: {exc}"}), 500

    return jsonify(
        {
            "feature": feature,
            "provider": provider,
            "locale": locale,
            "voices": voices,
            "voice_count": len(voices),
        }
    )


@app.route('/api/tts', methods=['GET'])
def tts():
    text = request.args.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    feature = request.args.get("feature", "default")
    try:
        tts_params = _resolve_tts_request(feature=feature)
        audio_bytes = synthesize_speech(
            text,
            speed=tts_params["speed"],
            voice=tts_params["voice"],
            provider=tts_params["provider"],
            rate=tts_params["rate"],
            pitch=tts_params["pitch"] or "+0Hz",
            feature=feature,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    response = Response(audio_bytes, mimetype='audio/mpeg')
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response

@app.route('/api/word-practice', methods=['POST'])
def word_practice():
    """
    Fast single-word pronunciation check using phoneme service only (no MFA).
    """
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    raw_word = request.form.get('word', '')
    accent = request.form.get('accent', 'US_ARPA')
    clean_word = re.sub(r"[^a-zA-Z']+", "", raw_word).lower()
    if not clean_word:
        return jsonify({"error": "No valid word provided"}), 400

    uploaded = request.files['audio']
    temp_input = get_temp_filepath('word_practice', 'webm')
    temp_wav = get_temp_filepath('word_practice', 'wav')
    processing_path = temp_wav

    try:
        uploaded.save(temp_input)
        if not convert_to_wav(temp_input, temp_wav):
            processing_path = temp_input

        builder = _get_word_practice_builder()
        scorer = _get_word_practice_scorer()
        expected_phones = builder.word_to_phonemes(clean_word)
        observed_phones = call_phoneme_service(processing_path)

        if not observed_phones:
            return jsonify({
                "error": "Could not detect phonemes from this recording. Please try again with clearer pronunciation."
            }), 422

        scoring_accent = _map_word_practice_accent(accent)
        score_obj = scorer.score_word(expected_phones, observed_phones, scoring_accent)
        accuracy = float(score_obj.get('accuracy', 0.0))
        if accuracy >= 75:
            status = "correct"
        elif accuracy >= 55:
            status = "acceptable"
        else:
            status = "mispronounced"

        alignment = []
        for exp, obs, score in score_obj.get('alignment', []):
            alignment.append({
                "expected": exp,
                "observed": obs,
                "score": round(float(score), 2)
            })

        return jsonify({
            "word": clean_word,
            "accent": scoring_accent,
            "status": status,
            "accuracy": round(accuracy, 1),
            "expected_phones": " ".join(expected_phones),
            "observed_phones": " ".join(observed_phones),
            "alignment": alignment,
            "method": "phoneme_service_only"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        _maybe_cleanup([temp_input, temp_wav], force=True)

# ============================================================================
# ROUTES - SPEAKING TASKS
# ============================================================================
@app.route('/speaking/read-aloud')
def read_aloud():
    """Read Aloud practice page."""
    return render_template('index.html')

@app.route('/speaking/read-aloud/get-topics')
def get_read_aloud_topics():
    """Get all available topics for read aloud."""
    try:
        if not os.path.exists(READ_ALOUD_JSON):
            return jsonify({"error": "Data file not found"}), 404

        with open(READ_ALOUD_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        passages = data.get('passages', [])
        if not passages:
            return jsonify({"error": "No data available"}), 404
        
        # Extract unique topics
        topics = list(set(p.get('topic', 'General') for p in passages))
        
        return jsonify({"topics": topics})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/speaking/read-aloud/get-passage')
def get_read_aloud_passage():
    """Get a passage by topic or random."""
    try:
        topic = request.args.get('topic', None)
        
        if not os.path.exists(READ_ALOUD_JSON):
            return jsonify({"error": "Data file not found"}), 404

        with open(READ_ALOUD_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        passages = data.get('passages', [])
        if not passages:
            return jsonify({"error": "No data available"}), 404
        
        # Filter by topic if provided
        if topic:
            filtered = [p for p in passages if p.get('topic', 'General') == topic]
            if not filtered:
                return jsonify({"error": f"No passages found for topic: {topic}"}), 404
            entry = random.choice(filtered)
        else:
            entry = random.choice(passages)
        
        return jsonify({
            "text": entry['text'],
            "id": entry['id'],
            "topic": entry.get('topic', 'General'),
            "title": entry.get('title', '')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/speaking/repeat-sentence')
def repeat_sentence():
    """Repeat Sentence practice page."""
    return render_template('repeat_sentence.html')

@app.route('/speaking/repeat-sentence/get-topics')
def get_repeat_sentence_topics():
    """Get all available topics for repeat sentence."""
    try:
        if not os.path.exists(REPEAT_SENTENCE_JSON):
            return jsonify({"error": "Data file not found"}), 404

        with open(REPEAT_SENTENCE_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        sentences = data.get('sentences', [])
        if not sentences:
            return jsonify({"error": "No data available"}), 404
        
        # Extract unique topics
        topics = list(set(s.get('topic', 'General') for s in sentences))
        
        return jsonify({"topics": topics})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/speaking/repeat-sentence/get-task')
def get_repeat_sentence_task():
    try:
        topic = request.args.get('topic', None)
        
        if not os.path.exists(REPEAT_SENTENCE_JSON):
             return jsonify({"error": "Data file not found"}), 404

        with open(REPEAT_SENTENCE_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        sentences = data.get('sentences', [])
        if not sentences:
            return jsonify({"error": "No data available"}), 404
        
        # Filter by topic if provided
        if topic:
            filtered = [s for s in sentences if s.get('topic', 'General') == topic]
            if not filtered:
                return jsonify({"error": f"No sentences found for topic: {topic}"}), 404
            entry = random.choice(filtered)
        else:
            entry = random.choice(sentences)
        
        return jsonify({
            "text": entry['text'],
            "id": entry['id'],
            "topic": entry.get('topic', 'General'),
            "audio_url": f"/audio/repeat-sentence/{entry['audio']}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/audio/repeat-sentence/<path:filename>')
def serve_repeat_sentence_audio(filename):
    return send_from_directory(REPEAT_SENTENCE_AUDIO_DIR, filename)

@app.route('/speaking/describe-image')
def describe_image_speaking():
    """Describe Image practice page."""
    return render_template('describe_image.html')

@app.route('/speaking/retell-lecture')
def retell_lecture_page():
    """Retell Lecture practice page."""
    return render_template('retell_lecture.html')

@app.route('/speaking/summarize-group-discussion')
def summarize_group_discussion_page():
    """Summarize Group Discussion page (soon available)."""
    return render_template('summarize_group_discussion.html')

@app.route('/writing/summarize-written-text')
def summarize_written_text_page():
    """Summarize Written Text page."""
    return render_template('summarize_written_text.html')

@app.route('/writing/write-essay')
def write_essay_page():
    """Write Essay page."""
    return render_template('write_essay.html')


@app.route('/writing/write-email')
def write_email_page():
    """Write Email page."""
    return render_template('write_email.html')


@app.route('/writing/summarize-written-text/get-topics', methods=['GET'])
def get_swt_topics():
    topics = get_writing_topics("summarize_written_text")
    if not topics:
        return jsonify({"error": "No topics available"}), 404
    return jsonify({"topics": topics})


@app.route('/writing/summarize-written-text/get-categories', methods=['GET'])
def get_swt_categories():
    difficulties = get_writing_difficulties("summarize_written_text")
    if not difficulties:
        return jsonify({"error": "No categories available"}), 404
    return jsonify({"categories": difficulties})


@app.route('/writing/summarize-written-text/get-catalog', methods=['GET'])
def get_swt_catalog():
    catalog = get_writing_catalog("summarize_written_text")
    if not catalog:
        return jsonify({"error": "No SWT prompts available"}), 404
    return jsonify({"items": catalog})


@app.route('/writing/summarize-written-text/get-task', methods=['GET'])
def get_swt_prompt():
    topic = request.args.get("topic", None)
    difficulty = request.args.get("difficulty", None)
    prompt_id = request.args.get("prompt_id", None)
    task = get_swt_task(topic=topic, prompt_id=prompt_id, difficulty=difficulty)
    if not task:
        return jsonify({"error": "No SWT prompts available"}), 404

    return jsonify({
        "id": task.get("id", ""),
        "title": task.get("title", "Untitled"),
        "topic": task.get("topic", "General"),
        "difficulty": task.get("difficulty", "medium"),
        "passage": task.get("passage", ""),
        "recommended_word_range": f"{5}-{75}",
    })


@app.route('/writing/summarize-written-text/score', methods=['POST'])
def score_swt():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = request.form.to_dict(flat=True)

    passage = str(payload.get("passage", ""))
    response_text = str(payload.get("response", ""))
    prompt_id = payload.get("prompt_id")

    result = evaluate_summarize_written_text(passage, response_text, prompt_id=prompt_id)
    if "error" in result:
        return jsonify(result), 400

    _persist_writing_result(
        "summarize_written_text",
        {
            "request": {
                "prompt_id": prompt_id,
                "passage": passage,
                "response": response_text,
            },
            "result": result,
        },
    )
    return jsonify(result)


@app.route('/writing/write-essay/get-topics', methods=['GET'])
def get_essay_topics():
    topics = get_writing_topics("write_essay")
    if not topics:
        return jsonify({"error": "No topics available"}), 404
    return jsonify({"topics": topics})


@app.route('/writing/write-essay/get-categories', methods=['GET'])
def get_essay_categories():
    difficulties = get_writing_difficulties("write_essay")
    if not difficulties:
        return jsonify({"error": "No categories available"}), 404
    return jsonify({"categories": difficulties})


@app.route('/writing/write-essay/get-catalog', methods=['GET'])
def get_essay_catalog():
    catalog = get_writing_catalog("write_essay")
    if not catalog:
        return jsonify({"error": "No essay prompts available"}), 404
    return jsonify({"items": catalog})


@app.route('/writing/write-essay/get-task', methods=['GET'])
def get_essay_prompt():
    topic = request.args.get("topic", None)
    difficulty = request.args.get("difficulty", None)
    prompt_id = request.args.get("prompt_id", None)
    task = get_essay_task(topic=topic, prompt_id=prompt_id, difficulty=difficulty)
    if not task:
        return jsonify({"error": "No essay prompts available"}), 404

    return jsonify({
        "id": task.get("id", ""),
        "title": task.get("title", "Untitled"),
        "topic": task.get("topic", "General"),
        "difficulty": task.get("difficulty", "medium"),
        "prompt": task.get("prompt", ""),
        "recommended_word_range": task.get("recommended_word_range", "200-300"),
    })


@app.route('/writing/write-essay/score', methods=['POST'])
def score_essay():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = request.form.to_dict(flat=True)

    prompt = str(payload.get("prompt", ""))
    response_text = str(payload.get("response", ""))
    prompt_id = payload.get("prompt_id")

    result = evaluate_write_essay(prompt, response_text, prompt_id=prompt_id)
    if "error" in result:
        return jsonify(result), 400

    _persist_writing_result(
        "write_essay",
        {
            "request": {
                "prompt_id": prompt_id,
                "prompt": prompt,
                "response": response_text,
            },
            "result": result,
        },
    )
    return jsonify(result)


@app.route('/writing/write-email/get-topics', methods=['GET'])
def get_write_email_topics():
    topics = get_writing_topics("write_email")
    if not topics:
        return jsonify({"error": "No topics available"}), 404
    return jsonify({"topics": topics})


@app.route('/writing/write-email/get-categories', methods=['GET'])
def get_write_email_categories():
    difficulties = get_writing_difficulties("write_email")
    if not difficulties:
        return jsonify({"error": "No categories available"}), 404
    return jsonify({"categories": difficulties})


@app.route('/writing/write-email/get-catalog', methods=['GET'])
def get_write_email_catalog():
    catalog = get_writing_catalog("write_email")
    if not catalog:
        return jsonify({"error": "No write email prompts available"}), 404
    return jsonify({"items": catalog})


@app.route('/writing/write-email/get-task', methods=['GET'])
def get_write_email_prompt():
    topic = request.args.get("topic", None)
    difficulty = request.args.get("difficulty", None)
    prompt_id = request.args.get("prompt_id", None)
    task = get_email_task(topic=topic, prompt_id=prompt_id, difficulty=difficulty)
    if not task:
        return jsonify({"error": "No write email prompts available"}), 404

    return jsonify({
        "id": task.get("id", ""),
        "title": task.get("title", "Untitled"),
        "topic": task.get("topic", "General"),
        "difficulty": task.get("difficulty", "medium"),
        "prompt": task.get("prompt", ""),
        "recipient": task.get("recipient", ""),
        "tone": task.get("tone", "formal"),
        "recommended_word_range": task.get("recommended_word_range", "50-120"),
    })


@app.route('/writing/write-email/score', methods=['POST'])
def score_write_email():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = request.form.to_dict(flat=True)

    prompt = str(payload.get("prompt", ""))
    response_text = str(payload.get("response", ""))
    prompt_id = payload.get("prompt_id")

    result = evaluate_write_email(prompt, response_text, prompt_id=prompt_id)
    if "error" in result:
        return jsonify(result), 400

    _persist_writing_result(
        "write_email",
        {
            "request": {
                "prompt_id": prompt_id,
                "prompt": prompt,
                "response": response_text,
            },
            "result": result,
        },
    )
    return jsonify(result)

@app.route('/save', methods=['POST'])
def save():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
    
    file = request.files['audio']
    text = request.form.get('text', '')
    feature = request.form.get('feature', FEATURE_READ_ALOUD)
    
    audio_path, text_path = get_paired_paths(feature)
    temp_path = get_temp_filepath('upload', 'webm', directory=os.path.dirname(audio_path))
    
    file.save(temp_path)
    
    if convert_to_wav(temp_path, audio_path):
        _maybe_cleanup([temp_path], force=True)
    else:
        os.rename(temp_path, audio_path)
    
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    filename = os.path.basename(audio_path).replace('.wav', '')
    return jsonify({"message": f"Saved as {filename}"})

@app.route('/check', methods=['POST'])
def check():
    """Submit audio for async pronunciation check. Returns job_id immediately."""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
        
    file = request.files['audio']
    text = request.form.get('text', '')
    feature = request.form.get('feature', FEATURE_READ_ALOUD)
    accent = request.form.get('accent', 'US_ARPA')  # Default to US_ARPA
    
    job_id = str(uuid.uuid4())[:8]
    audio_path, text_path = get_paired_paths(feature)
    temp_upload = get_temp_filepath(f'upload_{job_id}', 'tmp', directory=os.path.dirname(audio_path))
    
    try:
        file.save(temp_upload)
        
        if not convert_to_wav(temp_upload, audio_path):
            _maybe_cleanup([temp_upload], force=True)
            return jsonify({"error": "Audio conversion failed"}), 500
        
        _maybe_cleanup([temp_upload], force=True)
        
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        JOB_STORE[job_id] = {
            'status': 'queued',
            'result': None,
            'error': None,
            'audio_path': audio_path,
            'text_path': text_path,
            'accent': accent,
            'created_at': datetime.datetime.now().isoformat()
        }
        
        thread = threading.Thread(
            target=run_mfa_job,
            args=(job_id, audio_path, text_path),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "status": "queued",
            "job_id": job_id,
            "estimated_time": 30,
            "message": "Processing started. Poll /check/status/<job_id> for results."
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/check/status/<job_id>', methods=['GET'])
def check_status(job_id):
    """Get status of a pronunciation check job."""
    if job_id not in JOB_STORE:
        return jsonify({"error": "Job not found"}), 404
    
    job = JOB_STORE[job_id]
    response = {"job_id": job_id, "status": job['status']}
    
    if job['status'] == 'complete':
        response['result'] = job['result']
    elif job['status'] == 'failed':
        response['error'] = job['error']
    
    return jsonify(response)

@app.route('/check_stream', methods=['POST'])
def check_stream():
    """Streaming version of check using the main engine's generator."""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
        
    file = request.files['audio']
    text = request.form.get('text', '')
    feature = request.form.get('feature', FEATURE_READ_ALOUD)
    accent = request.form.get('accent', 'US_ARPA')  # Default to US_ARPA
    
    audio_path, text_path = get_paired_paths(feature)
    temp_upload = get_temp_filepath("temp_upload", "tmp", directory=os.path.dirname(audio_path))
    
    file.save(temp_upload)

    def generate():
        try:
            yield json.dumps({"type": "progress", "percent": 2, "message": "Converting audio..."}) + "\n"
            if not convert_to_wav(temp_upload, audio_path):
                 _maybe_cleanup([temp_upload], force=True)
                 yield json.dumps({"type": "error", "message": "Audio conversion failed"}) + "\n"
                 return
            
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
                
            from api.validator import align_and_validate_gen
            for update in align_and_validate_gen(audio_path, text_path, accents=[accent]):
                if isinstance(update, dict) and update.get("type") == "result":
                    _persist_attempt_artifacts(audio_path, update.get("data"), filename="check_stream_result.json")
                yield json.dumps(update) + "\n"
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"
        finally:
            _maybe_cleanup([temp_upload], force=True)
            _maybe_cleanup([audio_path, text_path])

    return Response(generate(), mimetype='application/x-ndjson')

# ============================================================================
# ROUTES - IMAGE DESCRIPTION
# ============================================================================
@app.route('/describe-image/get-image', methods=['GET'])
def get_image_task():
    topic = request.args.get('topic', None)  # Backward-compatible alias for difficulty
    difficulty = request.args.get('difficulty', None)
    chart_type = request.args.get('chart_type', None)
    image_id = request.args.get('image_id', None)
    exclude_id = request.args.get('exclude_id', None)
    image_data = get_random_image(
        topic=topic,
        difficulty=difficulty,
        chart_type=chart_type,
        image_id=image_id,
        exclude_id=exclude_id,
    )
    if not image_data:
        return jsonify({"error": "No images available"}), 404

    difficulty_value = str(image_data.get('difficulty', 'general')).strip().lower() or "general"
    chart_type_value = infer_chart_type(image_data)

    return jsonify({
        "image_id": image_data['id'],
        "image_url": f"/images/{image_data['filename']}",
        "title": image_data['title'],
        "topic": difficulty_value.title(),
        "difficulty": difficulty_value,
        "chart_type": chart_type_value
    })

@app.route('/speaking/describe-image/get-topics', methods=['GET'])
def get_describe_image_topics():
    """Get available topic filters for describe image."""
    catalog = get_image_catalog()
    if not catalog:
        return jsonify({"error": "No topics available"}), 404

    # Keep difficulty order stable for UI
    preferred_difficulty_order = {"easy": 0, "medium": 1, "difficult": 2}
    difficulties = sorted(
        {item.get("difficulty", "general") for item in catalog},
        key=lambda value: (preferred_difficulty_order.get(value, 99), value),
    )
    chart_types = ["bargraph", "piechart", "other"]

    return jsonify({
        "topics": [item.get("title", "Untitled") for item in catalog],
        "images": catalog,
        "filters": {
            "difficulty": difficulties,
            "chart_type": chart_types,
        }
    })

@app.route('/describe-image/submit', methods=['POST'])
def submit_description():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
    
    file = request.files['audio']
    image_id = request.form.get('image_id', '')
    accent = request.form.get('accent', 'US_ARPA')  # Default to US_ARPA
    
    job_id = str(uuid.uuid4())[:8]
    audio_path, _ = get_paired_paths(FEATURE_DESCRIBE_IMAGE)
    temp_upload = get_temp_filepath(f'img_{job_id}', 'tmp', directory=os.path.dirname(audio_path))
    
    try:
        file.save(temp_upload)
        if not convert_to_wav(temp_upload, audio_path):
            _maybe_cleanup([temp_upload], force=True)
            return jsonify({"error": "Audio conversion failed"}), 500
        _maybe_cleanup([temp_upload], force=True)
        
        IMAGE_JOB_STORE[job_id] = {
            'status': 'queued',
            'result': None,
            'error': None,
            'image_id': image_id,
            'audio_path': audio_path,
            'accent': accent,
            'created_at': datetime.datetime.now().isoformat()
        }
        
        thread = threading.Thread(
            target=run_image_evaluation_job,
            args=(job_id, image_id, audio_path),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "status": "queued",
            "job_id": job_id,
            "estimated_time": 10,
            "message": "Processing started."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/describe-image/status/<job_id>', methods=['GET'])
def description_status(job_id):
    if job_id not in IMAGE_JOB_STORE:
        return jsonify({"error": "Job not found"}), 404
    job = IMAGE_JOB_STORE[job_id]
    response = {"job_id": job_id, "status": job['status']}
    if job['status'] == 'complete':
        response['result'] = job['result']
    elif job['status'] == 'failed':
        response['error'] = job['error']
    return jsonify(response)

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)

@app.route('/lectures/<path:filename>')
def serve_lecture(filename):
    return send_from_directory(LECTURES_DIR, filename)

# ============================================================================
# ROUTES - RETELL LECTURE
# ============================================================================
@app.route('/retell-lecture/get-categories', methods=['GET'])
def get_retell_lecture_categories():
    categories = get_lecture_categories()
    if not categories:
        return jsonify({"error": "No categories available"}), 404
    return jsonify({"categories": categories})


@app.route('/retell-lecture/get-catalog', methods=['GET'])
def get_retell_lecture_catalog():
    catalog = get_lecture_catalog()
    if not catalog:
        return jsonify({"error": "No lectures available"}), 404
    return jsonify({"items": catalog})


@app.route('/retell-lecture/get-lecture', methods=['GET'])
def get_lecture_task():
    lecture_id = request.args.get("lecture_id", None)
    difficulty = request.args.get("difficulty", None)
    try:
        tts_params = _resolve_tts_request(feature="retell_lecture")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if lecture_id:
        lecture_data = get_lecture_by_id(lecture_id)
    else:
        lecture_data = get_random_lecture(difficulty=difficulty)
    if not lecture_data:
        return jsonify({"error": "No lectures available"}), 404

    resolved_lecture_id = str(lecture_data.get("id", "")).strip()
    if not resolved_lecture_id:
        return jsonify({"error": "Lecture id is missing"}), 500

    return jsonify({
        "lecture_id": resolved_lecture_id,
        "audio_url": _build_retell_audio_url(resolved_lecture_id, tts_params),
        "title": lecture_data['title'],
        "difficulty": lecture_data.get("difficulty", "medium"),
        "tts": {
            "provider": tts_params["provider"],
            "voice": tts_params["voice"],
            "speed": tts_params["speed"],
        },
    })


@app.route('/retell-lecture/audio/<lecture_id>', methods=['GET'])
def retell_lecture_audio(lecture_id):
    lecture_data = get_lecture_by_id(lecture_id)
    if not lecture_data:
        return jsonify({"error": "Lecture not found"}), 404

    transcript = str(lecture_data.get("transcript", "")).strip()
    if not transcript:
        return jsonify({"error": "Lecture transcript not found"}), 404

    try:
        tts_params = _resolve_tts_request(feature="retell_lecture")
        audio_bytes = synthesize_speech(
            transcript,
            speed=tts_params["speed"],
            voice=tts_params["voice"],
            provider=tts_params["provider"],
            rate=tts_params["rate"],
            pitch=tts_params["pitch"] or "+0Hz",
            feature="retell_lecture",
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"TTS generation failed: {exc}"}), 500

    response = Response(audio_bytes, mimetype="audio/mpeg")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route('/retell-lecture/submit', methods=['POST'])
def submit_lecture():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
    
    file = request.files['audio']
    lecture_id = request.form.get('lecture_id', '')
    accent = request.form.get('accent', 'US_ARPA')  # Default to US_ARPA
    
    job_id = str(uuid.uuid4())[:8]
    audio_path, _ = get_paired_paths(FEATURE_RETELL_LECTURE)
    temp_upload = get_temp_filepath(f'lec_{job_id}', 'tmp', directory=os.path.dirname(audio_path))
    
    try:
        file.save(temp_upload)
        if not convert_to_wav(temp_upload, audio_path):
            _maybe_cleanup([temp_upload], force=True)
            return jsonify({"error": "Audio conversion failed"}), 500
        _maybe_cleanup([temp_upload], force=True)
        
        LECTURE_JOB_STORE[job_id] = {
            'status': 'queued',
            'result': None,
            'error': None,
            'lecture_id': lecture_id,
            'audio_path': audio_path,
            'accent': accent,
            'created_at': datetime.datetime.now().isoformat()
        }
        
        thread = threading.Thread(
            target=run_lecture_evaluation_job,
            args=(job_id, lecture_id, audio_path),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "status": "queued",
            "job_id": job_id,
            "estimated_time": 10,
            "message": "Processing started."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/retell-lecture/status/<job_id>', methods=['GET'])
def lecture_status(job_id):
    if job_id not in LECTURE_JOB_STORE:
        return jsonify({"error": "Job not found"}), 404
    job = LECTURE_JOB_STORE[job_id]
    response = {"job_id": job_id, "status": job['status']}
    if job['status'] == 'complete':
        response['result'] = job['result']
    elif job['status'] == 'failed':
        response['error'] = job['error']
    return jsonify(response)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    app.run(debug=True, host='0.0.0.0', port=args.port)
