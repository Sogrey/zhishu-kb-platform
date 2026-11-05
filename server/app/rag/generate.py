"""LLM 生成：stub 输出干净 Markdown；正式模式走设置页渠道（DeepSeek/Ollama/llama.cpp）。"""

from __future__ import annotations

import re
from collections.abc import Iterator

from app.rag.context_inject import build_context, prefer_full_tables
from app.rag.retrieve import Hit
from app.schemas.document import Citation

# 对外复用：问答 / Hit Test 统一走表格优先注入
__all__ = [
    "build_citations",
    "build_citation_groups",
    "build_context",
    "prefer_full_tables",
    "stream_answer",
]


def build_citations(hits: list[Hit]) -> list[Citation]:
    cites: list[Citation] = []
    for h in prefer_full_tables(hits):
        snippet = h.chunk.content.strip()
        # 表格引用尽量保留整表，避免裁成碎片
        limit = 2000 if h.chunk.is_table else 480
        if len(snippet) > limit:
            snippet = snippet[:limit] + "…"
        cites.append(
            Citation(
                doc_id=h.document.id,
                title=h.document.title,
                page=h.chunk.page_no,
                snippet=snippet,
                chunk_id=h.chunk.id,
                score=round(h.score, 4),
                classification=int(getattr(h.document, "classification", 2) or 2),
            )
        )
    return cites


def build_citation_groups(hits: list[Hit]) -> dict:
    """四类引用结构：库 / 参考来源 / 图谱 / 配图（后两类占位）。"""
    ordered = prefer_full_tables(hits)
    sources = [c.model_dump() for c in build_citations(hits)]
    libs: dict[int, dict] = {}
    for h in ordered:
        d = h.document
        if d.id not in libs:
            libs[d.id] = {
                "doc_id": d.id,
                "title": d.title,
                "source_type": d.source_type,
                "hit_chunks": 0,
            }
        libs[d.id]["hit_chunks"] += 1
    return {
        "libraries": list(libs.values()),
        "sources": sources,
        "graph": [],
        "images": [],
    }


SYSTEM_PROMPT = (
    "你是企业知识库助手「知枢」。仅依据给定资料回答用户问题；"
    "若资料不足，明确说明未找到相关内容，不要编造制度或数据。"
    "回答使用简体中文 Markdown：可用标题、列表、加粗；不要把整篇原文粘贴进回答。"
)


def stream_answer(question: str, hits: list[Hit]) -> Iterator[str]:
    from app.rag.llm_client import load_runtime

    ordered = prefer_full_tables(hits)
    context = build_context(ordered)
    if not ordered or not context.strip():
        yield "未在知识库中找到相关资料，请补充文档或换一种问法。"
        return
    rt = load_runtime()
    # 渠道=stub，或仍开启全局 stub 且未切到真实渠道时，走模板回答
    if not rt.use_llm:
        yield from _stub_stream(question, ordered)
        return
    yield from _llm_stream(question, context, rt)


def _stub_stream(question: str, hits: list[Hit]) -> Iterator[str]:
    """从命中块中抽取与问题相关的条目，输出可读 Markdown。"""
    ordered = prefer_full_tables(hits)
    table_hits = [h for h in ordered if h.chunk.is_table]
    bullets = _extract_bullets(question, ordered)
    sources = []
    seen: set[int] = set()
    for h in ordered[:3]:
        if h.document.id in seen:
            continue
        seen.add(h.document.id)
        page = f"p.{h.chunk.page_no}" if h.chunk.page_no else "全文"
        tag = " · 全表" if h.chunk.is_table else ""
        sources.append(f"- **{h.document.title}** · {page}{tag}")

    # 去掉「A / B / C」这种从表行拆出的碎要点（表已完整展示时更丑）
    clean_bullets = [b for b in bullets if b.count(" / ") < 2]

    if table_hits:
        table_md = table_hits[0].chunk.content.strip()
        body = (
            f"根据知识库现行资料，关于「**{question}**」"
            f"（依据《{table_hits[0].document.title}》**全表**）：\n\n"
            f"{table_md}\n\n"
            f"**参考来源**\n"
            + "\n".join(sources)
        )
    elif clean_bullets:
        body = (
            f"根据知识库现行资料，关于「**{question}**」：\n\n"
            + "\n".join(f"- {b}" for b in clean_bullets)
            + "\n\n**参考来源**\n"
            + "\n".join(sources)
        )
    else:
        excerpt = _clean_excerpt(ordered[0].chunk.content, limit=280)
        body = (
            f"根据《{ordered[0].document.title}》相关段落：\n\n"
            f"{excerpt}\n\n"
            f"**参考来源**\n"
            + "\n".join(sources)
        )

    # 模拟流式
    step = max(12, len(body) // 8)
    for i in range(0, len(body), step):
        yield body[i : i + step]


def _extract_bullets(question: str, hits: list[Hit]) -> list[str]:
    keys = _question_keys(question)
    found: list[str] = []
    for h in prefer_full_tables(hits)[:4]:
        for line in h.chunk.content.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            # Markdown 表行 → 「列1 / 列2 / …」
            if raw.count("|") >= 2:
                cells = [c.strip() for c in raw.strip("|").split("|")]
                if cells and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells):
                    continue  # 表头分隔行
                text = " / ".join(c for c in cells if c)
            else:
                text = re.sub(r"^[-*•]\s*", "", raw).strip()
                text = re.sub(r"^\d+[\.、]\s*", "", text).strip()
            if len(text) < 4:
                continue
            if text.startswith(("适用范围", "本制度")):
                continue
            if re.fullmatch(r"[\u4e00-\u9fff]{2,12}(标准|规定|说明|范围)?", text) and "元" not in text:
                continue
            if keys and not any(k in text for k in keys):
                if not re.search(r"(上限|元/|可报销|不得|需.*审批|档|级)", text):
                    continue
            if text not in found:
                found.append(text)
            if len(found) >= 5:
                return found
    return found


def _question_keys(question: str) -> list[str]:
    keys = re.findall(r"[\u4e00-\u9fff]{2,}", question)
    out: list[str] = []
    for k in keys:
        if len(k) <= 2:
            out.append(k)
        else:
            for i in range(len(k) - 1):
                out.append(k[i : i + 2])
    # 去重保序
    seen: set[str] = set()
    uniq: list[str] = []
    for k in out:
        if k not in seen and k not in {"多少", "什么", "如何", "是否"}:
            seen.add(k)
            uniq.append(k)
    return uniq[:12]


def _clean_excerpt(text: str, limit: int) -> str:
    # 保留 markdown 结构，仅截断过长内容
    t = text.strip()
    if len(t) <= limit:
        return t
    return t[:limit].rstrip() + "…"


def _llm_stream(question: str, context: str, runtime) -> Iterator[str]:
    from app.rag.llm_client import chat_completion

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"资料：\n{context}\n\n问题：{question}",
        },
    ]
    yield from chat_completion(
        messages=messages,
        stream=True,
        temperature=0.2,
        timeout=None,
        runtime=runtime,
    )
