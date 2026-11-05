"""上下文组装：FR-06 表格全表注入。"""

from __future__ import annotations

from app.rag.retrieve import Hit


def prefer_full_tables(hits: list[Hit]) -> list[Hit]:
    """命中的 is_table 块整体前置，组内保持原精排顺序。"""
    tables = [h for h in hits if getattr(h.chunk, "is_table", False)]
    others = [h for h in hits if not getattr(h.chunk, "is_table", False)]
    if not tables:
        return list(hits)
    return tables + others


def build_context(hits: list[Hit]) -> str:
    """组装注入模型的上下文；表格块标注【全表 Markdown】且不截断。"""
    ordered = prefer_full_tables(hits)
    parts: list[str] = []
    for i, h in enumerate(ordered, start=1):
        page = f" p.{h.chunk.page_no}" if h.chunk.page_no else ""
        body = (h.chunk.content or "").strip()
        if h.chunk.is_table:
            parts.append(f"[{i}] 《{h.document.title}》{page} 【全表 Markdown】\n{body}")
        else:
            parts.append(f"[{i}] 《{h.document.title}》{page}\n{body}")
    return "\n\n".join(parts)


def table_inject_meta(hits: list[Hit]) -> dict:
    ordered = prefer_full_tables(hits)
    n = sum(1 for h in ordered if h.chunk.is_table)
    return {
        "table_full_inject": n > 0,
        "table_hits": n,
        "inject_order": "tables_first" if n else "score",
    }
