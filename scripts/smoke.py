"""冒烟：登录 → 上传 → 问答引用 → 密级隔离 → 工作区隔离。"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000/api/v1"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "travel_policy.md"
FIXTURE_V2 = ROOT / "fixtures" / "travel_policy_v2.md"
FIXTURE_TABLE = ROOT / "fixtures" / "expense_grades.md"


def _login(client: httpx.Client, username: str, password: str) -> dict:
    r = client.post(f"{API}/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()


def _headers(token: str, workspace_id: int | None = None) -> dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if workspace_id is not None:
        h["X-Workspace-Id"] = str(workspace_id)
    return h


def _wait_ready(client: httpx.Client, headers: dict, doc_id: int) -> dict:
    """等到 ready；retired/过期则清有效期并 reingest，继续轮询。"""
    revived = False
    for _ in range(90):
        d = client.get(f"{API}/documents/{doc_id}", headers=headers).json()
        print(
            f"  status={d['status']} progress={d['progress']} "
            f"current={d.get('is_current')} validity={d.get('validity')}"
        )
        if d["status"] == "ready" and d.get("is_current") is not False:
            return d
        if d["status"] == "failed":
            raise RuntimeError(f"ingest failed: {d.get('error_message')}")
        # 退休 / 历史稿 / 过期：尽量恢复为现行 ready
        if (
            not revived
            and (
                d["status"] == "retired"
                or d.get("is_current") is False
                or d.get("validity") in {"expired", "retired"}
            )
        ):
            revived = True
            client.patch(
                f"{API}/documents/{doc_id}/validity",
                headers=headers,
                json={"valid_from": None, "valid_to": None},
            ).raise_for_status()
            # 历史稿无法靠 validity 变回 current；归并测用新上传即可
            if d.get("is_current") is False:
                return d
            client.post(f"{API}/documents/{doc_id}/reingest", headers=headers).raise_for_status()
        time.sleep(0.5)
    raise TimeoutError(f"timeout waiting ready doc={doc_id}")


def _upload(
    client: httpx.Client,
    headers: dict,
    path: Path,
    classification: int = 2,
) -> dict:
    with path.open("rb") as f:
        resp = client.post(
            f"{API}/documents/upload",
            headers=headers,
            data={"classification": str(classification)},
            files={"file": (path.name, f, "text/markdown")},
        )
    resp.raise_for_status()
    return resp.json()


def _upload_unique(
    client: httpx.Client,
    headers: dict,
    path: Path,
    classification: int = 2,
    suffix: str = "",
) -> dict:
    """避免 SHA 去重：追加唯一尾巴后上传临时文件。"""
    text = path.read_text(encoding="utf-8")
    stamp = f"\n\n<!-- smoke {time.time_ns()} {suffix} -->\n"
    tmp = ROOT / "fixtures" / f"_smoke_{path.stem}_{int(time.time())}.md"
    tmp.write_text(text + stamp, encoding="utf-8")
    try:
        return _upload(client, headers, tmp, classification=classification)
    finally:
        tmp.unlink(missing_ok=True)


def _wait_merge_suggestion(
    client: httpx.Client,
    headers: dict,
    newer_id: int,
    older_id: int | None = None,
    timeout_s: float = 20.0,
) -> dict | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        sug = client.get(
            f"{API}/documents/merge-suggestions",
            headers=headers,
            params={"status": "pending"},
        )
        sug.raise_for_status()
        items = sug.json()
        if older_id is not None:
            match = next(
                (
                    s
                    for s in items
                    if s["newer_doc_id"] == newer_id and s["older_doc_id"] == older_id
                ),
                None,
            )
        else:
            match = next((s for s in items if s["newer_doc_id"] == newer_id), None)
        if match:
            return match
        time.sleep(0.5)
    return None


def main() -> int:
    if not FIXTURE.exists():
        print("missing fixture, run: make fixtures")
        return 1

    with httpx.Client(timeout=60.0) as client:
        h = client.get(f"{API}/health")
        h.raise_for_status()
        print("health:", h.json())

        # --- login admin ---
        admin = _login(client, "admin", "admin123")
        workspaces = admin["workspaces"]
        if len(workspaces) < 2:
            print("FAIL: admin should have >=2 workspaces (restart API to re-seed)")
            return 10
        ws_default = next(w for w in workspaces if w["name"] == "默认工作区")
        ws_iso = next(w for w in workspaces if w["name"] == "制度隔离区")
        admin_h = _headers(admin["access_token"], ws_default["id"])
        print(f"admin workspaces: {[w['name'] for w in workspaces]}")

        # --- upload L2 into default（唯一内容，避免历史库 SHA/归并态干扰）---
        doc = _upload_unique(client, admin_h, FIXTURE, classification=2, suffix="base")
        doc_id = doc["id"]
        print("uploaded L2:", doc_id, "dedup=", doc.get("deduplicated"))
        ready = _wait_ready(client, admin_h, doc_id)
        if ready.get("is_current") is False:
            print("FAIL: baseline doc is not current after upload", ready)
            return 3

        # --- SSE chat with citations ---
        saw_citation = False
        answer_bits: list[str] = []
        with client.stream(
            "POST",
            f"{API}/chat",
            headers=admin_h,
            json={"message": "差旅住宿标准是多少？"},
            timeout=60.0,
        ) as stream:
            for line in stream.iter_lines():
                if not line:
                    continue
                print(line)
                if line.startswith("data: ") and "citations" in line:
                    payload = json.loads(line[6:])
                    cites = payload.get("blocks", [{}])[0].get("citations") or []
                    if cites:
                        saw_citation = True
                if line.startswith("data: ") and "delta" in line:
                    try:
                        answer_bits.append(json.loads(line[6:]).get("delta") or "")
                    except json.JSONDecodeError:
                        pass
        print("--- answer ---")
        print("".join(answer_bits)[:500])
        if not saw_citation:
            print("FAIL: no citations")
            return 4
        print("PASS: chat + citations")

        # --- upload L4 secret, member must not see ---
        secret = _upload(client, admin_h, FIXTURE, classification=4)
        # may dedupe by sha within WS — force unique content if deduped
        if secret.get("deduplicated"):
            tmp = ROOT / "fixtures" / "_smoke_secret.md"
            tmp.write_text(
                FIXTURE.read_text(encoding="utf-8") + "\n\n## 机密附录\n仅 L4 可见。\n",
                encoding="utf-8",
            )
            secret = _upload(client, admin_h, tmp, classification=4)
            tmp.unlink(missing_ok=True)
        secret_id = secret["id"]
        print("uploaded L4:", secret_id)
        _wait_ready(client, admin_h, secret_id)

        member = _login(client, "member", "member123")
        member_h = _headers(member["access_token"], ws_default["id"])
        listed = client.get(f"{API}/documents", headers=member_h).json()
        member_ids = {d["id"] for d in listed}
        if secret_id in member_ids:
            print("FAIL: member listed L4 document")
            return 5
        print("PASS: clearance list filter (member cannot see L4)")

        hit = client.get(
            f"{API}/chat/hit-test",
            headers=member_h,
            params={"q": "差旅住宿"},
        )
        hit.raise_for_status()
        hit_docs = {h.get("doc_id") for h in hit.json().get("injected", [])}
        if secret_id in hit_docs:
            print("FAIL: member hit-test returned L4 chunk")
            return 6
        print("PASS: clearance retrieve filter")

        # --- workspace isolation: secret not in 制度隔离区 ---
        iso_h = _headers(admin["access_token"], ws_iso["id"])
        iso_list = client.get(f"{API}/documents", headers=iso_h).json()
        if any(d["id"] == doc_id or d["id"] == secret_id for d in iso_list):
            print("FAIL: default-WS docs leaked into 制度隔离区")
            return 7
        print("PASS: workspace list isolation")

        # member cannot use 制度隔离区
        bad = client.get(
            f"{API}/documents",
            headers=_headers(member["access_token"], ws_iso["id"]),
        )
        if bad.status_code not in (403, 404):
            print(f"FAIL: member access to 制度隔离区 expected 403, got {bad.status_code}")
            return 8
        print("PASS: workspace membership gate")

        # --- merge: upload similar v2, confirm, old doc must drop from retrieve ---
        if not FIXTURE_V2.exists():
            print("FAIL: missing fixtures/travel_policy_v2.md")
            return 14
        v2 = _upload_unique(client, admin_h, FIXTURE_V2, classification=2, suffix="v2")
        v2_id = v2["id"]
        print("uploaded v2:", v2_id, "dedup=", v2.get("deduplicated"))
        _wait_ready(client, admin_h, v2_id)
        match = _wait_merge_suggestion(client, admin_h, newer_id=v2_id, older_id=doc_id)
        if not match:
            match = _wait_merge_suggestion(client, admin_h, newer_id=v2_id, older_id=None)
        if not match:
            print("FAIL: no merge suggestion for v2")
            return 15
        print(
            f"merge hint: #{match['id']} {match['strength']} score={match['score']} "
            f"older={match['older_doc_id']}"
        )
        older_id = match["older_doc_id"]
        conf = client.post(
            f"{API}/documents/merge-suggestions/{match['id']}/confirm",
            headers=admin_h,
        )
        conf.raise_for_status()
        older = client.get(f"{API}/documents/{older_id}", headers=admin_h).json()
        if older.get("is_current") is not False:
            print("FAIL: older doc still current after merge", older)
            return 16
        hit_m = client.get(
            f"{API}/chat/hit-test",
            headers=admin_h,
            params={"q": "差旅住宿标准"},
        )
        hit_m.raise_for_status()
        hit_m_docs = {h.get("doc_id") for h in hit_m.json().get("injected", [])}
        if older_id in hit_m_docs:
            print("FAIL: superseded doc still retrieved", hit_m_docs)
            return 17
        print("PASS: merge confirm + is_current retrieve filter")

        # --- validity: expire v2, retrieve must miss it ---
        past = "2020-01-01T00:00:00+00:00"
        vr = client.patch(
            f"{API}/documents/{v2_id}/validity",
            headers=admin_h,
            json={"valid_from": None, "valid_to": past},
        )
        vr.raise_for_status()
        if vr.json().get("validity") not in {"expired", "retired"}:
            print("FAIL: validity not expired after patch", vr.json())
            return 11
        hit2 = client.get(
            f"{API}/chat/hit-test",
            headers=admin_h,
            params={"q": "差旅住宿标准"},
        )
        hit2.raise_for_status()
        hit2_docs = {h.get("doc_id") for h in hit2.json().get("injected", [])}
        if v2_id in hit2_docs:
            print("FAIL: expired document still retrieved")
            return 12
        print("PASS: validity retrieve filter")

        # restore validity so local KB usable after smoke
        client.patch(
            f"{API}/documents/{v2_id}/validity",
            headers=admin_h,
            json={"valid_from": None, "valid_to": None},
        ).raise_for_status()

        audits = client.get(f"{API}/audit", headers=admin_h, params={"limit": 30})
        audits.raise_for_status()
        actions = {a["action"] for a in audits.json().get("items", [])}
        if "document.merge_confirm" not in actions and "document.validity" not in actions:
            print("FAIL: audit log missing merge/validity", actions)
            return 13
        print("PASS: audit log written")

        # --- C-011 table full inject ---
        if not FIXTURE_TABLE.exists():
            print("FAIL: missing fixtures/expense_grades.md")
            return 18
        tab = _upload(client, admin_h, FIXTURE_TABLE, classification=2)
        tab_id = tab["id"]
        print("uploaded table fixture:", tab_id, "dedup=", tab.get("deduplicated"))
        _wait_ready(client, admin_h, tab_id)
        chunks = client.get(
            f"{API}/documents/{tab_id}/chunks",
            headers=admin_h,
        )
        chunks.raise_for_status()
        chunk_items = chunks.json() if isinstance(chunks.json(), list) else chunks.json().get("items", [])
        if not any(c.get("is_table") for c in chunk_items):
            print("FAIL: expense_grades has no is_table chunk", chunk_items[:3])
            return 19
        print("PASS: table chunk marked is_table")
        hit_t = client.get(
            f"{API}/chat/hit-test",
            headers=admin_h,
            params={"q": "P4 住宿上限一线城市"},
        )
        hit_t.raise_for_status()
        ht = hit_t.json()
        meta = ht.get("meta") or {}
        inj = ht.get("injected") or []
        table_blocks = [b for b in inj if b.get("is_table") or b.get("table_full_inject")]
        if not meta.get("table_full_inject") and not table_blocks:
            print("FAIL: table full inject not triggered", meta, [b.get("title") for b in inj])
            return 20
        # 注入序：表格块应排在前面
        if table_blocks and inj and not (inj[0].get("is_table") or inj[0].get("table_full_inject")):
            print("FAIL: table block not preferred first", inj[0])
            return 21
        body0 = (table_blocks[0].get("content") or "") if table_blocks else ""
        if "P7+" not in body0 or "总监" not in body0:
            print("FAIL: injected table content truncated/missing rows", body0[:200])
            return 22
        print("PASS: table full inject (is_table first + full markdown)")

        print(
            "PASS: smoke ok (auth + cite + clearance + workspace + merge + validity + audit + table)"
        )
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print("FAIL:", e)
        sys.exit(9)
