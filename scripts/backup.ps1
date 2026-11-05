# 知枢 C-202：备份 SQLite 库 + files 卷（stub/单机）
# 用法：.\scripts\backup.ps1 [-Tag note]
param(
    [string]$Root = (Split-Path $PSScriptRoot -Parent),
    [string]$Tag = ""
)

$ErrorActionPreference = "Stop"
Set-Location $Root

$data = Join-Path $Root "data"
$db = Join-Path $data "zhishu.db"
$files = Join-Path $data "files"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if ($Tag) { $stamp = "$stamp-$Tag" }
$dest = Join-Path $data "backups\$stamp"

New-Item -ItemType Directory -Force -Path $dest | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dest "files") | Out-Null

if (-not (Test-Path $db)) {
    Write-Error "missing database: $db"
}

# SQLite 热备：优先 online backup API，失败则文件拷贝
$py = Join-Path $Root "server\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$destDb = Join-Path $dest "zhishu.db"
& $py -c @"
import sqlite3, shutil, sys
src = r'$($db -replace "'","''")'
dst = r'$($destDb -replace "'","''")'
try:
    s = sqlite3.connect(src)
    d = sqlite3.connect(dst)
    s.backup(d)
    d.close(); s.close()
    print('sqlite-backup-api ok')
except Exception as e:
    shutil.copy2(src, dst)
    print('sqlite-copy-fallback', e)
"@
if ($LASTEXITCODE -ne 0) { throw "sqlite backup failed" }

# wal/shm 若存在一并带走（copy 路径更稳）
foreach ($ext in @("-wal", "-shm")) {
    $side = "$db$ext"
    if (Test-Path $side) {
        Copy-Item $side (Join-Path $dest ("zhishu.db" + $ext)) -Force
    }
}

if (Test-Path $files) {
    Copy-Item -Path (Join-Path $files "*") -Destination (Join-Path $dest "files") -Recurse -Force -ErrorAction SilentlyContinue
}

$manifest = @{
    created_at = (Get-Date).ToString("o")
    kind       = "sqlite+files"
    db_bytes   = (Get-Item $destDb).Length
    files_count = @(Get-ChildItem (Join-Path $dest "files") -Recurse -File -ErrorAction SilentlyContinue).Count
    source_db  = $db
    note       = "C-202 stub backup"
} | ConvertTo-Json
Set-Content -Path (Join-Path $dest "manifest.json") -Value $manifest -Encoding UTF8

Write-Host "backup ok: $dest" -ForegroundColor Green
Write-Host "db=$($manifest | ConvertFrom-Json | Select-Object -ExpandProperty db_bytes) bytes  files=$($manifest | ConvertFrom-Json | Select-Object -ExpandProperty files_count)"
Write-Output $dest
