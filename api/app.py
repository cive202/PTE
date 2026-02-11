import os
import sys
import datetime
import subprocess
import json
import threading
import uuid
import shutil
import requests
import random
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, send_from_directory

# Ensure project root is in path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.validator import align_and_validate, align_and_validate_gen
from api.image_evaluator import get_random_image, evaluate_description
from api.lecture_evaluator import get_random_lecture, evaluate_lecture
from api.file_utils import (
    get_paired_paths,
    get_temp_filepath,
    FEATURE_READ_ALOUD,
    FEATURE_REPEAT_SENTENCE,
    FEATURE_DESCRIBE_IMAGE,
    FEATURE_RETELL_LECTURE
)
from src.shared.paths import (
    IMAGES_DIR as SHARED_IMAGES_DIR,
    LECTURES_DIR as SHARED_LECTURES_DIR,
    REPEAT_SENTENCE_AUDIO_DIR as SHARED_REPEAT_SENTENCE_AUDIO_DIR,
    READ_ALOUD_REFERENCE_FILE,
    REPEAT_SENTENCE_REFERENCE_FILE,
    ensure_runtime_dirs,
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
        
        # Evaluate description
        result = evaluate_description(image_id, transcription)
        
        # Use MFA words directly (they already contain timing and status)
        mfa_words = mfa_result.get('words', []) if mfa_result else []
        
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
    image_data = get_random_image()
    if not image_data:
        return jsonify({"error": "No images available"}), 404
    return jsonify({
        "image_id": image_data['id'],
        "image_url": f"/images/{image_data['filename']}",
        "title": image_data['title']
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
@app.route('/retell-lecture/get-lecture', methods=['GET'])
def get_lecture_task():
    lecture_data = get_random_lecture()
    if not lecture_data:
        return jsonify({"error": "No lectures available"}), 404
    return jsonify({
        "lecture_id": lecture_data['id'],
        "audio_url": f"/lectures/{lecture_data['filename']}",
        "title": lecture_data['title']
    })

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
