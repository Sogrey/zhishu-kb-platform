"""
旧稿相似度归并（C-004 ~ C-007）

流程：
1. 入库完成后写 documents.doc_embedding（分块向量均值；stub 用 n-gram 向量保证相似文相近）
2. 与同工作区现行稿比对余弦相似度
3. ≥ strong → 强提示；weak~strong → 弱提示；写入 merge_suggestions
4. 管理员确认后：旧稿 is_current=False、superseded_by=新稿；检索层已过滤 is_current
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Chunk, Document, MergeSuggestion

logger = logging.getLogger(__name__)


@dataclass
class MergeHit:
    older: Document
    score: float
    strength: str  # strong | weak


def mean_embedding(vectors: list[list[float]]) -> list[float] | None:
    if not vectors:
        return None
    arr = np.array(vectors, dtype=np.float32)
    mean = arr.mean(axis=0)
    norm = float(np.linalg.norm(mean)) or 1.0
    return (mean / norm).tolist()


def ngram_doc_vector(text: str, dim: int) -> list[float]:
    """
    stub/文档级专用：字符 trigram 哈希到固定维，相似正文余弦会高。
    （分块 stub 向量基于全文 hash，相近文本也可能正交，不适合归并）
    """
    vec = np.zeros(dim, dtype=np.float32)
    raw = (text or "").lower()
    if len(raw) < 3:
        raw = (raw + "___")[:8]
    for i in range(max(1, len(raw) - 2)):
        gram = raw[i : i + 3]
        h = int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:8], 16)
        vec[h % dim] += 1.0
    # 标题权重：前 80 字加倍计入
    head = raw[:80]
    for i in range(max(1, len(head) - 2)):
        gram = head[i : i + 3]
        h = int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:8], 16)
        vec[h % dim] += 0.5
    norm = float(np.linalg.norm(vec)) or 1.0
    return (vec / norm).tolist()


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.0
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb)) or 1.0
    return float(np.dot(va, vb) / denom)


def build_doc_embedding(db: Session, doc: Document) -> list[float] | None:
    settings = get_settings()
    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == doc.id, Chunk.active.is_(True))
        .order_by(Chunk.seq.asc())
        .all()
    )
    if settings.zhishu_dev_stub:
        blob = doc.title + "\n" + "\n".join(c.content for c in chunks[:40])
        return ngram_doc_vector(blob, settings.embedding_dim)
    vectors = [c.embedding for c in chunks if c.embedding]
    return mean_embedding(vectors)  # type: ignore[arg-type]


def write_doc_embedding(db: Session, doc: Document) -> list[float] | None:
    emb = build_doc_embedding(db, doc)
    doc.doc_embedding = emb
    db.commit()
    return emb


def find_merge_hits(db: Session, doc: Document) -> list[MergeHit]:
    settings = get_settings()
    if not doc.doc_embedding:
        return []
    others = (
        db.query(Document)
        .filter(
            Document.workspace_id == doc.workspace_id,
            Document.id != doc.id,
            Document.status == "ready",
            Document.is_current.is_(True),
            Document.doc_embedding.is_not(None),
        )
        .all()
    )
    hits: list[MergeHit] = []
    for older in others:
        score = cosine(doc.doc_embedding, older.doc_embedding)
        if score >= settings.merge_strong_threshold:
            hits.append(MergeHit(older=older, score=score, strength="strong"))
        elif score >= settings.merge_weak_threshold:
            hits.append(MergeHit(older=older, score=score, strength="weak"))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:5]


def refresh_merge_suggestions(db: Session, doc: Document) -> list[MergeSuggestion]:
    """清除该新稿未处理提示，按最新相似度重建。"""
    db.query(MergeSuggestion).filter(
        MergeSuggestion.newer_doc_id == doc.id,
        MergeSuggestion.status == "pending",
    ).delete(synchronize_session=False)
    created: list[MergeSuggestion] = []
    for hit in find_merge_hits(db, doc):
        row = MergeSuggestion(
            workspace_id=doc.workspace_id,
            newer_doc_id=doc.id,
            older_doc_id=hit.older.id,
            score=round(hit.score, 4),
            strength=hit.strength,
            status="pending",
        )
        db.add(row)
        created.append(row)
    db.commit()
    for r in created:
        db.refresh(r)
    if created:
        logger.info(
            "merge suggestions doc=%s count=%s top=%s",
            doc.id,
            len(created),
            created[0].score,
        )
    return created


def after_ingest_merge(db: Session, document_id: int) -> None:
    doc = db.get(Document, document_id)
    if not doc or doc.status != "ready":
        return
    write_doc_embedding(db, doc)
    refresh_merge_suggestions(db, doc)


def confirm_merge(
    db: Session, *, suggestion_id: int, workspace_id: int
) -> MergeSuggestion:
    sug = db.get(MergeSuggestion, suggestion_id)
    if not sug or sug.workspace_id != workspace_id:
        raise ValueError("归并提示不存在")
    if sug.status != "pending":
        raise ValueError(f"提示状态不可确认: {sug.status}")
    older = db.get(Document, sug.older_doc_id)
    newer = db.get(Document, sug.newer_doc_id)
    if not older or not newer:
        raise ValueError("关联文档缺失")
    older.is_current = False
    older.superseded_by = newer.id
    # 旧稿分块标记 inactive，双保险（检索还看 is_current）
    db.query(Chunk).filter(Chunk.document_id == older.id).update(
        {"active": False}, synchronize_session=False
    )
    sug.status = "confirmed"
    # 同对其他 pending 一并关闭
    db.query(MergeSuggestion).filter(
        MergeSuggestion.workspace_id == workspace_id,
        MergeSuggestion.older_doc_id == older.id,
        MergeSuggestion.status == "pending",
        MergeSuggestion.id != sug.id,
    ).update({"status": "ignored"}, synchronize_session=False)
    db.commit()
    db.refresh(sug)
    return sug


def ignore_merge(
    db: Session, *, suggestion_id: int, workspace_id: int
) -> MergeSuggestion:
    sug = db.get(MergeSuggestion, suggestion_id)
    if not sug or sug.workspace_id != workspace_id:
        raise ValueError("归并提示不存在")
    if sug.status != "pending":
        raise ValueError(f"提示状态不可忽略: {sug.status}")
    sug.status = "ignored"
    db.commit()
    db.refresh(sug)
    return sug
