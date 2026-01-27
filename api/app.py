import os
import sys
import datetime
import subprocess
from flask import Flask, render_template, request, jsonify

# Ensure project root is in path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.validator import align_and_validate

app = Flask(__name__)
CORPUS_DIR = os.path.join(PROJECT_ROOT, "corpus")
os.makedirs(CORPUS_DIR, exist_ok=True)

def convert_to_wav(input_path, output_path):
    """Convert audio to 16kHz mono WAV using ffmpeg."""
    try:
        # ffmpeg -i input -ac 1 -ar 16000 output.wav -y
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save', methods=['POST'])
def save():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
    
    file = request.files['audio']
    text = request.form.get('text', '')
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"recording_{timestamp}"
    
    # Save original upload temporarily
    temp_path = os.path.join(CORPUS_DIR, f"temp_{base_name}.webm") # Browser usually sends webm
    file.save(temp_path)
    
    final_audio_path = os.path.join(CORPUS_DIR, f"{base_name}.wav")
    text_path = os.path.join(CORPUS_DIR, f"{base_name}.txt")
    
    # Convert
    if convert_to_wav(temp_path, final_audio_path):
        os.remove(temp_path) # Remove temp if successful
    else:
        # Fallback: just rename if conversion fails (might still fail in MFA)
        os.rename(temp_path, final_audio_path)
    
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(text)
        
    return jsonify({"message": f"Saved as {base_name}"})

@app.route('/check', methods=['POST'])
def check():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
        
    file = request.files['audio']
    text = request.form.get('text', '')
    
    # Save to temp for validation
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    temp_upload = os.path.join(CORPUS_DIR, f"temp_upload_{timestamp}")
    
    audio_path = os.path.join(CORPUS_DIR, f"check_{timestamp}.wav")
    text_path = os.path.join(CORPUS_DIR, f"check_{timestamp}.txt")
    
    try:
        file.save(temp_upload)
        
        # Convert to ensure 16kHz WAV
        if not convert_to_wav(temp_upload, audio_path):
             return jsonify({"error": "Audio conversion failed"}), 500
        
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
            
        # Run validation
        result = align_and_validate(audio_path, text_path)
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        # Cleanup temp files
        try:
            if os.path.exists(temp_upload):
                os.remove(temp_upload)
            if os.path.exists(audio_path):
                os.remove(audio_path)
            if os.path.exists(text_path):
                os.remove(text_path)
        except Exception:
            pass

if __name__ == '__main__':
    # Running on 0.0.0.0 to be accessible if needed
    app.run(debug=True, host='0.0.0.0', port=5000)
