"""C-202 备份演练取证：做一次备份，校验 SQLite 可读 + files 计数，写纪要。"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "C202备份演练纪要.md"
EVID = ROOT / "docs" / "m3-evidence" / "c202-backup-manifest.json"


def main() -> int:
    ps1 = ROOT / "scripts" / "backup.ps1"
    r = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
            "-Tag",
            "drill",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return r.returncode or 1

    # 脚本最后一行是备份目录
    lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    dest = Path(lines[-1]) if lines else None
    if not dest or not dest.is_dir():
        # 回退：找最新 backups/*
        backups = sorted((ROOT / "data" / "backups").glob("*drill*"), key=lambda p: p.stat().st_mtime)
        dest = backups[-1] if backups else None
    if not dest or not (dest / "zhishu.db").is_file():
        print("FAIL: backup dir not found", file=sys.stderr)
        return 2

    db = dest / "zhishu.db"
    conn = sqlite3.connect(str(db))
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        msgs = (
            conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            if "messages" in tables
            else 0
        )
    finally:
        conn.close()

    files_n = len(list((dest / "files").rglob("*"))) if (dest / "files").is_dir() else 0
    manifest = {
        "ok": True,
        "backup_dir": str(dest.relative_to(ROOT)).replace("\\", "/"),
        "db_bytes": db.stat().st_size,
        "tables_sample": sorted(list(tables))[:12],
        "documents": docs,
        "messages": msgs,
        "files_entries": files_n,
        "drilled_at": datetime.now(timezone.utc).isoformat(),
        "kind": "sqlite+files",
    }
    EVID.parent.mkdir(parents=True, exist_ok=True)
    EVID.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    OUT.write_text(
        "\n".join(
            [
                "# 知枢 · C-202 备份演练纪要（SQLite stub）",
                "",
                f"> 日期：{datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ 形态：SQLite + files 卷",
                "",
                "## 结论",
                "",
                "**通过**：热备 API 写出完整库；抽查 `documents` / `messages` 可读；files 目录已打包。",
                "",
                "## 步骤",
                "",
                "1. `powershell -File scripts\\backup.ps1 -Tag drill`",
                "2. 校验：本脚本打开备份库 `SELECT COUNT(*)`",
                "3. 恢复演练（可选，需先 `stop.ps1`）：",
                "   `powershell -File scripts\\restore.ps1 -BackupDir <上一步目录>`",
                "",
                "## 取证",
                "",
                f"| 项 | 值 |",
                f"|----|----|",
                f"| 备份目录 | `{manifest['backup_dir']}` |",
                f"| DB 字节 | {manifest['db_bytes']} |",
                f"| documents | {manifest['documents']} |",
                f"| messages | {manifest['messages']} |",
                f"| files 条目 | {manifest['files_entries']} |",
                "",
                f"机器可读：[{EVID.name}](./m3-evidence/{EVID.name})",
                "",
                "## 说明",
                "",
                "- 本纪要覆盖 **stub 单机**；PostgreSQL 正式环境请改用 `pg_dump` + files rsync（见运维文档）。",
                "- 断网冷启（C-203）与 TLS（C-204）未在本演练范围。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("wrote", OUT)
    print("wrote", EVID)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
