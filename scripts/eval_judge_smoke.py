"""真 LLM 裁判冒烟：探测 llama-server，可跑则 EVAL 1 条并打印 engine。

用法（需 LLM 在 .env 的 LLM_BASE_URL，默认 :8080）：
  $env:EVAL_LLM_JUDGE='1'
  server\\.venv\\Scripts\\python scripts\\eval_judge_smoke.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

API = os.environ.get("ZHISHU_API", "http://127.0.0.1:8000/api/v1")


def main() -> int:
    from app.core.config import get_settings

    s = get_settings()
    llm = s.llm_base_url.rstrip("/") + "/models"
    try:
        r = httpx.get(llm, timeout=3.0)
        r.raise_for_status()
        print("LLM ok:", llm, r.text[:120])
    except Exception as e:  # noqa: BLE001
        print("SKIP LLM unreachable:", e)
        print("Start llama-server then set EVAL_LLM_JUDGE=1 and re-run.")
        return 0

    os.environ["EVAL_LLM_JUDGE"] = "1"
    # 清 settings 缓存
    get_settings.cache_clear()

    login = httpx.post(
        f"{API}/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=30.0,
    )
    login.raise_for_status()
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}", "X-Workspace-Id": "1"}
    sets = httpx.get(f"{API}/eval/sets", headers=h, timeout=30.0).json().get("items") or []
    if not sets:
        print("FAIL no eval sets")
        return 2
    run = httpx.post(
        f"{API}/eval/sets/{sets[0]['id']}/run",
        headers=h,
        params={"limit": 1},
        timeout=180.0,
    )
    run.raise_for_status()
    body = run.json()
    m = body.get("metrics") or {}
    print(json.dumps({"status": body.get("status"), "metrics": m, "id": body.get("id")}, ensure_ascii=False))
    eng = m.get("engine")
    if eng in {"llm_judge", "llm_judge_fallback"}:
        print("PASS engine=", eng)
        return 0 if eng == "llm_judge" else 3
    print("FAIL unexpected engine", eng)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
