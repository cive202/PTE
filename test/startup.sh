#!/bin/bash
set -e

# Resolve Project Root (Found inside test/, so go up one level)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "🚀 PTE Platform Startup Script"
echo "=========================================="
echo "Project Root: $PROJECT_ROOT"

# 1. Check/Start Docker Daemon
echo "[1/4] Checking Docker Daemon..."
if ! systemctl is-active --quiet docker; then
    echo "⚠️  Docker daemon is not running."
    echo "Attempting to start (sudo required)..."
    sudo systemctl start docker
    sleep 3
fi

if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to Docker daemon. Check permissions/status."
    exit 1
fi
echo "✅ Docker is running."

# 2. Start ASR Container
CONTAINER_NAME="pte-asr-grammar-service"
IMAGE_NAME="pte-asr-grammar"
PORT=8000

echo "[2/4] Checking ASR Service Container..."
if [ ! "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
        echo "Container exists but stopped. Starting..."
        docker start $CONTAINER_NAME > /dev/null
    else
        echo "Container does not exist. run ./build_and_run.sh first?"
        echo "Trying to run from image..."
        if [ "$(docker images -q $IMAGE_NAME)" ]; then
             docker run -d --name $CONTAINER_NAME -p $PORT:$PORT $IMAGE_NAME
        else
             echo "❌ Image $IMAGE_NAME not found. Please run ./build_and_run.sh first."
             exit 1
        fi
    fi
else
    echo "Container is already running."
fi

# 3. Health Check Loop
echo "[3/4] Waiting for Service Health (Whisper/LangTool)..."
MAX_RETRIES=60
COUNT=0
HEALTH_URL="http://localhost:8000/health"

start_time=$(date +%s)
until curl -s "$HEALTH_URL" | grep "ok" > /dev/null; do
    sleep 2
    COUNT=$((COUNT+1))
    elapsed=$(($(date +%s) - start_time))
    echo -ne "\rWaiting... ${elapsed}s (Services loading models)"
    
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo ""
        echo "❌ Timeout waiting for ASR service at $HEALTH_URL"
        echo "Check logs with: docker logs $CONTAINER_NAME"
        exit 1
    fi
done
echo ""
echo "✅ ASR Service is UP & Ready!"

# 4. Start Flask App
echo "[4/4] Starting Flask App..."
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ venv not found in $PROJECT_ROOT"
    exit 1
fi

echo "=========================================="
echo "🌐 App running at: http://localhost:5000"
echo "=========================================="

# Use exec so this script process is replaced by python
exec python api/app.py
