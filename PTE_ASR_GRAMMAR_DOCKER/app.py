
import os
import shutil
import tempfile
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import whisper
import language_tool_python

app = FastAPI(title="PTE ASR & Grammar Service")

# --- Global Models ---
# Load models at startup to avoid reloading on every request
print("Loading Whisper model (medium)...")
try:
    # Use "medium" as requested. Could be parameterized.
    # It will download to ~/.cache/whisper on first run.
    whisper_model = whisper.load_model("medium")
    print("Whisper model loaded.")
except Exception as e:
    print(f"Error loading Whisper model: {e}")
    whisper_model = None

print("Loading LanguageTool...")
try:
    # This will download the Java server on first run if not present
    lang_tool = language_tool_python.LanguageTool('en-US')
    print("LanguageTool loaded.")
except Exception as e:
    print(f"Error loading LanguageTool: {e}")
    lang_tool = None


# --- Data Models ---
class GrammarRequest(BaseModel):
    text: str

class GrammarResponse(BaseModel):
    matches: List[str]

class ASRResponse(BaseModel):
    text: str

# --- Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "ok", "whisper": whisper_model is not None, "language_tool": lang_tool is not None}

@app.post("/asr", response_model=ASRResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe uploaded audio file using Whisper.
    """
    if not whisper_model:
        raise HTTPException(status_code=503, detail="Whisper model not loaded")

    # Save uploaded file to temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        temp_path = temp_file.name

    try:
        # Transcribe
        result = whisper_model.transcribe(temp_path)
        text = result.get("text", "").strip()
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)

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
