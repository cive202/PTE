import torch
import librosa
from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC
import warnings

# Suppress warnings
warnings.filterwarnings("ignore")

MODEL_ID = "facebook/wav2vec2-lv-60-espeak-cv-ft"
device = "cpu"  # CPU only

print(f"Loading wav2vec2 phoneme model from {MODEL_ID} (CPU)...")
try:
    processor = Wav2Vec2Processor.from_pretrained(MODEL_ID)
    model = Wav2Vec2ForCTC.from_pretrained(MODEL_ID).to(device)
    model.eval()
    print("Model loaded successfully")
except Exception as e:
    print(f"Error loading model: {e}")
    raise e

def get_phonemes(wav_path, start=None, end=None):
    """
    Extract phonemes from audio file.
    Args:
        wav_path: Path to .wav file
        start: Start time in seconds (optional)
        end: End time in seconds (optional)
    Returns:
        List of phonemes
    """
    try:
        # Load audio at 16kHz
        audio, sr = librosa.load(wav_path, sr=16000)

        # Slice if start/end provided
        if start is not None and end is not None:
            start_frame = int(start * sr)
            end_frame = int(end * sr)
            
            # Boundary checks
            if start_frame < 0: start_frame = 0
            if end_frame > len(audio): end_frame = len(audio)
            
            # Ensure valid segment length
            if end_frame > start_frame:
                audio = audio[start_frame:end_frame]
            else:
                return [] # Empty result for invalid segment

        # Check for very short audio which might crash model
        if len(audio) < 160: # < 0.01s
            return []

        inputs = processor(audio, sampling_rate=16000, return_tensors="pt").input_values.to(device)

        with torch.no_grad():
            logits = model(inputs).logits

        ids = torch.argmax(logits, dim=-1)
        phonemes = processor.batch_decode(ids)[0]
        
        # Clean up result (remove empty strings if any)
        return phonemes.split()
        
    except Exception as e:
        print(f"Inference error: {e}")
        return []
