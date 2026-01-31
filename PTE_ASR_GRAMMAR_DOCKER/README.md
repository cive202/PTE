# PTE ASR & Grammar Docker Service

Dockerized Whisper ASR and LanguageTool grammar checking service for the PTE Practice Platform.

## Services

### 1. Whisper ASR (Port 8000)

- **Model**: OpenAI Whisper (base model)
- **Purpose**: Speech-to-text transcription
- **Endpoint**: `POST /transcribe`
- **Input**: Audio file (WAV, MP3, WebM)
- **Output**: JSON with transcribed text

### 2. LanguageTool (Port 8010)

- **Purpose**: Grammar and spelling checking
- **Endpoint**: `POST /v2/check`
- **Languages**: English (US, UK, Indian)

## Quick Start

### Build and Run

```bash
docker-compose up -d
```

### Or build manually

```bash
docker build -t pte-asr-grammar .
docker run -d -p 8000:8000 -p 8010:8010 --name pte-asr-grammar-service pte-asr-grammar
```

### Test the service

```bash
# Test ASR
curl -X POST -F "audio=@test.wav" http://localhost:8000/transcribe

# Test LanguageTool
curl -X POST -d "text=This are a test" -d "language=en-US" http://localhost:8010/v2/check
```

## API Documentation

### Whisper ASR Endpoint

**POST** `/transcribe`

**Request:**

- Method: `multipart/form-data`
- Field: `audio` (file)

**Response:**

```json
{
  "text": "transcribed text here",
  "language": "en"
}
```

**Example:**

```python
import requests

with open('audio.wav', 'rb') as f:
    files = {'audio': ('audio.wav', f, 'audio/wav')}
    response = requests.post('http://localhost:8000/transcribe', files=files)
    print(response.json()['text'])
```

### LanguageTool Endpoint

**POST** `/v2/check`

**Request:**

- Method: `application/x-www-form-urlencoded`
- Fields:
  - `text`: Text to check
  - `language`: Language code (e.g., `en-US`)

**Response:**

```json
{
  "matches": [
    {
      "message": "Error description",
      "replacements": ["suggestion1", "suggestion2"],
      "offset": 0,
      "length": 4
    }
  ]
}
```

## Configuration

### Whisper Model

Default: `base` (fastest, good accuracy)

To change model, edit `app.py`:

```python
model = whisper.load_model("medium")  # Options: tiny, base, small, medium, large
```

### LanguageTool

- Auto-downloads on first run (~200MB)
- Cached in container for faster subsequent starts

## Resource Requirements

- **CPU**: 2+ cores recommended
- **RAM**: 2GB minimum, 4GB recommended
- **Disk**: 2GB for models and cache
- **First Start**: ~5 minutes (downloading models)
- **Subsequent Starts**: ~30 seconds

## Troubleshooting

### Container won't start

```bash
docker logs pte-asr-grammar-service
```

### LanguageTool download slow

- First run downloads ~200MB
- Be patient, it's a one-time download
- Check internet connection

### Out of memory

- Increase Docker memory limit to 4GB
- Use smaller Whisper model (`tiny` or `base`)

### Port conflicts

```bash
# Check what's using the port
lsof -i :8000
lsof -i :8010

# Change ports in docker-compose.yml
```

## Development

### Rebuild after changes

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### View logs

```bash
docker-compose logs -f
```

### Shell into container

```bash
docker exec -it pte-asr-grammar-service bash
```

## Updates

### Update Whisper

```bash
# In Dockerfile, change version
pip install openai-whisper==1.x.x
```

### Update LanguageTool

- Auto-updates on rebuild
- Or manually download new version

## Performance

### Whisper Transcription Speed

- **tiny**: ~1-2s per 10s audio
- **base**: ~2-4s per 10s audio
- **small**: ~4-8s per 10s audio
- **medium**: ~8-15s per 10s audio

### LanguageTool

- ~100-500ms per check
- Depends on text length

## Security

- Service runs on localhost only
- No authentication (local development)
- For production: Add API keys, rate limiting

## License

This Docker service uses:

- Whisper (MIT License)
- LanguageTool (LGPL License)
