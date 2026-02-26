FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# ffmpeg: audio conversion in api/app.py
# docker-cli: required for MFA `docker run` calls from API container
# libsndfile1: required by librosa/soundfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    docker-cli \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN sed '/^torch>=/d' /app/requirements.txt > /app/requirements.api.txt \
    && pip install --no-cache-dir "typing-extensions>=4.10.0" \
    && pip install --no-cache-dir --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cpu torch==2.6.0+cpu \
    && pip install --no-cache-dir -r /app/requirements.api.txt

# Copy runtime code only (data is mounted at runtime)
COPY api /app/api
COPY pte_core /app/pte_core
COPY read_aloud /app/read_aloud
COPY repeat_sentence /app/repeat_sentence
COPY src /app/src

EXPOSE 5000

CMD ["python", "api/app.py", "--port", "5000"]
