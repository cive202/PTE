# Helper script to build and run the ASR/Grammar Docker container

$ErrorActionPreference = "Stop"

$IMAGE_NAME = "pte-asr-grammar"
$CONTAINER_NAME = "pte-asr-grammar-service"
$PORT = 8000
$DOCKER_DIR = "PTE_ASR_GRAMMAR_DOCKER"

Write-Host "Building Docker image '$IMAGE_NAME' from $DOCKER_DIR..."
docker build -t $IMAGE_NAME $DOCKER_DIR

# Check if container exists and remove it
if (docker ps -a --format '{{.Names}}' | Select-String -Pattern "^$CONTAINER_NAME$") {
    Write-Host "Removing existing container '$CONTAINER_NAME'..."
    docker rm -f $CONTAINER_NAME
}

Write-Host "Starting container '$CONTAINER_NAME' on port $PORT..."
docker run -d -p "$PORT`:8000" --name $CONTAINER_NAME $IMAGE_NAME

Write-Host "Waiting for service to initialize..."
Start-Sleep -Seconds 5

Write-Host "Checking service health..."
try {
    $response = Invoke-RestMethod -Uri "http://localhost:$PORT/health" -Method Get
    Write-Host "Service Status: $($response.status)"
    Write-Host "Whisper Loaded: $($response.whisper)"
    Write-Host "LanguageTool Loaded: $($response.language_tool)"
} catch {
    Write-Host "Failed to connect to service. Check logs:"
    docker logs $CONTAINER_NAME
}

Write-Host "`nTo view logs: docker logs -f $CONTAINER_NAME"
Write-Host "To stop: docker stop $CONTAINER_NAME"
