FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
# docker.io is needed for the app to spawn sibling containers (Docker-in-Docker)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Start command
CMD ["python", "api/app.py"]
