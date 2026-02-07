from flask import Flask, request, jsonify
import tempfile
import os
from phoneme_model import get_phonemes

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "wav2vec2-phoneme-cpu"})

@app.route("/phonemes", methods=["POST"])
def phonemes():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
        
    file = request.files["audio"]
    
    # Get optional start/end times
    try:
        start = request.form.get("start", type=float)
        end = request.form.get("end", type=float)
    except ValueError:
        return jsonify({"error": "Invalid start/end parameters"}), 400

    # Save to temp file
    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    try:
        os.close(fd) # Close file descriptor so other libs can open it
        file.save(tmp_path)
        
        # Run inference
        ph = get_phonemes(tmp_path, start, end)
        
        return jsonify({"phonemes": ph})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass

if __name__ == "__main__":
    # Disable debug mode for production-like consistency
    app.run(host="0.0.0.0", port=8001, debug=False)
