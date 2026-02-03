# PTE Platform Startup Script for Windows

Write-Host "🚀 Starting PTE Practice Platform..." -ForegroundColor Cyan

# 1. Check ASR Service
Write-Host "📡 Checking ASR & Grammar Service (Port 8000)..."
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
    if ($response.status -eq "ok") {
        Write-Host "✅ ASR Service is ONLINE" -ForegroundColor Green
    } else {
        Write-Host "⚠️ ASR Service is running but reporting issues." -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ ASR Service is OFFLINE." -ForegroundColor Red
    Write-Host "Attempting to start ASR service locally..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\venv\Scripts\python PTE_ASR_GRAMMAR_DOCKER/app.py"
    Write-Host "Waiting for ASR service to initialize..."
    Start-Sleep -Seconds 10
}

# 2. Check MFA (Docker-based)
Write-Host "🔍 Checking Montreal Forced Aligner (Docker)..."
try {
    $dockerImage = "mmcauliffe/montreal-forced-aligner:latest"
    docker pull $dockerImage
    Write-Host "✅ MFA Docker image is ready." -ForegroundColor Green
} catch {
    Write-Host "⚠️ Docker not found or MFA image unavailable. Pronunciation analysis will be skipped (content only)." -ForegroundColor Yellow
}

# 3. Start Flask Application
Write-Host "🌐 Starting Web Interface (Port 5000)..."
.\venv\Scripts\python api/app.py
