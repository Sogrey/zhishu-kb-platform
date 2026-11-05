# 知枢 C-202：从 data/backups/<stamp> 恢复 SQLite + files
# 用法：先 stop.ps1，再 .\scripts\restore.ps1 -BackupDir data\backups\yyyyMMdd-HHmmss
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDir,
    [string]$Root = (Split-Path $PSScriptRoot -Parent),
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-Location $Root

if (-not [System.IO.Path]::IsPathRooted($BackupDir)) {
    $BackupDir = Join-Path $Root $BackupDir
}
$srcDb = Join-Path $BackupDir "zhishu.db"
$srcFiles = Join-Path $BackupDir "files"
if (-not (Test-Path $srcDb)) { Write-Error "missing $srcDb" }

$data = Join-Path $Root "data"
$db = Join-Path $data "zhishu.db"
$files = Join-Path $data "files"

# 占用检测：8000 有监听则拒恢复
try {
    $busy = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($busy -and -not $Force) {
        Write-Error "API port 8000 is listening. Run .\scripts\stop.ps1 first, or -Force (危险)."
    }
} catch {
    # Get-NetTCPConnection 不可用时跳过
}

$safety = Join-Path $data ("pre-restore-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Force -Path $safety | Out-Null
if (Test-Path $db) {
    Copy-Item $db (Join-Path $safety "zhishu.db") -Force
}
if (Test-Path $files) {
    Copy-Item $files (Join-Path $safety "files") -Recurse -Force
}
Write-Host "safety copy -> $safety" -ForegroundColor Yellow

New-Item -ItemType Directory -Force -Path $data | Out-Null
Copy-Item $srcDb $db -Force
foreach ($ext in @("-wal", "-shm")) {
    $side = Join-Path $BackupDir ("zhishu.db" + $ext)
    $target = "$db$ext"
    if (Test-Path $side) { Copy-Item $side $target -Force }
    elseif (Test-Path $target) { Remove-Item $target -Force }
}

if (Test-Path $files) { Remove-Item $files -Recurse -Force }
New-Item -ItemType Directory -Force -Path $files | Out-Null
if (Test-Path $srcFiles) {
    Copy-Item (Join-Path $srcFiles "*") $files -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "restore ok from $BackupDir" -ForegroundColor Green
Write-Host "restart: .\scripts\start.ps1"
