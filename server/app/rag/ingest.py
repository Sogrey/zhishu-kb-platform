"""摄取流水线：解析 → 分块 → 嵌入 → 入库。"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Chunk, Document
from app.rag.chunker import chunk_document
from app.rag.embed import embed_texts
from app.rag.parse import parse_file

logger = logging.getLogger(__name__)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run_ingest(db: Session, document_id: int) -> None:
    doc = db.get(Document, document_id)
    if not doc or not doc.file_path:
        raise ValueError(f"document {document_id} not found or missing file")

    path = Path(doc.file_path)
    try:
        doc.status = "parsing"
        doc.progress = 10
        doc.error_message = None
        db.commit()

        parsed = parse_file(path, title=doc.title)
        doc.progress = 40
        db.commit()

        drafts = chunk_document(parsed)
        if not drafts:
            raise ValueError("解析结果为空，无可用分块")

        doc.status = "embedding"
        doc.progress = 55
        db.commit()

        # 清旧块（重跑）
        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        db.commit()

        texts = [d.content for d in drafts]
        vectors = embed_texts(texts)
        for draft, vec in zip(drafts, vectors, strict=True):
            db.add(
                Chunk(
                    document_id=doc.id,
                    workspace_id=doc.workspace_id,
                    seq=draft.seq,
                    content=draft.content,
                    is_table=draft.is_table,
                    page_no=draft.page_no,
                    token_count=draft.token_count,
                    classification=doc.classification,
                    active=True,
                    embedding=vec,
                )
            )
        doc.status = "ready"
        doc.progress = 100
        db.commit()
        logger.info("ingest ok doc=%s chunks=%s", doc.id, len(drafts))
        # 文档向量 + 旧稿相似提示（失败不阻断入库）
        try:
            from app.rag.merge import after_ingest_merge

            after_ingest_merge(db, doc.id)
        except Exception:  # noqa: BLE001
            logger.exception("merge detect failed doc=%s", doc.id)
    except Exception as exc:  # noqa: BLE001 — 任务边界捕获
        logger.exception("ingest failed doc=%s", document_id)
        db.rollback()
        doc = db.get(Document, document_id)
        if doc:
            doc.status = "failed"
            doc.error_message = str(exc)[:2000]
            doc.progress = 0
            db.commit()
        raise
