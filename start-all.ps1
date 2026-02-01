# NaniLabs - Start All Services
# Run this script to start the entire NaniLabs ecosystem

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  NaniLabs - Starting All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Start HIVE (Next.js on port 3000)
Write-Host "[1/3] Starting HIVE (Social Network)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\Nived\Projects\NaniLabs\hive-app; npm run dev" -WindowStyle Minimized

# Wait a bit
Start-Sleep -Seconds 2

# Start AURA Infra (FastAPI on port 8001)
Write-Host "[2/3] Starting AURA Infra (Wallets)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\Nived\Projects\NaniLabs\aura-infra\src; python -m uvicorn api:app --reload --port 8001" -WindowStyle Minimized

# Wait a bit
Start-Sleep -Seconds 2

# Start NEXUS Mail (FastAPI on port 8002)
Write-Host "[3/3] Starting NEXUS Mail (Communication)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\Nived\Projects\NaniLabs\nexus-mail\src; python -m uvicorn api:app --reload --port 8002" -WindowStyle Minimized

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  All Services Starting!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Services:" -ForegroundColor White
Write-Host "  - HIVE:       http://localhost:3000" -ForegroundColor Cyan
Write-Host "  - AURA Infra: http://localhost:8001" -ForegroundColor Cyan
Write-Host "  - NEXUS Mail: http://localhost:8002" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Docs:" -ForegroundColor White
Write-Host "  - AURA Infra: http://localhost:8001/docs" -ForegroundColor Gray
Write-Host "  - NEXUS Mail: http://localhost:8002/docs" -ForegroundColor Gray
Write-Host ""
Write-Host "Press any key to exit this window..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
