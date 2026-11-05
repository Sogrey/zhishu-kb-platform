# ZhiShu stop local API / frontend
$ErrorActionPreference = "SilentlyContinue"

function Stop-Port {
  param([int]$Port)
  $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  foreach ($c in $conns) {
    $procId = $c.OwningProcess
    if ($procId -and $procId -ne 0) {
      Write-Host ("stop port " + $Port + " (PID " + $procId + ")")
      Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
  }
}

Stop-Port -Port 8000
Stop-Port -Port 5173
Write-Host "freed 8000 / 5173" -ForegroundColor Green
