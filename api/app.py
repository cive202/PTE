import os
import sys
import datetime
import subprocess
import json
import threading
import uuid
import requests
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

app = Flask(__name__)
CORPUS_DIR = os.path.join(PROJECT_ROOT, "corpus")
DATA_DIR = os.path.join(PROJECT_ROOT, "data_2")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
LECTURES_DIR = os.path.join(DATA_DIR, "lectures")
os.makedirs(CORPUS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(LECTURES_DIR, exist_ok=True)

# Docker Grammar Service URL
GRAMMAR_SERVICE_URL = "http://localhost:8000/grammar"

# ============================================================================
# JOB QUEUE SYSTEM
# ============================================================================
JOB_STORE = {}  # {job_id: {status, result, error, audio_path, text_path}}
IMAGE_JOB_STORE = {}  # {job_id: {status, result, error, image_id, audio_path}}
LECTURE_JOB_STORE = {}  # {job_id: {status, result, error, lecture_id, audio_path}}

def run_mfa_job(job_id, audio_path, text_path):
    """Background worker for MFA alignment using the main engine."""
    try:
        JOB_STORE[job_id]['status'] = 'processing'
        
        # Use the main engine from validator.py
        result = align_and_validate(audio_path, text_path)
        
        JOB_STORE[job_id]['status'] = 'complete'
        JOB_STORE[job_id]['result'] = result
    except Exception as e:
        import traceback
        traceback.print_exc()
        JOB_STORE[job_id]['status'] = 'failed'
        JOB_STORE[job_id]['error'] = str(e)
    finally:
        # Cleanup temp files
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            if os.path.exists(text_path):
                os.remove(text_path)
        except Exception:
            pass

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
        mfa_result = align_and_validate(audio_path, temp_text_path, accents=['Indian'])
        
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
    except Exception as e:
        import traceback
        traceback.print_exc()
        IMAGE_JOB_STORE[job_id]['status'] = 'failed'
        IMAGE_JOB_STORE[job_id]['error'] = str(e)
    finally:
        # Cleanup temp files
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            if 'temp_text_path' in locals() and os.path.exists(temp_text_path):
                os.remove(temp_text_path)
        except Exception:
            pass

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
        mfa_result = align_and_validate(audio_path, temp_text_path, accents=['Indian'])
        
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
    except Exception as e:
        import traceback
        traceback.print_exc()
        LECTURE_JOB_STORE[job_id]['status'] = 'failed'
        LECTURE_JOB_STORE[job_id]['error'] = str(e)
    finally:
        # Cleanup temp files
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            if 'temp_text_path' in locals() and os.path.exists(temp_text_path):
                os.remove(temp_text_path)
        except Exception:
            pass

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
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"Conversion failed: {e}")
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

@app.route('/speaking/repeat-sentence')
def repeat_sentence():
    """Repeat Sentence practice page."""
    return render_template('repeat_sentence.html')

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
    temp_path = get_temp_filepath('upload', 'webm')
    
    file.save(temp_path)
    
    if convert_to_wav(temp_path, audio_path):
        os.remove(temp_path)
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
    
    job_id = str(uuid.uuid4())[:8]
    audio_path, text_path = get_paired_paths(feature)
    temp_upload = get_temp_filepath(f'upload_{job_id}', 'tmp')
    
    try:
        file.save(temp_upload)
        
        if not convert_to_wav(temp_upload, audio_path):
            return jsonify({"error": "Audio conversion failed"}), 500
        
        if os.path.exists(temp_upload):
            os.remove(temp_upload)
        
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        JOB_STORE[job_id] = {
            'status': 'queued',
            'result': None,
            'error': None,
            'audio_path': audio_path,
            'text_path': text_path,
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
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    temp_upload = os.path.join(CORPUS_DIR, f"temp_upload_{timestamp}")
    audio_path = os.path.join(CORPUS_DIR, f"check_{timestamp}.wav")
    text_path = os.path.join(CORPUS_DIR, f"check_{timestamp}.txt")
    
    file.save(temp_upload)

    def generate():
        try:
            yield json.dumps({"type": "progress", "percent": 2, "message": "Converting audio..."}) + "\n"
            if not convert_to_wav(temp_upload, audio_path):
                 yield json.dumps({"type": "error", "message": "Audio conversion failed"}) + "\n"
                 return
            
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
                
            from api.validator import align_and_validate_gen
            for update in align_and_validate_gen(audio_path, text_path):
                yield json.dumps(update) + "\n"
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"
        finally:
            try:
                if os.path.exists(temp_upload): os.remove(temp_upload)
                if os.path.exists(audio_path): os.remove(audio_path)
                if os.path.exists(text_path): os.remove(text_path)
            except Exception: pass

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
    
    job_id = str(uuid.uuid4())[:8]
    audio_path, _ = get_paired_paths(FEATURE_DESCRIBE_IMAGE)
    temp_upload = get_temp_filepath(f'img_{job_id}', 'tmp')
    
    try:
        file.save(temp_upload)
        if not convert_to_wav(temp_upload, audio_path):
            return jsonify({"error": "Audio conversion failed"}), 500
        if os.path.exists(temp_upload):
            os.remove(temp_upload)
        
        IMAGE_JOB_STORE[job_id] = {
            'status': 'queued',
            'result': None,
            'error': None,
            'image_id': image_id,
            'audio_path': audio_path,
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
    
    job_id = str(uuid.uuid4())[:8]
    audio_path, _ = get_paired_paths(FEATURE_RETELL_LECTURE)
    temp_upload = get_temp_filepath(f'lec_{job_id}', 'tmp')
    
    try:
        file.save(temp_upload)
        if not convert_to_wav(temp_upload, audio_path):
            return jsonify({"error": "Audio conversion failed"}), 500
        if os.path.exists(temp_upload):
            os.remove(temp_upload)
        
        LECTURE_JOB_STORE[job_id] = {
            'status': 'queued',
            'result': None,
            'error': None,
            'lecture_id': lecture_id,
            'audio_path': audio_path,
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
    app.run(debug=True, host='0.0.0.0', port=5000)
