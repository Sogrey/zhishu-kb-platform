"""简易分块：按字符近似 token（中文约 1.5 字/token）。"""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.parse import ParsedBlock, ParsedDoc


@dataclass
class ChunkDraft:
    seq: int
    content: str
    page_no: int | None
    is_table: bool
    token_count: int


def _approx_tokens(text: str) -> int:
    # 粗估：英文按空格，中文按字
    return max(1, int(len(text) / 1.5))


def chunk_document(parsed: ParsedDoc, max_tokens: int = 512, overlap_ratio: float = 0.1) -> list[ChunkDraft]:
    overlap = int(max_tokens * overlap_ratio)
    drafts: list[ChunkDraft] = []
    seq = 0
    for block in parsed.blocks:
        if block.is_table:
            drafts.append(
                ChunkDraft(
                    seq=seq,
                    content=block.text.strip(),
                    page_no=block.page_no,
                    is_table=True,
                    token_count=_approx_tokens(block.text),
                )
            )
            seq += 1
            continue
        drafts.extend(_split_text(block, max_tokens, overlap, start_seq=seq))
        if drafts:
            seq = drafts[-1].seq + 1
    return drafts


def _split_text(
    block: ParsedBlock, max_tokens: int, overlap: int, start_seq: int
) -> list[ChunkDraft]:
    text = block.text.strip()
    if not text:
        return []
    # 按段落优先
    paras = [p.strip() for p in text.replace("\r", "").split("\n") if p.strip()]
    chunks: list[ChunkDraft] = []
    buf: list[str] = []
    buf_tokens = 0
    seq = start_seq

    def flush(force: bool = False) -> None:
        nonlocal buf, buf_tokens, seq
        if not buf:
            return
        if buf_tokens >= max_tokens * 0.6 or force:
            content = "\n".join(buf).strip()
            chunks.append(
                ChunkDraft(
                    seq=seq,
                    content=content,
                    page_no=block.page_no,
                    is_table=False,
                    token_count=_approx_tokens(content),
                )
            )
            seq += 1
            if overlap > 0 and content:
                # 保留尾部重叠
                keep = content[- overlap * 2 :] if len(content) > overlap * 2 else content
                buf = [keep]
                buf_tokens = _approx_tokens(keep)
            else:
                buf = []
                buf_tokens = 0

    for para in paras:
        t = _approx_tokens(para)
        if t > max_tokens:
            flush(force=True)
            # 硬切长段
            step = max(50, int(max_tokens * 1.5))
            for i in range(0, len(para), step):
                piece = para[i : i + step]
                chunks.append(
                    ChunkDraft(
                        seq=seq,
                        content=piece,
                        page_no=block.page_no,
                        is_table=False,
                        token_count=_approx_tokens(piece),
                    )
                )
                seq += 1
            continue
        if buf_tokens + t > max_tokens:
            flush(force=True)
        buf.append(para)
        buf_tokens += t
    flush(force=True)
    return chunks
