#!/bin/bash
set -e

IMAGE_NAME="pte-asr-grammar"
CONTAINER_NAME="pte-asr-grammar-service"
PORT=8000
DOCKER_DIR="PTE_ASR_GRAMMAR_DOCKER"

echo "Building Docker image '$IMAGE_NAME' from $DOCKER_DIR..."
docker build -t $IMAGE_NAME $DOCKER_DIR

# Check if container exists and remove it
if [ "$(docker ps -a -q -f name=^/${CONTAINER_NAME}$)" ]; then
    echo "Removing existing container '$CONTAINER_NAME'..."
    docker rm -f $CONTAINER_NAME
fi

echo "Starting container '$CONTAINER_NAME' on port $PORT..."
docker run -d -p "${PORT}:8000" --name $CONTAINER_NAME $IMAGE_NAME

echo "Waiting for service to initialize..."
sleep 5

echo "Checking service health..."
# Loop a few times to give it a chance to start up
for i in {1..5}; do
    if curl -s "http://localhost:$PORT/health" | grep -q "status"; then
        echo "Service is UP!"
        curl -s "http://localhost:$PORT/health" | jq .
        break
    else
        echo "Waiting for health check (attempt $i/5)..."
        sleep 2
    fi
done

echo ""
echo "To view logs: docker logs -f $CONTAINER_NAME"
echo "To stop: docker stop $CONTAINER_NAME"
