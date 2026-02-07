FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for soundfile and phonemizer
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install CPU-only torch to save space
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["python", "app.py"]
