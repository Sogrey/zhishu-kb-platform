"""组装并可落库 Hit Test / 问答的 context_snapshot。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import HitTestRun
from app.rag.context_inject import prefer_full_tables, table_inject_meta
from app.rag.retrieve import Hit, RetrieveDebug


def build_context_snapshot(
    *,
    query: str,
    workspace_id: int,
    clearance: int,
    hits: list[Hit],
    debug: RetrieveDebug,
) -> dict[str, Any]:
    ordered = prefer_full_tables(hits)
    tmeta = table_inject_meta(ordered)
    return {
        "query": query,
        "workspace_id": workspace_id,
        "clearance": clearance,
        "debug": {
            "vector_ids": debug.vector_ids,
            "keyword_ids": debug.keyword_ids,
            "fused_ids": debug.fused_ids,
            "rrf_k": debug.rrf_k,
        },
        "meta": {
            "vector_hits": len(debug.vector_ids),
            "keyword_hits": len(debug.keyword_ids),
            "fused": len(debug.fused_ids),
            "injected": len(ordered),
            "rrf_k": debug.rrf_k,
            **tmeta,
        },
        "injected": [
            {
                "rank": i,
                "chunk_id": h.chunk.id,
                "doc_id": h.document.id,
                "title": h.document.title,
                "classification": h.document.classification,
                "is_current": h.document.is_current,
                "score": round(h.score, 4),
                "channels": h.channels,
                "is_table": bool(h.chunk.is_table),
                "table_full_inject": bool(h.chunk.is_table),
                "page_no": h.chunk.page_no,
                "seq": h.chunk.seq,
                "content": h.chunk.content,
                "preview": h.chunk.content[:180],
            }
            for i, h in enumerate(ordered, start=1)
        ],
    }


def persist_hit_test_run(
    db: Session,
    *,
    query: str,
    workspace_id: int,
    clearance: int,
    user_id: int | None,
    hits: list[Hit],
    debug: RetrieveDebug,
    source: str = "hit_test",
    conversation_id: int | None = None,
) -> HitTestRun:
    snap = build_context_snapshot(
        query=query,
        workspace_id=workspace_id,
        clearance=clearance,
        hits=hits,
        debug=debug,
    )
    row = HitTestRun(
        workspace_id=workspace_id,
        user_id=user_id,
        query=query,
        clearance=clearance,
        source=source,
        conversation_id=conversation_id,
        context_snapshot=snap,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
