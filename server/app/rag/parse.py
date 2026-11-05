"""文档解析：stub 本地解析；正式模式可切 Docling HTTP。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.core.config import get_settings

_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


@dataclass
class ParsedBlock:
    text: str
    page_no: int | None = None
    is_table: bool = False


@dataclass
class ParsedDoc:
    title: str
    blocks: list[ParsedBlock] = field(default_factory=list)


def parse_file(path: Path, title: str | None = None) -> ParsedDoc:
    settings = get_settings()
    if not settings.zhishu_dev_stub:
        return _parse_via_http(path, title)
    return _parse_local(path, title)


def _parse_local(path: Path, title: str | None) -> ParsedDoc:
    suffix = path.suffix.lower()
    doc_title = title or path.stem
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        blocks: list[ParsedBlock] = []
        for i, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                # PDF 文本层里也可能夹 GFM 表（少见）；按行探测
                blocks.extend(_blocks_from_text(text, page_no=i))
        if not blocks:
            blocks.append(ParsedBlock(text="[空 PDF 或扫描件，请启用 OCR 解析]", page_no=1))
        return ParsedDoc(title=doc_title, blocks=blocks)
    if suffix in {".docx"}:
        return ParsedDoc(title=doc_title, blocks=_blocks_from_docx(path))
    if suffix in {".md", ".txt", ".markdown"}:
        text = path.read_text(encoding="utf-8", errors="ignore").strip() or "[空文本]"
        return ParsedDoc(title=doc_title, blocks=_blocks_from_text(text, page_no=1))
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        raise ValueError(f"暂不支持的文件类型: {suffix}")
    return ParsedDoc(title=doc_title, blocks=_blocks_from_text(text, page_no=1))


def _blocks_from_text(text: str, page_no: int | None = 1) -> list[ParsedBlock]:
    """将 Markdown/纯文本拆成普通块 + 整表块（is_table）。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[ParsedBlock] = []
    buf: list[str] = []
    i = 0

    def flush_text() -> None:
        nonlocal buf
        joined = "\n".join(buf).strip()
        if joined:
            blocks.append(ParsedBlock(text=joined, page_no=page_no, is_table=False))
        buf = []

    while i < len(lines):
        if _is_table_start(lines, i):
            flush_text()
            table_lines: list[str] = []
            while i < len(lines) and _is_table_line(lines[i]):
                table_lines.append(lines[i])
                i += 1
            table_text = "\n".join(table_lines).strip()
            if table_text:
                blocks.append(ParsedBlock(text=table_text, page_no=page_no, is_table=True))
            continue
        buf.append(lines[i])
        i += 1
    flush_text()
    return blocks or [ParsedBlock(text=text.strip() or "[空文本]", page_no=page_no)]


def _is_table_line(line: str) -> bool:
    return bool(_TABLE_ROW.match(line) or _TABLE_SEP.match(line))


def _is_table_start(lines: list[str], i: int) -> bool:
    """GFM：表头行 + 分隔行；或连续两行 pipe 行。"""
    if i >= len(lines) or not _TABLE_ROW.match(lines[i]):
        return False
    if i + 1 >= len(lines):
        return False
    nxt = lines[i + 1]
    return bool(_TABLE_SEP.match(nxt) or _TABLE_ROW.match(nxt))


def _blocks_from_docx(path: Path) -> list[ParsedBlock]:
    d = DocxDocument(str(path))
    blocks: list[ParsedBlock] = []
    text_buf: list[str] = []

    def flush_text() -> None:
        nonlocal text_buf
        joined = "\n".join(text_buf).strip()
        if joined:
            blocks.append(ParsedBlock(text=joined, page_no=1, is_table=False))
        text_buf = []

    for item in _iter_docx_blocks(d):
        if isinstance(item, str):
            # paragraph
            if item.strip():
                text_buf.append(item.strip())
        else:
            # markdown table string
            flush_text()
            md = item.strip()
            if md:
                blocks.append(ParsedBlock(text=md, page_no=1, is_table=True))
    flush_text()
    return blocks or [ParsedBlock(text="[空 Word 文档]", page_no=1)]


def _iter_docx_blocks(doc: DocxDocument):
    """按文档顺序产出段落字符串或表格 Markdown。"""
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            p = Paragraph(child, doc)
            yield p.text or ""
        elif child.tag == qn("w:tbl"):
            yield _docx_table_to_md(Table(child, doc))


def _docx_table_to_md(table) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        cells = [c.text.strip().replace("\n", " ") for c in row.cells]
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    norm = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(norm[0]) + " |"]
    lines.append("| " + " | ".join(["---"] * width) + " |")
    for r in norm[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _parse_via_http(path: Path, title: str | None) -> ParsedDoc:
    try:
        import httpx

        settings = get_settings()
        with path.open("rb") as f:
            resp = httpx.post(
                f"{settings.parse_url}/parse",
                files={"file": (path.name, f)},
                timeout=120.0,
            )
        if resp.status_code >= 400:
            return _parse_local(path, title)
        data = resp.json()
        blocks = [
            ParsedBlock(
                text=b.get("text", ""),
                page_no=b.get("page_no"),
                is_table=bool(b.get("is_table")),
            )
            for b in data.get("blocks", [])
            if b.get("text")
        ]
        if not blocks:
            return _parse_local(path, title)
        return ParsedDoc(title=title or data.get("title") or path.stem, blocks=blocks)
    except Exception:
        return _parse_local(path, title)
