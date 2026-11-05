from __future__ import annotations

import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.db import SessionLocal, get_db
from app.core.deps import AuthContext, get_auth
from app.models import Conversation, HitTestRun, Message, QaTrace
from app.rag.context_inject import prefer_full_tables, table_inject_meta
from app.rag.generate import build_citation_groups, stream_answer
from app.rag.hit_test_snap import persist_hit_test_run
from app.rag.qa_trace import bind_message, new_trace_id, persist_qa_trace
from app.rag.rerank import rerank
from app.rag.retrieve import hybrid_search
from app.schemas.document import ChatRequest

router = APIRouter()


def _require_hit_viewer(auth: AuthContext) -> None:
    if auth.user.role not in {"admin", "librarian", "auditor"}:
        raise HTTPException(403, "仅管理员/知识管理员/审计员可查看 Hit Test")


def _can_view_trace(auth: AuthContext, row: QaTrace) -> bool:
    if row.workspace_id != auth.workspace_id:
        return False
    if auth.user.role in {"admin", "librarian", "auditor"}:
        return True
    return row.user_id == auth.user.id


@router.post("")
def chat(
    body: ChatRequest,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    if body.conversation_id:
        conv = db.get(Conversation, body.conversation_id)
        if (
            not conv
            or conv.workspace_id != auth.workspace_id
            or (conv.user_id and conv.user_id != auth.user.id)
        ):
            raise HTTPException(404, "会话不存在")
    else:
        conv = Conversation(
            title=body.message[:40],
            workspace_id=auth.workspace_id,
            user_id=auth.user.id,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    conversation_id = conv.id
    db.add(Message(conversation_id=conversation_id, role="user", content=body.message))
    db.commit()

    trace_id = new_trace_id()
    t0 = time.perf_counter()

    fused, debug = hybrid_search(
        db,
        body.message,
        workspace_id=auth.workspace_id,
        clearance=auth.user.clearance,
        recall_k=50,
        top_k=20,
    )
    t_retrieve = time.perf_counter()

    hits = prefer_full_tables(rerank(body.message, fused, top_n=8))
    t_inject = time.perf_counter()

    citation_groups = build_citation_groups(hits)
    citations = citation_groups["sources"]
    answer_iter = list(stream_answer(body.message, hits))
    t_gen = time.perf_counter()

    # 问答链路同步落一条 Hit Test 快照，便于事后解释
    hit_run = persist_hit_test_run(
        db,
        query=body.message,
        workspace_id=auth.workspace_id,
        clearance=auth.user.clearance,
        user_id=auth.user.id,
        hits=hits,
        debug=debug,
        source="chat",
        conversation_id=conversation_id,
    )
    hit_run_id = hit_run.id

    full_answer = "".join(answer_iter)
    spans = [
        {
            "name": "retrieve",
            "status": "ok",
            "duration_ms": int((t_retrieve - t0) * 1000),
            "meta": {
                "vector_hits": len(debug.vector_ids),
                "keyword_hits": len(debug.keyword_ids),
                "fused": len(debug.fused_ids),
                "rrf_k": debug.rrf_k,
            },
        },
        {
            "name": "rerank_inject",
            "status": "ok",
            "duration_ms": int((t_inject - t_retrieve) * 1000),
            "meta": {
                "injected": len(hits),
                "table_chunks": sum(1 for h in hits if h.chunk.is_table),
            },
        },
        {
            "name": "generate",
            "status": "ok",
            "duration_ms": int((t_gen - t_inject) * 1000),
            "meta": {"answer_chars": len(full_answer), "citations": len(citations)},
        },
    ]
    persist_qa_trace(
        db,
        trace_id=trace_id,
        workspace_id=auth.workspace_id,
        user_id=auth.user.id,
        conversation_id=conversation_id,
        hit_test_id=hit_run_id,
        query=body.message,
        answer=full_answer,
        spans=spans,
        latency_ms=int((t_gen - t0) * 1000),
    )

    # SSE 生成器在请求 Session 关闭后执行，勿再访问 ORM 属性
    clearance = int(auth.user.clearance)
    workspace_id = int(auth.workspace_id)

    def event_gen() -> Iterator[dict]:
        yield {
            "event": "conversation_meta",
            "data": json.dumps(
                {
                    "conversation_id": conversation_id,
                    "hit_test_id": hit_run_id,
                    "trace_id": trace_id,
                },
                ensure_ascii=False,
            ),
        }
        yield {
            "event": "retrieve_meta",
            "data": json.dumps(
                {
                    "vector_hits": len(debug.vector_ids),
                    "keyword_hits": len(debug.keyword_ids),
                    "fused": len(debug.fused_ids),
                    "injected": len(hits),
                    "rrf_k": debug.rrf_k,
                    "clearance": clearance,
                    "workspace_id": workspace_id,
                    "hit_test_id": hit_run_id,
                    "trace_id": trace_id,
                },
                ensure_ascii=False,
            ),
        }
        yield {
            "event": "block_start",
            "data": json.dumps({"block_id": 1, "type": "text"}, ensure_ascii=False),
        }
        for delta in answer_iter:
            yield {
                "event": "block_delta",
                "data": json.dumps({"block_id": 1, "delta": delta}, ensure_ascii=False),
            }
        yield {
            "event": "block_replace",
            "data": json.dumps(
                {
                    "blocks": [
                        {
                            "type": "text",
                            "content": full_answer,
                            "citations": citations,
                            "citation_groups": citation_groups,
                            "trace_id": trace_id,
                            "hit_test_id": hit_run_id,
                        }
                    ]
                },
                ensure_ascii=False,
            ),
        }
        session = SessionLocal()
        try:
            msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_answer,
                citations={
                    "sources": citations,
                    "groups": citation_groups,
                    "retrieve": {
                        "vector_hits": len(debug.vector_ids),
                        "keyword_hits": len(debug.keyword_ids),
                        "injected": len(hits),
                        "hit_test_id": hit_run_id,
                        "trace_id": trace_id,
                    },
                },
            )
            session.add(msg)
            session.commit()
            session.refresh(msg)
            bind_message(session, trace_id, msg.id)
        finally:
            session.close()
        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(event_gen())


@router.get("/conversations")
def list_conversations(
    auth: AuthContext = Depends(get_auth), db: Session = Depends(get_db)
) -> list[dict]:
    rows = (
        db.query(Conversation)
        .filter(
            Conversation.workspace_id == auth.workspace_id,
            Conversation.user_id == auth.user.id,
        )
        .order_by(Conversation.id.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": c.id,
            "title": c.title or f"会话 {c.id}",
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    conv = db.get(Conversation, conversation_id)
    if (
        not conv
        or conv.workspace_id != auth.workspace_id
        or conv.user_id != auth.user.id
    ):
        raise HTTPException(404, "会话不存在")
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.asc())
        .all()
    )
    out_msgs = []
    for m in msgs:
        cites = []
        groups = None
        trace_id = None
        hit_test_id = None
        if isinstance(m.citations, dict):
            cites = m.citations.get("sources") or []
            groups = m.citations.get("groups")
            retrieve = m.citations.get("retrieve") or {}
            if isinstance(retrieve, dict):
                trace_id = retrieve.get("trace_id")
                hit_test_id = retrieve.get("hit_test_id")
        elif isinstance(m.citations, list):
            cites = m.citations
        out_msgs.append(
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "citations": cites,
                "citation_groups": groups,
                "trace_id": trace_id,
                "hit_test_id": hit_test_id,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )
    return {"id": conv.id, "title": conv.title, "messages": out_msgs}


@router.get("/hit-test")
def hit_test(
    q: str = Query(..., min_length=1),
    persist: bool = Query(default=True),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    """即时 Hit Test；默认落库 context_snapshot，返回 run id。"""
    fused, debug = hybrid_search(
        db,
        q,
        workspace_id=auth.workspace_id,
        clearance=auth.user.clearance,
        recall_k=50,
        top_k=20,
    )
    hits = prefer_full_tables(rerank(q, fused, top_n=8))
    tmeta = table_inject_meta(hits)
    run_id = None
    snapshot = None
    if persist:
        row = persist_hit_test_run(
            db,
            query=q,
            workspace_id=auth.workspace_id,
            clearance=auth.user.clearance,
            user_id=auth.user.id,
            hits=hits,
            debug=debug,
            source="hit_test",
        )
        run_id = row.id
        snapshot = row.context_snapshot
    return {
        "id": run_id,
        "query": q,
        "workspace_id": auth.workspace_id,
        "clearance": auth.user.clearance,
        "meta": tmeta,
        "debug": {
            "vector_ids": debug.vector_ids,
            "keyword_ids": debug.keyword_ids,
            "fused_ids": debug.fused_ids,
            "rrf_k": debug.rrf_k,
        },
        "injected": [
            {
                "chunk_id": h.chunk.id,
                "doc_id": h.document.id,
                "title": h.document.title,
                "classification": h.document.classification,
                "score": round(h.score, 4),
                "channels": h.channels,
                "is_table": bool(h.chunk.is_table),
                "table_full_inject": bool(h.chunk.is_table),
                "preview": h.chunk.content[:180],
                "content": h.chunk.content,
            }
            for h in hits
        ],
        "context_snapshot": snapshot,
    }


@router.get("/hit-tests")
def list_hit_tests(
    limit: int = Query(default=40, ge=1, le=100),
    source: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    _require_hit_viewer(auth)
    q = db.query(HitTestRun).filter(HitTestRun.workspace_id == auth.workspace_id)
    if source:
        q = q.filter(HitTestRun.source == source)
    rows = q.order_by(HitTestRun.id.desc()).limit(limit).all()
    return {
        "items": [
            {
                "id": r.id,
                "query": r.query,
                "source": r.source,
                "clearance": r.clearance,
                "conversation_id": r.conversation_id,
                "injected": (r.context_snapshot or {}).get("meta", {}).get("injected"),
                "vector_hits": (r.context_snapshot or {}).get("meta", {}).get("vector_hits"),
                "keyword_hits": (r.context_snapshot or {}).get("meta", {}).get("keyword_hits"),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get("/hit-tests/{run_id}")
def get_hit_test(
    run_id: int,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    _require_hit_viewer(auth)
    row = db.get(HitTestRun, run_id)
    if not row or row.workspace_id != auth.workspace_id:
        raise HTTPException(404, "Hit Test 记录不存在")
    return {
        "id": row.id,
        "query": row.query,
        "source": row.source,
        "clearance": row.clearance,
        "workspace_id": row.workspace_id,
        "user_id": row.user_id,
        "conversation_id": row.conversation_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "context_snapshot": row.context_snapshot,
    }


@router.get("/traces")
def list_traces(
    limit: int = Query(default=30, ge=1, le=100),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    """最近问答 Trace 列表（管理员全工作区；普通用户仅本人）。"""
    q = db.query(QaTrace).filter(QaTrace.workspace_id == auth.workspace_id)
    if auth.user.role not in {"admin", "librarian", "auditor"}:
        q = q.filter(QaTrace.user_id == auth.user.id)
    rows = q.order_by(QaTrace.created_at.desc()).limit(limit).all()
    return {
        "items": [
            {
                "id": r.id,
                "query": r.query,
                "latency_ms": r.latency_ms,
                "hit_test_id": r.hit_test_id,
                "conversation_id": r.conversation_id,
                "message_id": r.message_id,
                "span_count": len(r.spans or []),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get("/traces/{trace_id}")
def get_trace(
    trace_id: str,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    """单次问答全链路 Trace（retrieve → inject → generate）。"""
    row = db.get(QaTrace, trace_id)
    if not row or not _can_view_trace(auth, row):
        raise HTTPException(404, "Trace 不存在")
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "user_id": row.user_id,
        "conversation_id": row.conversation_id,
        "message_id": row.message_id,
        "hit_test_id": row.hit_test_id,
        "query": row.query,
        "answer_preview": row.answer_preview,
        "spans": row.spans or [],
        "latency_ms": row.latency_ms,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "engine": "zhishu-local",
    }
