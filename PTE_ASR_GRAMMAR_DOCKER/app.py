
import os
import shutil
import tempfile
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import language_tool_python
import whisper

app = FastAPI(title="PTE ASR & Grammar Service")

# --- Global Models ---
print("Loading Whisper model (base)...")
try:
    whisper_model = whisper.load_model("base")
    print("Whisper model loaded.")
except Exception as e:
    print(f"Error loading Whisper: {e}")
    whisper_model = None

print("Loading LanguageTool...")
try:
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

class TranscribeResponse(BaseModel):
    text: str
    language: str
    segments: List[Dict[str, Any]]

# --- Endpoints ---

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "whisper": whisper_model is not None,
        "language_tool": lang_tool is not None
    }

@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio file using Whisper ASR.
    Returns: text, detected language, and word-level segments.
    """
    if not whisper_model:
        raise HTTPException(status_code=503, detail="Whisper model not loaded")

    # Save uploaded file to temp location
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_path = temp_file.name
            content = await audio.read()
            temp_file.write(content)
        
        # Transcribe with Whisper
        result = whisper_model.transcribe(
            temp_path,
            language="en",
            task="transcribe",
            word_timestamps=True
        )
        
        # Extract segments with word timestamps
        segments = []
        for seg in result.get("segments", []):
            segment_data = {
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": seg.get("text", ""),
                "words": []
            }
            # Add word-level timestamps if available
            for word in seg.get("words", []):
                segment_data["words"].append({
                    "word": word.get("word", ""),
                    "start": word.get("start", 0),
                    "end": word.get("end", 0)
                })
            segments.append(segment_data)
        
        return {
            "text": result.get("text", "").strip(),
            "language": result.get("language", "en"),
            "segments": segments
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
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
