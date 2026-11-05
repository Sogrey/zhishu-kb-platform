from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import write_audit
from app.core.config import get_settings
from app.core.db import SessionLocal, get_db
from app.core.deps import AuthContext, get_auth
from app.models import Chunk, Document, MergeSuggestion
from app.rag.ingest import file_sha256, run_ingest
from app.rag.merge import confirm_merge, ignore_merge
from app.rag.validity import retire_expired, validity_state
from app.schemas.document import ChunkOut, DocumentOut, MergeSuggestionOut, ValidityIn

logger = logging.getLogger(__name__)
router = APIRouter()


def _enqueue_ingest(document_id: int) -> None:
    settings = get_settings()
    if settings.zhishu_dev_stub:
        db = SessionLocal()
        try:
            run_ingest(db, document_id)
        finally:
            db.close()
        return
    try:
        from worker.tasks import ingest_document

        ingest_document.delay(document_id)
    except Exception:  # noqa: BLE001
        logger.exception("celery enqueue failed, sync fallback doc=%s", document_id)
        db = SessionLocal()
        try:
            run_ingest(db, document_id)
        finally:
            db.close()


def _chunk_counts(db: Session, doc_ids: list[int]) -> dict[int, int]:
    if not doc_ids:
        return {}
    rows = (
        db.query(Chunk.document_id, func.count(Chunk.id))
        .filter(Chunk.document_id.in_(doc_ids))
        .group_by(Chunk.document_id)
        .all()
    )
    return {int(doc_id): int(cnt) for doc_id, cnt in rows}


def _client_ip(request: Request | None) -> str | None:
    if not request:
        return None
    return request.client.host if request.client else None


def _to_out(doc: Document, chunk_count: int = 0, deduplicated: bool = False) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        workspace_id=doc.workspace_id,
        title=doc.title,
        source_type=doc.source_type,
        status=doc.status,
        progress=doc.progress,
        classification=doc.classification,
        is_current=doc.is_current,
        superseded_by=doc.superseded_by,
        valid_from=doc.valid_from,
        valid_to=doc.valid_to,
        validity=validity_state(doc),
        error_message=doc.error_message,
        sha256=doc.sha256,
        created_at=doc.created_at,
        chunk_count=chunk_count,
        deduplicated=deduplicated,
    )


def _merge_out(db: Session, row: MergeSuggestion) -> MergeSuggestionOut:
    newer = db.get(Document, row.newer_doc_id)
    older = db.get(Document, row.older_doc_id)
    return MergeSuggestionOut(
        id=row.id,
        newer_doc_id=row.newer_doc_id,
        older_doc_id=row.older_doc_id,
        newer_title=newer.title if newer else f"#{row.newer_doc_id}",
        older_title=older.title if older else f"#{row.older_doc_id}",
        score=row.score,
        strength=row.strength,
        status=row.status,
        created_at=row.created_at,
    )


