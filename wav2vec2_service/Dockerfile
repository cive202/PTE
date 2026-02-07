FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
# libsndfile1 is required by soundfile/librosa
# espeak-ng is required by phonemizer
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python dependencies
# Using the CPU version of PyTorch to reduce image size since the app runs on CPU
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

COPY app.py .
COPY phoneme_model.py .

# Pre-download the model during build so the image is self-contained
# This imports phoneme_model which triggers the download logic at module level
RUN python -c "import phoneme_model; print('Model pre-downloaded')"

EXPOSE 8001

CMD ["python", "app.py"]
