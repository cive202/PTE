import os
import sys
import datetime
import subprocess
import threading
import uuid
from flask import Flask, render_template, request, jsonify, send_from_directory

# Ensure project root is in path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.validator import align_and_validate
from api.image_evaluator import get_random_image, evaluate_description
from api.file_utils import (
    get_paired_paths,
    get_temp_filepath,
    FEATURE_READ_ALOUD,
    FEATURE_DESCRIBE_IMAGE
)

app = Flask(__name__)
CORPUS_DIR = os.path.join(PROJECT_ROOT, "corpus")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
os.makedirs(CORPUS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# ============================================================================
# JOB QUEUE SYSTEM
# ============================================================================
JOB_STORE = {}  # {job_id: {status, result, error, audio_path, text_path}}
IMAGE_JOB_STORE = {}  # {job_id: {status, result, error, image_id, audio_path}}

def run_mfa_job(job_id, audio_path, text_path):
    """Background worker for MFA alignment."""
    try:
        JOB_STORE[job_id]['status'] = 'processing'
        
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
            # Also remove the temp upload if it exists
            temp_upload = JOB_STORE[job_id].get('temp_upload')
            if temp_upload and os.path.exists(temp_upload):
                os.remove(temp_upload)
        except Exception:
            pass

def run_image_evaluation_job(job_id, image_id, audio_path):
    """Background worker for image description evaluation."""
    try:
        IMAGE_JOB_STORE[job_id]['status'] = 'processing'
        
        # Transcribe audio using Whisper
        import requests
        with open(audio_path, 'rb') as audio_file:
            files = {'audio': ('audio.wav', audio_file, 'audio/wav')}
            response = requests.post('http://localhost:8000/transcribe', files=files, timeout=60)
        
        if response.status_code != 200:
            raise Exception(f"ASR service error: {response.status_code}")
        
        asr_result = response.json()
        transcription = asr_result.get('text', '').strip()
        
        # Evaluate description
        result = evaluate_description(image_id, transcription)
        
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
# ROUTES - SPEAKING TASKS
# ============================================================================
@app.route('/speaking/read-aloud')
def read_aloud():
    """Read Aloud practice page."""
    return render_template('index.html')

@app.route('/speaking/repeat-sentence')
def repeat_sentence():
    """Repeat Sentence practice page."""
    # For now, redirect to read-aloud (same functionality)
    return render_template('index.html')

@app.route('/speaking/describe-image')
def describe_image_speaking():
    """Describe Image practice page."""
    return render_template('describe_image.html')

# Backward compatibility redirects
@app.route('/check-pronunciation')
def old_check_pronunciation():
    """Redirect old URL to new structure."""
    from flask import redirect
    return redirect('/speaking/read-aloud', code=301)

@app.route('/save', methods=['POST'])
def save():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
    
    file = request.files['audio']
    text = request.form.get('text', '')
    
    # Use standardized file naming
    audio_path, text_path = get_paired_paths(FEATURE_READ_ALOUD)
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
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())[:8]
    
    # Use standardized file naming
    audio_path, text_path = get_paired_paths(FEATURE_READ_ALOUD)
    temp_upload = get_temp_filepath(f'upload_{job_id}', 'tmp')
    
    try:
        file.save(temp_upload)
        
        # Convert to ensure 16kHz WAV
        if not convert_to_wav(temp_upload, audio_path):
            return jsonify({"error": "Audio conversion failed"}), 500
        
        # Remove temp upload after conversion
        if os.path.exists(temp_upload):
            os.remove(temp_upload)
        
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        # Initialize job in store
        JOB_STORE[job_id] = {
            'status': 'queued',
            'result': None,
            'error': None,
            'audio_path': audio_path,
            'text_path': text_path,
            'created_at': datetime.datetime.now().isoformat()
        }
        
        # Start background thread
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
    
    response = {
        "job_id": job_id,
        "status": job['status']
    }
    
    if job['status'] == 'complete':
        response['result'] = job['result']
    elif job['status'] == 'failed':
        response['error'] = job['error']
    
    return jsonify(response)

# ============================================================================
# ROUTES - IMAGE DESCRIPTION (Legacy compatibility)
# ============================================================================
@app.route('/describe-image')
def describe_image_page():
    """Legacy route - redirect to new structure."""
    from flask import redirect
    return redirect('/speaking/describe-image', code=301)

@app.route('/describe-image/get-image', methods=['GET'])
def get_image_task():
    """Get a random image for description task."""
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
    """Submit audio description for async evaluation."""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
    
    file = request.files['audio']
    image_id = request.form.get('image_id', '')
    
    if not image_id:
        return jsonify({"error": "No image_id provided"}), 400
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())[:8]
    
    # Use standardized file naming
    audio_path, _ = get_paired_paths(FEATURE_DESCRIBE_IMAGE)
    temp_upload = get_temp_filepath(f'img_{job_id}', 'tmp')
    
    try:
        file.save(temp_upload)
        
        # Convert to ensure 16kHz WAV
        if not convert_to_wav(temp_upload, audio_path):
            return jsonify({"error": "Audio conversion failed"}), 500
        
        # Remove temp upload after conversion
        if os.path.exists(temp_upload):
            os.remove(temp_upload)
        
        # Initialize job in store
        IMAGE_JOB_STORE[job_id] = {
            'status': 'queued',
            'result': None,
            'error': None,
            'image_id': image_id,
            'audio_path': audio_path,
            'created_at': datetime.datetime.now().isoformat()
        }
        
        # Start background thread
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
            "message": "Processing started. Poll /describe-image/status/<job_id> for results."
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/describe-image/status/<job_id>', methods=['GET'])
def description_status(job_id):
    """Get status of an image description evaluation job."""
    if job_id not in IMAGE_JOB_STORE:
        return jsonify({"error": "Job not found"}), 404
    
    job = IMAGE_JOB_STORE[job_id]
    
    response = {
        "job_id": job_id,
        "status": job['status']
    }
    
    if job['status'] == 'complete':
        response['result'] = job['result']
    elif job['status'] == 'failed':
        response['error'] = job['error']
    
    return jsonify(response)

@app.route('/images/<path:filename>')
def serve_image(filename):
    """Serve images from data/images directory."""
    return send_from_directory(IMAGES_DIR, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
