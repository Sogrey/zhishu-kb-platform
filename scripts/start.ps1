# ZhiShu one-click start (Windows PowerShell)
# Run from repo root: .\scripts\start.ps1
# Or double-click start.bat

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "======= ZhiShu start =======" -ForegroundColor Cyan
Write-Host ("Repo: " + $Root)

# 1) .env
if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "[ok] created .env from .env.example" -ForegroundColor Green
} else {
  Write-Host "[ok] .env exists"
}

# 2) Python venv + deps
$Py = Join-Path $Root "server\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
  Write-Host "[..] creating Python venv..."
  python -m venv "server\.venv"
  if (-not (Test-Path $Py)) {
    throw "venv failed; install Python 3.12+"
  }
}
Write-Host "[..] installing Python deps..."
& $Py -m pip install -r "server\requirements.txt" -q
Write-Host "[ok] Python ready" -ForegroundColor Green

# 3) frontend deps
if (-not (Test-Path "frontend\node_modules\vue")) {
  Write-Host "[..] npm install..."
  Push-Location "frontend"
  try {
    npm install --registry=https://registry.npmmirror.com
  } finally {
    Pop-Location
  }
  Write-Host "[ok] frontend ready" -ForegroundColor Green
} else {
  Write-Host "[ok] node_modules exists"
}

# 4) free ports
function Stop-Port {
  param([int]$Port)
  $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  foreach ($c in $conns) {
    $procId = $c.OwningProcess
    if ($procId -and $procId -ne 0) {
      Write-Host ("[..] free port " + $Port + " (PID " + $procId + ")")
      Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
  }
}
Stop-Port -Port 8000
Stop-Port -Port 5173
Start-Sleep -Seconds 1

# 5) start API window
$apiCmd = "`$env:PYTHONPATH='server'; Set-Location '$Root'; Write-Host 'ZhiShu API http://127.0.0.1:8000' -ForegroundColor Green; & '$Py' -m uvicorn app.main:app --app-dir server --reload --host 127.0.0.1 --port 8000"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-Command",$apiCmd | Out-Null
Write-Host "[ok] API window opened" -ForegroundColor Green

# 6) start frontend window
$feDir = Join-Path $Root "frontend"
$feCmd = "Set-Location '$feDir'; Write-Host 'ZhiShu UI http://127.0.0.1:5173' -ForegroundColor Green; npm run dev -- --host 127.0.0.1 --port 5173"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-Command",$feCmd | Out-Null
Write-Host "[ok] frontend window opened" -ForegroundColor Green

# 7) wait + open browser
Write-Host "[..] waiting for API..."
$ok = $false
for ($i = 0; $i -lt 40; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) {
      $ok = $true
      break
    }
  } catch {
    Start-Sleep -Milliseconds 500
  }
}
if ($ok) {
  Write-Host "[ok] API health OK" -ForegroundColor Green
} else {
  Write-Host "[!] API not ready yet; check API window" -ForegroundColor Yellow
}

Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:5173/login"

Write-Host ""
Write-Host "======= done =======" -ForegroundColor Cyan
Write-Host "UI : http://127.0.0.1:5173"
Write-Host "API: http://127.0.0.1:8000"
Write-Host "login: admin / admin123 (L4)"
Write-Host "       member / member123 (L2)"
Write-Host "stop : close windows, or .\scripts\stop.ps1"
Write-Host ""
