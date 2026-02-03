
import os
import shutil
import tempfile
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import language_tool_python
import nemo.collections.asr as nemo_asr
import torch
import lhotse

# --- Monkeypatch Lhotse ---
# Fix for "TypeError: object.__init__() takes exactly one argument"
try:
    import lhotse.dataset.sampling.base
    original_init = lhotse.dataset.sampling.base.CutSampler.__init__
    def patched_init(self, *args, **kwargs):
        try:
            # Try to call the original init
            original_init(self, *args, **kwargs)
        except TypeError as e:
            if "object.__init__() takes exactly one argument" in str(e):
                # If it fails with the specific error, manually initialize
                # This is a fallback for the specific lhotse/torch version mismatch
                self.drop_last = kwargs.get('drop_last', False)
                self.shuffle = kwargs.get('shuffle', False)
                self.seed = kwargs.get('seed', 0)
                self.epoch = 0
                from lhotse.dataset.sampling.base import SamplingDiagnostics, _filter_nothing
                self._diagnostics = SamplingDiagnostics()
                self._just_restored_state = False
                self._maybe_init_distributed(world_size=kwargs.get('world_size'), rank=kwargs.get('rank'))
                self._filter_fn = _filter_nothing()
                self._transforms = []
            else:
                raise e
    lhotse.dataset.sampling.base.CutSampler.__init__ = patched_init
    print("Applied Lhotse monkeypatch.")
except Exception as e:
    print(f"Failed to apply Lhotse monkeypatch: {e}")

app = FastAPI(title="PTE ASR & Grammar Service")

# --- Global Models ---
# Load models at startup to avoid reloading on every request

print("Loading Parakeet ASR model...")
try:
    # Use a smaller Parakeet model to fit in memory (0.6b instead of 1.1b)
    asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name="nvidia/parakeet-ctc-0.6b")
    # Move to GPU if available
    if torch.cuda.is_available():
        asr_model = asr_model.cuda()
    asr_model.eval()
    print("Parakeet ASR model loaded.")
except Exception as e:
    print(f"Error loading Parakeet ASR model: {e}")
    asr_model = None

print("Loading LanguageTool...")
try:
    # Re-enabling LanguageTool for grammar checking
    lang_tool = language_tool_python.LanguageTool('en-US')
    print("LanguageTool initialized.")
except Exception as e:
    print(f"Error loading LanguageTool: {e}")
    lang_tool = None


# --- Data Models ---
class GrammarRequest(BaseModel):
    text: str

class GrammarResponse(BaseModel):
    matches: List[str]

# --- Endpoints ---

@app.get("/health")
def health_check():
    return {
        "status": "ok", 
        "language_tool": lang_tool is not None,
        "asr_model": asr_model is not None
    }

@app.post("/asr")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe audio file using Parakeet ASR model.
    """
    if not asr_model:
        raise HTTPException(status_code=503, detail="ASR model not loaded")

    print(f"Received transcription request for file: {file.filename}")
    
    # Create a temporary file to store the uploaded audio
    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    try:
        with os.fdopen(fd, 'wb') as tmp:
            content = await file.read()
            tmp.write(content)
        
        print(f"File saved to {tmp_path}, starting transcription...")
        
        # Convert to mono if necessary using ffmpeg
        mono_path = tmp_path.replace(".wav", "_mono.wav")
        os.system(f"ffmpeg -i {tmp_path} -ac 1 {mono_path} -y")
        if os.path.exists(mono_path):
            transcription_path = mono_path
        else:
            transcription_path = tmp_path

        # Run transcription with hypotheses to get timestamps
        # Parakeet returns a list of transcriptions or hypotheses
        transcriptions = asr_model.transcribe([transcription_path], batch_size=1, return_hypotheses=True)
        
        print(f"Transcription finished. Output type: {type(transcriptions)}")
        
        word_timestamps = []
        text = ""

        if transcriptions and len(transcriptions) > 0:
            hyp = transcriptions[0]
            # Handle list of hypotheses if returned
            if isinstance(hyp, list) and len(hyp) > 0:
                hyp = hyp[0]
            
            text = hyp.text
            
            # Extract word timestamps if available
            # For NeMo CTC models, hyp often has 'word_offsets'
            if hasattr(hyp, 'word_offsets') and hyp.word_offsets:
                for word_info in hyp.word_offsets:
                    # word_info is usually a dict with {'word': str, 'start_offset': int, 'end_offset': int}
                    # Offsets are in frames, need to convert to seconds.
                    # Default frame shift for NeMo models is often 0.04s or 0.08s depending on the model.
                    # However, Hypotheses in recent NeMo versions often already have 'start_time' and 'end_time' in seconds.
                    
                    word_timestamps.append({
                        "word": word_info.get('word', ''),
                        "start": word_info.get('start_offset', 0) * 0.04, # Assuming 40ms frame shift
                        "end": word_info.get('end_offset', 0) * 0.04
                    })
            elif hasattr(hyp, 'timestep') and hyp.timestep:
                # Fallback if only frame-level timesteps are available
                # This is more complex to aggregate into words manually
                pass

        return {
            "text": text,
            "word_timestamps": word_timestamps
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # Clean up temporary files
        for p in [tmp_path, tmp_path.replace(".wav", "_mono.wav")]:
            if os.path.exists(p):
                os.remove(p)

@app.post("/grammar", response_model=GrammarResponse)
async def check_grammar(req: GrammarRequest):
    """
    Check grammar of provided text using LanguageTool.
    """
    if not lang_tool:
        raise HTTPException(status_code=503, detail="LanguageTool not loaded")

    try:
        matches = lang_tool.check(req.text)
        formatted_matches = []
        for match in matches:
            # Format: "RuleID: Message (Context: ...)"
            context = match.context
            if len(context) > 50:
                context = context[:47] + "..."
            issue = f"[{match.ruleId}] {match.message} near '{context}'"
            formatted_matches.append(issue)
        
        return {"matches": formatted_matches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grammar check failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
