from datetime import datetime

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: int
    workspace_id: int = 1
    title: str
    source_type: str
    status: str
    progress: int
    classification: int = 2
    is_current: bool = True
    superseded_by: int | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    validity: str = "active"
    error_message: str | None = None
    sha256: str | None = None
    created_at: datetime
    chunk_count: int = 0
    deduplicated: bool = False

    model_config = {"from_attributes": True}


class ChunkOut(BaseModel):
    id: int
    seq: int
    content: str
    is_table: bool
    page_no: int | None = None
    token_count: int | None = None

    model_config = {"from_attributes": True}


class Citation(BaseModel):
    doc_id: int
    title: str
    page: int | None = None
    snippet: str
    chunk_id: int | None = None
    score: float | None = None
    classification: int = 2


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None


class ValidityIn(BaseModel):
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class MergeSuggestionOut(BaseModel):
    id: int
    newer_doc_id: int
    older_doc_id: int
    newer_title: str
    older_title: str
    score: float
    strength: str
    status: str
    created_at: datetime | None = None
