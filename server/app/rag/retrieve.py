"""混合检索：向量 + 关键词 → RRF；检索层密级/工作区过滤。"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Chunk, Document
from app.rag.embed import embed_query
from app.rag.rrf import rrf_fuse
from app.rag.validity import validity_sql_clauses


@dataclass
class Hit:
    chunk: Chunk
    document: Document
    score: float
    channels: list[str] = field(default_factory=list)


@dataclass
class RetrieveDebug:
    vector_ids: list[int]
    keyword_ids: list[int]
    fused_ids: list[int]
    rrf_k: int = 60


def visibility_filter(workspace_id: int, clearance: int):
    """ADR-3：密级在检索层过滤；无权文档「不存在」。有效期即时生效。"""
    return (
        Chunk.active.is_(True),
        Document.status == "ready",
        Document.is_current.is_(True),
        Chunk.workspace_id == workspace_id,
        Document.workspace_id == workspace_id,
        Chunk.classification <= clearance,
        Document.classification <= clearance,
        *validity_sql_clauses(),
    )


def hybrid_search(
    db: Session,
    query: str,
    *,
    workspace_id: int,
    clearance: int,
    recall_k: int = 50,
    top_k: int = 20,
) -> tuple[list[Hit], RetrieveDebug]:
    vector_hits = _vector_channel(db, query, recall_k, workspace_id, clearance)
    keyword_hits = _keyword_rank(db, query, recall_k, workspace_id, clearance)

    fused = rrf_fuse(
        [vector_hits, keyword_hits],
        k=60,
        key_fn=lambda h: h.chunk.id,
    )

    channel_map: dict[int, set[str]] = {}
    for h in vector_hits:
        channel_map.setdefault(h.chunk.id, set()).add("vector")
    for h in keyword_hits:
        channel_map.setdefault(h.chunk.id, set()).add("keyword")

    hits: list[Hit] = []
    for base, score in fused[:top_k]:
        hits.append(
            Hit(
                chunk=base.chunk,
                document=base.document,
                score=score,
                channels=sorted(channel_map.get(base.chunk.id, set())),
            )
        )

    debug = RetrieveDebug(
        vector_ids=[h.chunk.id for h in vector_hits[:20]],
        keyword_ids=[h.chunk.id for h in keyword_hits[:20]],
        fused_ids=[h.chunk.id for h in hits],
    )
    return hits, debug


def vector_search(
    db: Session,
    query: str,
    top_k: int = 8,
    *,
    workspace_id: int = 1,
    clearance: int = 4,
) -> list[Hit]:
    hits, _ = hybrid_search(
        db,
        query,
        workspace_id=workspace_id,
        clearance=clearance,
        recall_k=max(50, top_k * 5),
        top_k=top_k,
    )
    return hits


def _vector_channel(
    db: Session, query: str, top_k: int, workspace_id: int, clearance: int
) -> list[Hit]:
    settings = get_settings()
    if settings.use_sqlite:
        return _sqlite_cosine(db, query, top_k, workspace_id, clearance)
    return _pgvector_search(db, query, top_k, workspace_id, clearance)


def _pgvector_search(
    db: Session, query: str, top_k: int, workspace_id: int, clearance: int
) -> list[Hit]:
    qvec = embed_query(query)
    distance = Chunk.embedding.cosine_distance(qvec)
    stmt = (
        select(Chunk, Document, distance.label("distance"))
        .join(Document, Document.id == Chunk.document_id)
        .where(*visibility_filter(workspace_id, clearance), Chunk.embedding.is_not(None))
        .order_by(distance)
        .limit(top_k)
    )
    rows = db.execute(stmt).all()
    return [
        Hit(chunk=chunk, document=doc, score=1.0 - float(dist), channels=["vector"])
        for chunk, doc, dist in rows
    ]


def _sqlite_cosine(
    db: Session, query: str, top_k: int, workspace_id: int, clearance: int
) -> list[Hit]:
    import numpy as np

    q = np.array(embed_query(query), dtype=np.float32)
    stmt = (
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(*visibility_filter(workspace_id, clearance), Chunk.embedding.is_not(None))
    )
    scored: list[Hit] = []
    for chunk, doc in db.execute(stmt).all():
        vec = np.array(chunk.embedding, dtype=np.float32)
        denom = float(np.linalg.norm(q) * np.linalg.norm(vec)) or 1.0
        score = float(np.dot(q, vec) / denom)
        scored.append(Hit(chunk=chunk, document=doc, score=score, channels=["vector"]))
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:top_k]


def _keyword_rank(
    db: Session, query: str, top_k: int, workspace_id: int, clearance: int
) -> list[Hit]:
    tokens = [t for t in _tokenize(query) if len(t) >= 2][:8]
    stmt = (
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(*visibility_filter(workspace_id, clearance))
        .limit(400)
    )
    rows = db.execute(stmt).all()
    scored: list[Hit] = []
    q_lower = query.lower()
    for chunk, doc in rows:
        content = chunk.content.lower()
        score = 0.0
        if q_lower and q_lower in content:
            score += 2.0
        for t in tokens:
            if t.lower() in content:
                score += 1.0
        if score > 0:
            scored.append(
                Hit(chunk=chunk, document=doc, score=score, channels=["keyword"])
            )
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:top_k]


def _tokenize(text: str) -> list[str]:
    import re

    tokens: list[str] = re.findall(r"[A-Za-z0-9_]{2,}", text)
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(run) <= 2:
            tokens.append(run)
            continue
        for i in range(len(run) - 1):
            tokens.append(run[i : i + 2])
        for i in range(len(run) - 2):
            tokens.append(run[i : i + 3])
    return tokens[:24]
