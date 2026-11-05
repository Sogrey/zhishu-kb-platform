"""M3 签收取证脚本（stub 环境可跑）。

对照开发计划 M3 签收清单：
FR-06/07/09/10/11/13 + 治理四动作 + 评测基线 + 密级漏检=0
FR-14 轻量自建 Trace（非 Langfuse）：问答落库 + GET /chat/traces/{id}
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000/api/v1"
ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "fixtures" / "travel_policy.md"
FX_V2 = ROOT / "fixtures" / "travel_policy_v2.md"
FX_TAB = ROOT / "fixtures" / "expense_grades.md"
FX_FAQ = ROOT / "fixtures" / "faq.txt"

RESULTS: list[dict] = []


def _ok(item: str, detail: str = "") -> None:
    RESULTS.append({"item": item, "pass": True, "detail": detail})
    print(f"PASS  {item}  {detail}")


def _fail(item: str, detail: str = "") -> None:
    RESULTS.append({"item": item, "pass": False, "detail": detail})
    print(f"FAIL  {item}  {detail}")


def _skip(item: str, detail: str = "") -> None:
    RESULTS.append({"item": item, "pass": None, "detail": detail})
    print(f"SKIP  {item}  {detail}")


def _login(c: httpx.Client, user: str, pwd: str) -> dict:
    r = c.post(f"{API}/auth/login", json={"username": user, "password": pwd})
    r.raise_for_status()
    return r.json()


def _hdr(token: str, ws: int) -> dict:
    return {"Authorization": f"Bearer {token}", "X-Workspace-Id": str(ws)}


def _wait_ready(c: httpx.Client, h: dict, doc_id: int) -> dict:
    for _ in range(80):
        d = c.get(f"{API}/documents/{doc_id}", headers=h).json()
        if d["status"] == "ready" and d.get("is_current") is not False:
            return d
        if d["status"] == "failed":
            raise RuntimeError(d.get("error_message"))
        if d["status"] == "retired" or d.get("validity") in {"expired", "retired"}:
            c.patch(
                f"{API}/documents/{doc_id}/validity",
                headers=h,
                json={"valid_from": None, "valid_to": None},
            )
            c.post(f"{API}/documents/{doc_id}/reingest", headers=h)
        time.sleep(0.4)
    raise TimeoutError(f"doc {doc_id} not ready")


def _upload_unique(c: httpx.Client, h: dict, path: Path, level: int = 2) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    tmp = ROOT / "fixtures" / f"_m3_{path.stem}_{time.time_ns()}.md"
    tmp.write_text(text + f"\n\n<!-- m3 {time.time_ns()} -->\n", encoding="utf-8")
    try:
        with tmp.open("rb") as f:
            r = c.post(
                f"{API}/documents/upload",
                headers=h,
                data={"classification": str(level)},
                files={"file": (tmp.name, f, "text/markdown")},
            )
        r.raise_for_status()
        return r.json()
    finally:
        tmp.unlink(missing_ok=True)


def main() -> int:
    if not FX.exists():
        print("missing fixtures")
        return 1

    with httpx.Client(timeout=180.0) as c:
        health = c.get(f"{API}/health").json()
        print("health:", health)

        admin = _login(c, "admin", "admin123")
        ws = next(w for w in admin["workspaces"] if w["name"] == "默认工作区")
        ah = _hdr(admin["access_token"], ws["id"])

        # --- FR-03/01 baseline upload ---
        base = _upload_unique(c, ah, FX, 2)
        base_id = base["id"]
        _wait_ready(c, ah, base_id)
        _ok("摄取闭环", f"doc#{base_id} ready")

        # --- FR-11 密级：L4 对 member 不可见 ---
        secret = _upload_unique(c, ah, FX, 4)
        secret_id = secret["id"]
        _wait_ready(c, ah, secret_id)
        member = _login(c, "member", "member123")
        mh = _hdr(member["access_token"], ws["id"])
        listed = {d["id"] for d in c.get(f"{API}/documents", headers=mh).json()}
        if secret_id in listed:
            _fail("密级列表过滤", f"member saw L4 #{secret_id}")
        else:
            _ok("密级列表过滤", "member 不可见 L4")
        hit = c.get(f"{API}/chat/hit-test", headers=mh, params={"q": "差旅住宿"}).json()
        hit_docs = {x.get("doc_id") for x in hit.get("injected") or []}
        if secret_id in hit_docs:
            _fail("密级检索过滤", "member hit-test 命中 L4")
        else:
            _ok("密级检索过滤 / 漏检=0（本用例）", "member 未命中 L4")

        # --- FR-06 表格全表注入 ---
        if FX_TAB.exists():
            tab = _upload_unique(c, ah, FX_TAB, 2)
            tab_id = tab["id"]
            _wait_ready(c, ah, tab_id)
            chunks = c.get(f"{API}/documents/{tab_id}/chunks", headers=ah).json()
            if not any(x.get("is_table") for x in chunks):
                _fail("FR-06 表格成块", "无 is_table chunk")
            else:
                _ok("FR-06 表格成块", f"doc#{tab_id}")
            ht = c.get(
                f"{API}/chat/hit-test",
                headers=ah,
                params={"q": "P4 住宿上限一线"},
            ).json()
            meta = ht.get("meta") or {}
            inj = ht.get("injected") or []
            if meta.get("table_full_inject") or any(x.get("is_table") for x in inj):
                body = (inj[0].get("content") if inj else "") or ""
                if "P7+" in body or "总监" in body or any(
                    "P7+" in (x.get("content") or "") for x in inj if x.get("is_table")
                ):
                    _ok("FR-06 表格全表注入", "注入含完整职级行")
                else:
                    _fail("FR-06 表格全表注入", "表格块内容不完整")
            else:
                _fail("FR-06 表格全表注入", str(meta))
        else:
            _skip("FR-06", "缺 expense_grades.md")

        # --- FR-07 Hit Test ---
        ht2 = c.get(
            f"{API}/chat/hit-test",
            headers=ah,
            params={"q": "差旅住宿标准是多少？", "persist": "true"},
        ).json()
        if ht2.get("id") and ht2.get("injected") is not None:
            _ok("FR-07 Hit Test", f"run#{ht2.get('id')} injected={len(ht2.get('injected') or [])}")
        else:
            _fail("FR-07 Hit Test", str(ht2)[:200])

        # --- FR-09 有效期 ---
        past = "2020-01-01T00:00:00+00:00"
        vr = c.patch(
            f"{API}/documents/{base_id}/validity",
            headers=ah,
            json={"valid_from": None, "valid_to": past},
        )
        vr.raise_for_status()
        state = vr.json().get("validity")
        hit3 = c.get(
            f"{API}/chat/hit-test",
            headers=ah,
            params={"q": "差旅住宿标准"},
        ).json()
        docs3 = {x.get("doc_id") for x in hit3.get("injected") or []}
        if state in {"expired", "retired"} and base_id not in docs3:
            _ok("FR-09 有效期过滤", f"validity={state}")
        else:
            _fail("FR-09 有效期过滤", f"validity={state} still_hit={base_id in docs3}")
        # restore
        c.patch(
            f"{API}/documents/{base_id}/validity",
            headers=ah,
            json={"valid_from": None, "valid_to": None},
        ).raise_for_status()
        c.post(f"{API}/documents/{base_id}/reingest", headers=ah)

        # --- FR-10 归并 ---
        if FX_V2.exists():
            # ensure base ready current again
            try:
                _wait_ready(c, ah, base_id)
            except Exception:
                base = _upload_unique(c, ah, FX, 2)
                base_id = base["id"]
                _wait_ready(c, ah, base_id)
            v2 = _upload_unique(c, ah, FX_V2, 2)
            v2_id = v2["id"]
            _wait_ready(c, ah, v2_id)
            match = None
            for _ in range(40):
                items = c.get(
                    f"{API}/documents/merge-suggestions",
                    headers=ah,
                    params={"status": "pending"},
                ).json()
                match = next(
                    (
                        s
                        for s in items
                        if s["newer_doc_id"] == v2_id and s["older_doc_id"] == base_id
                    ),
                    None,
                ) or next((s for s in items if s["newer_doc_id"] == v2_id), None)
                if match:
                    break
                time.sleep(0.4)
            if not match:
                _fail("FR-10 归并提示", "无 merge suggestion")
            else:
                older_id = match["older_doc_id"]
                c.post(
                    f"{API}/documents/merge-suggestions/{match['id']}/confirm",
                    headers=ah,
                ).raise_for_status()
                older = c.get(f"{API}/documents/{older_id}", headers=ah).json()
                hit4 = c.get(
                    f"{API}/chat/hit-test",
                    headers=ah,
                    params={"q": "差旅住宿标准"},
                ).json()
                docs4 = {x.get("doc_id") for x in hit4.get("injected") or []}
                if older.get("is_current") is False and older_id not in docs4:
                    _ok("FR-10 归并现行稿过滤", f"older#{older_id} superseded")
                else:
                    _fail("FR-10 归并", f"current={older.get('is_current')} hit={older_id in docs4}")
        else:
            _skip("FR-10", "缺 travel_policy_v2.md")

        # --- FR-11 审计导出 ---
        audits = c.get(f"{API}/audit", headers=ah, params={"limit": 50}).json()
        actions = {a["action"] for a in audits.get("items") or []}
        if actions & {
            "document.validity",
            "document.merge_confirm",
            "document.upload",
            "document.retire_scan",
        }:
            _ok("FR-11 审计可查", f"actions sample={sorted(list(actions))[:6]}")
        else:
            _fail("FR-11 审计", str(actions)[:200])
        # export endpoint existence
        exp = c.get(f"{API}/audit/export", headers=ah, params={"format": "json"})
        if exp.status_code == 200 and exp.content:
            _ok("审计导出", f"bytes={len(exp.content)}")
        else:
            _fail("审计导出", f"status={exp.status_code}")

        # 退休扫描
        rs = c.post(f"{API}/documents/retire-scan", headers=ah)
        if rs.status_code == 200:
            _ok("治理·退休扫描", rs.json())
        else:
            _fail("治理·退休扫描", rs.text[:120])

        # --- FR-13 评测基线 ---
        sets = c.get(f"{API}/eval/sets", headers=ah).json().get("items") or []
        if not sets or sets[0].get("case_count", 0) < 50:
            _fail("FR-13 金标规模", str(sets[:1]))
        else:
            _ok("FR-13 金标规模", f"{sets[0]['case_count']} 条")
            run = c.post(
                f"{API}/eval/sets/{sets[0]['id']}/run",
                headers=ah,
                params={"limit": 8},
            ).json()
            m = run.get("metrics") or {}
            need = {"pass_rate", "citation_hit", "context_recall", "answer_relevancy", "faithfulness"}
            if run.get("status") == "done" and need <= set(m):
                _ok(
                    "FR-13 评测四指标首报",
                    f"engine={m.get('engine')} pass_rate={m.get('pass_rate')} run#{run.get('id')}",
                )
            else:
                _fail("FR-13 评测跑通", str(run)[:240])
            dash = c.get(f"{API}/eval/dashboard", headers=ah).json()
            if dash.get("run_count", 0) >= 1:
                _ok("评测看板", f"runs={dash.get('run_count')}")
            else:
                _fail("评测看板", "no runs")

        # FAQ optional for product Q
        if FX_FAQ.exists():
            faq = _upload_unique(c, ah, FX_FAQ, 1)
            _wait_ready(c, ah, faq["id"])
            _ok("FAQ 样例入库", f"doc#{faq['id']}")

        # --- FR-14 轻量 Trace ---
        with c.stream(
            "POST",
            f"{API}/chat",
            headers={**ah, "Accept": "text/event-stream"},
            json={"message": "差旅住宿标准是多少？", "conversation_id": None},
            timeout=120.0,
        ) as stream:
            stream.raise_for_status()
            buf = ""
            trace_id = None
            event_name = "message"
            for chunk in stream.iter_text():
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("data:") and event_name in {
                        "conversation_meta",
                        "retrieve_meta",
                    }:
                        try:
                            payload = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        if payload.get("trace_id"):
                            trace_id = payload["trace_id"]
            if not trace_id:
                _fail("FR-14 Trace 落库", "SSE 无 trace_id")
            else:
                tr = c.get(f"{API}/chat/traces/{trace_id}", headers=ah)
                body = tr.json() if tr.status_code == 200 else {}
                spans = body.get("spans") or []
                names = {s.get("name") for s in spans if isinstance(s, dict)}
                if (
                    tr.status_code == 200
                    and body.get("id") == trace_id
                    and {"retrieve", "rerank_inject", "generate"} <= names
                ):
                    _ok(
                        "FR-14 轻量 Trace",
                        f"id={trace_id[:8]}… latency={body.get('latency_ms')}ms "
                        f"hit_test=#{body.get('hit_test_id')} engine={body.get('engine')}",
                    )
                else:
                    _fail("FR-14 Trace 详情", f"status={tr.status_code} body={str(body)[:200]}")

        # FE 手测：有截图证据则记 PASS，否则提醒补 docs/m3-evidence/
        evid = ROOT / "docs" / "m3-evidence"
        wm = evid / "c010-watermark-l4-chunks.png"
        gov = evid / "c013-governance-hub.png"
        if wm.is_file() and wm.stat().st_size > 1000:
            _ok("C-010 动态水印手测", f"evidence={wm.name} bytes={wm.stat().st_size}")
        else:
            _skip("C-010 动态水印手测", "缺 docs/m3-evidence/c010-watermark-l4-chunks.png")
        if gov.is_file() and gov.stat().st_size > 1000:
            _ok("C-013 治理导航手测", f"evidence={gov.name} bytes={gov.stat().st_size}")
        else:
            _skip("C-013 治理导航手测", "缺 docs/m3-evidence/c013-governance-hub.png")

    passed = sum(1 for r in RESULTS if r["pass"] is True)
    failed = sum(1 for r in RESULTS if r["pass"] is False)
    skipped = sum(1 for r in RESULTS if r["pass"] is None)
    print("---")
    print(f"summary pass={passed} fail={failed} skip={skipped}")

    out = ROOT / "docs" / "M3签收取证结果.json"
    out.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out)
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print("FAIL script:", e)
        raise SystemExit(9)