def _get_doc_in_ws(db: Session, doc_id: int, workspace_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if not doc or doc.workspace_id != workspace_id:
        raise HTTPException(404, "文档不存在")
    return doc


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    classification: int = Form(default=2),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> DocumentOut:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(400, "缺少文件名")
    if classification < 1 or classification > 4:
        raise HTTPException(400, "密级须为 1~4")
    if classification > auth.user.clearance:
        raise HTTPException(403, "不能上传高于本人密级的文档")

    suffix = Path(file.filename).suffix.lower()
    allowed = {".pdf", ".docx", ".md", ".txt", ".markdown"}
    if suffix not in allowed:
        raise HTTPException(400, f"暂不支持 {suffix}，允许: {sorted(allowed)}")

    dest_dir = settings.files_path / "uploads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}{suffix}"

    size = 0
    max_bytes = settings.upload_max_mb * 1024 * 1024
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(400, f"文件超过 {settings.upload_max_mb}MB")
            out.write(chunk)

    digest = file_sha256(dest)
    existing = (
        db.query(Document)
        .filter(Document.sha256 == digest, Document.workspace_id == auth.workspace_id)
        .first()
    )
    if existing:
        dest.unlink(missing_ok=True)
        counts = _chunk_counts(db, [existing.id])
        return _to_out(existing, chunk_count=counts.get(existing.id, 0), deduplicated=True)

    doc = Document(
        workspace_id=auth.workspace_id,
        title=Path(file.filename).name,
        source_type="upload",
        file_path=str(dest),
        sha256=digest,
        mime_type=file.content_type,
        status="pending",
        progress=0,
        classification=classification,
    )
    db.add(doc)
    db.flush()
    write_audit(
        db,
        action="document.upload",
        actor_id=auth.user.id,
        actor_name=auth.user.username,
        workspace_id=auth.workspace_id,
        resource_type="document",
        resource_id=doc.id,
        detail={"title": doc.title, "classification": classification},
        ip=_client_ip(request),
    )
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(_enqueue_ingest, doc.id)
    return _to_out(doc, chunk_count=0, deduplicated=False)


@router.get("", response_model=list[DocumentOut])
def list_documents(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    query = db.query(Document).filter(Document.workspace_id == auth.workspace_id)
    query = query.filter(Document.classification <= auth.user.clearance)
    if status:
        query = query.filter(Document.status == status)
    if q:
        query = query.filter(Document.title.ilike(f"%{q.strip()}%"))
    rows = query.order_by(Document.id.desc()).limit(100).all()
    counts = _chunk_counts(db, [r.id for r in rows])
    return [_to_out(r, chunk_count=counts.get(r.id, 0)) for r in rows]


@router.post("/retire-scan")
def retire_scan(
    request: Request,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    if auth.user.role not in {"admin", "librarian"}:
        raise HTTPException(403, "仅管理员/知识管理员可扫描退休")
    n = retire_expired(db, workspace_id=auth.workspace_id)
    write_audit(
        db,
        action="document.retire_scan",
        actor_id=auth.user.id,
        actor_name=auth.user.username,
        workspace_id=auth.workspace_id,
        detail={"retired": n},
        ip=_client_ip(request),
        commit=True,
    )
    return {"ok": True, "retired": n}


@router.get("/merge-suggestions", response_model=list[MergeSuggestionOut])
def list_merge_suggestions(
    status: str = Query(default="pending"),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> list[MergeSuggestionOut]:
    """归并待办队列：新稿入库后与现行稿相似度提示。"""
    q = db.query(MergeSuggestion).filter(
        MergeSuggestion.workspace_id == auth.workspace_id
    )
    if status:
        q = q.filter(MergeSuggestion.status == status)
    rows = q.order_by(MergeSuggestion.id.desc()).limit(50).all()
    return [_merge_out(db, r) for r in rows]


@router.post("/merge-suggestions/{suggestion_id}/confirm", response_model=MergeSuggestionOut)
def merge_confirm(
    suggestion_id: int,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> MergeSuggestionOut:
    if auth.user.role not in {"admin", "librarian"}:
        raise HTTPException(403, "仅管理员/知识管理员可确认归并")
    try:
        sug = confirm_merge(
            db, suggestion_id=suggestion_id, workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    write_audit(
        db,
        action="document.merge_confirm",
        actor_id=auth.user.id,
        actor_name=auth.user.username,
        workspace_id=auth.workspace_id,
        resource_type="merge_suggestion",
        resource_id=suggestion_id,
        detail={
            "newer_doc_id": sug.newer_doc_id,
            "older_doc_id": sug.older_doc_id,
            "score": sug.score,
        },
        ip=_client_ip(request),
        commit=True,
    )
    return _merge_out(db, sug)


@router.post("/merge-suggestions/{suggestion_id}/ignore", response_model=MergeSuggestionOut)
def merge_ignore(
    suggestion_id: int,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> MergeSuggestionOut:
    if auth.user.role not in {"admin", "librarian"}:
        raise HTTPException(403, "仅管理员/知识管理员可忽略归并")
    try:
        sug = ignore_merge(
            db, suggestion_id=suggestion_id, workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    write_audit(
        db,
        action="document.merge_ignore",
        actor_id=auth.user.id,
        actor_name=auth.user.username,
        workspace_id=auth.workspace_id,
        resource_type="merge_suggestion",
        resource_id=suggestion_id,
        detail={"older_doc_id": sug.older_doc_id},
        ip=_client_ip(request),
        commit=True,
    )
    return _merge_out(db, sug)


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: int, auth: AuthContext = Depends(get_auth), db: Session = Depends(get_db)
) -> DocumentOut:
    doc = _get_doc_in_ws(db, doc_id, auth.workspace_id)
    if doc.classification > auth.user.clearance:
        raise HTTPException(404, "文档不存在")
    counts = _chunk_counts(db, [doc.id])
    return _to_out(doc, chunk_count=counts.get(doc.id, 0))


@router.get("/{doc_id}/chunks", response_model=list[ChunkOut])
def list_chunks(
    doc_id: int, auth: AuthContext = Depends(get_auth), db: Session = Depends(get_db)
) -> list[Chunk]:
    doc = _get_doc_in_ws(db, doc_id, auth.workspace_id)
    if doc.classification > auth.user.clearance:
        raise HTTPException(404, "文档不存在")
    return (
        db.query(Chunk)
        .filter(Chunk.document_id == doc_id)
        .order_by(Chunk.seq.asc())
        .all()
    )


@router.get("/{doc_id}/parsed", response_class=PlainTextResponse)
def download_parsed(
    doc_id: int, auth: AuthContext = Depends(get_auth), db: Session = Depends(get_db)
) -> PlainTextResponse:
    doc = _get_doc_in_ws(db, doc_id, auth.workspace_id)
    if doc.classification > auth.user.clearance:
        raise HTTPException(404, "文档不存在")
    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == doc_id)
        .order_by(Chunk.seq.asc())
        .all()
    )
    if not chunks:
        raise HTTPException(400, "尚无分块，请等待摄取完成或重跑")
    parts = [f"# {doc.title}", ""]
    for c in chunks:
        header = f"<!-- chunk seq={c.seq}"
        if c.page_no is not None:
            header += f" page={c.page_no}"
        if c.is_table:
            header += " table"
        header += " -->"
        parts.append(header)
        parts.append(c.content)
        parts.append("")
    body = "\n".join(parts)
    filename = f"{Path(doc.title).stem}-parsed.md"
    return PlainTextResponse(
        body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{doc_id}/reingest", response_model=DocumentOut)
def reingest(
    doc_id: int,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> DocumentOut:
    doc = _get_doc_in_ws(db, doc_id, auth.workspace_id)
    if not doc.file_path or not Path(doc.file_path).exists():
        raise HTTPException(400, "原文件缺失，无法重跑")
    doc.status = "pending"
    doc.progress = 0
    doc.error_message = None
    db.commit()
    db.refresh(doc)
    background_tasks.add_task(_enqueue_ingest, doc.id)
    return _to_out(doc, chunk_count=0)


@router.patch("/{doc_id}/classification", response_model=DocumentOut)
def set_classification(
    doc_id: int,
    request: Request,
    level: int = Query(..., ge=1, le=4),
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> DocumentOut:
    if auth.user.role not in {"admin", "librarian"}:
        raise HTTPException(403, "仅管理员/知识管理员可改密级")
    if level > auth.user.clearance:
        raise HTTPException(403, "不能设置高于本人密级的级别")
    doc = _get_doc_in_ws(db, doc_id, auth.workspace_id)
    old = doc.classification
    doc.classification = level
    db.query(Chunk).filter(Chunk.document_id == doc.id).update(
        {"classification": level}, synchronize_session=False
    )
    write_audit(
        db,
        action="document.classify",
        actor_id=auth.user.id,
        actor_name=auth.user.username,
        workspace_id=auth.workspace_id,
        resource_type="document",
        resource_id=doc.id,
        detail={"from": old, "to": level, "title": doc.title},
        ip=_client_ip(request),
    )
    db.commit()
    db.refresh(doc)
    counts = _chunk_counts(db, [doc.id])
    return _to_out(doc, chunk_count=counts.get(doc.id, 0))


@router.patch("/{doc_id}/validity", response_model=DocumentOut)
def set_validity(
    doc_id: int,
    body: ValidityIn,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> DocumentOut:
    if auth.user.role not in {"admin", "librarian"}:
        raise HTTPException(403, "仅管理员/知识管理员可改有效期")
    doc = _get_doc_in_ws(db, doc_id, auth.workspace_id)
    if body.valid_from and body.valid_to and body.valid_from > body.valid_to:
        raise HTTPException(400, "生效日不能晚于失效日")
    doc.valid_from = body.valid_from
    doc.valid_to = body.valid_to
    # 若仍标记 retired 但改回有效窗口，恢复 ready
    state = validity_state(doc)
    if state == "active" and doc.status == "retired":
        doc.status = "ready"
        doc.is_current = True
    elif state == "expired":
        doc.status = "retired"
        doc.is_current = False
    write_audit(
        db,
        action="document.validity",
        actor_id=auth.user.id,
        actor_name=auth.user.username,
        workspace_id=auth.workspace_id,
        resource_type="document",
        resource_id=doc.id,
        detail={
            "title": doc.title,
            "valid_from": body.valid_from.isoformat() if body.valid_from else None,
            "valid_to": body.valid_to.isoformat() if body.valid_to else None,
            "validity": state,
        },
        ip=_client_ip(request),
    )
    db.commit()
    db.refresh(doc)
    counts = _chunk_counts(db, [doc.id])
    return _to_out(doc, chunk_count=counts.get(doc.id, 0))


@router.delete("/{doc_id}")
def delete_document(
    doc_id: int,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> dict:
    doc = _get_doc_in_ws(db, doc_id, auth.workspace_id)
    title = doc.title
    path = Path(doc.file_path) if doc.file_path else None
    write_audit(
        db,
        action="document.delete",
        actor_id=auth.user.id,
        actor_name=auth.user.username,
        workspace_id=auth.workspace_id,
        resource_type="document",
        resource_id=doc_id,
        detail={"title": title},
        ip=_client_ip(request),
    )
    db.delete(doc)
    db.commit()
    if path and path.exists():
        path.unlink(missing_ok=True)
    return {"ok": True, "id": doc_id}
