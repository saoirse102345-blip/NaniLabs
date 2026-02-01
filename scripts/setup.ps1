# NaniLabs - Development Setup Script (Windows)
# Run this to set up your development environment

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  NaniLabs Development Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"
$ROOT_DIR = Split-Path -Parent $PSScriptRoot

# Check prerequisites
Write-Host "[1/6] Checking prerequisites..." -ForegroundColor Yellow

# Check Node.js
try {
    $nodeVersion = node --version
    Write-Host "  ✓ Node.js: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Node.js not found. Please install from https://nodejs.org" -ForegroundColor Red
    exit 1
}

# Check Python
try {
    $pythonVersion = python --version
    Write-Host "  ✓ Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found. Please install from https://python.org" -ForegroundColor Red
    exit 1
}

# Install HIVE dependencies
Write-Host ""
Write-Host "[2/6] Installing HIVE dependencies..." -ForegroundColor Yellow
Set-Location "$ROOT_DIR\hive-app"
npm install
Write-Host "  ✓ HIVE dependencies installed" -ForegroundColor Green

# Install AURA Infra dependencies
Write-Host ""
Write-Host "[3/6] Installing AURA Infra dependencies..." -ForegroundColor Yellow
Set-Location "$ROOT_DIR\aura-infra"
pip install -r requirements.txt
Write-Host "  ✓ AURA Infra dependencies installed" -ForegroundColor Green

# Install NEXUS Mail dependencies
Write-Host ""
Write-Host "[4/6] Installing NEXUS Mail dependencies..." -ForegroundColor Yellow
Set-Location "$ROOT_DIR\nexus-mail"
pip install -r requirements.txt
Write-Host "  ✓ NEXUS Mail dependencies installed" -ForegroundColor Green

# Install Autonomous Agents dependencies
Write-Host ""
Write-Host "[5/6] Installing Autonomous Agents dependencies..." -ForegroundColor Yellow
Set-Location "$ROOT_DIR\autonomous-agents"
pip install -r requirements.txt
Write-Host "  ✓ Autonomous Agents dependencies installed" -ForegroundColor Green

# Create .env files
Write-Host ""
Write-Host "[6/6] Setting up environment files..." -ForegroundColor Yellow

$envTemplate = @"
# NaniLabs Environment Configuration
# Copy this to .env and fill in your values

# Claude API (for AURA Agents)
ANTHROPIC_API_KEY=your_key_here

# Database URLs (defaults work for development)
# DATABASE_URL=sqlite:///./data/aura_infra.db

# Agent Configuration
DAILY_REVENUE_TARGET=100
CYCLE_INTERVAL_SECONDS=60
DEMO_MODE=true
"@

if (-not (Test-Path "$ROOT_DIR\autonomous-agents\.env")) {
    $envTemplate | Out-File -FilePath "$ROOT_DIR\autonomous-agents\.env" -Encoding utf8
    Write-Host "  ✓ Created autonomous-agents/.env" -ForegroundColor Green
} else {
    Write-Host "  - autonomous-agents/.env already exists" -ForegroundColor Gray
}

Set-Location $ROOT_DIR

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start all services, run:" -ForegroundColor White
Write-Host "  .\start-all.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "Or start individually:" -ForegroundColor White
Write-Host "  HIVE:        cd hive-app && npm run dev" -ForegroundColor Gray
Write-Host "  AURA Infra:  cd aura-infra/src && uvicorn api:app --reload --port 8001" -ForegroundColor Gray
Write-Host "  NEXUS Mail:  cd nexus-mail/src && uvicorn api:app --reload --port 8002" -ForegroundColor Gray
Write-Host "  AURA Agent:  cd autonomous-agents && python run.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor White
Write-Host "  HIVE:        http://localhost:3000" -ForegroundColor Cyan
Write-Host "  AURA Infra:  http://localhost:8001 (docs: /docs)" -ForegroundColor Cyan
Write-Host "  NEXUS Mail:  http://localhost:8002 (docs: /docs)" -ForegroundColor Cyan
Write-Host "  AURA Agent:  http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
