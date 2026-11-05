"""Rerank：stub 用查询词重合打分；正式模式调 TEI /rerank。"""

from __future__ import annotations

import re

import httpx

from app.core.config import get_settings
from app.rag.retrieve import Hit


def rerank(query: str, hits: list[Hit], top_n: int = 8) -> list[Hit]:
    if not hits:
        return []
    settings = get_settings()
    if settings.zhishu_dev_stub or settings.use_sqlite:
        return _stub_rerank(query, hits, top_n)
    try:
        return _tei_rerank(query, hits, top_n, settings.tei_rerank_url)
    except Exception:
        return _stub_rerank(query, hits, top_n)


def _stub_rerank(query: str, hits: list[Hit], top_n: int) -> list[Hit]:
    tokens = set(_tokens(query))
    scored: list[tuple[float, Hit]] = []
    for h in hits:
        content = h.chunk.content.lower()
        overlap = sum(1 for t in tokens if t in content)
        # 保留召回分作次要信号
        score = overlap * 1.5 + float(h.score) * 0.1
        scored.append(
            (
                score,
                Hit(
                    chunk=h.chunk,
                    document=h.document,
                    score=score,
                    channels=list(h.channels),
                ),
            )
        )
    scored.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in scored[:top_n]]


def _tei_rerank(query: str, hits: list[Hit], top_n: int, base_url: str) -> list[Hit]:
    texts = [h.chunk.content for h in hits]
    url = base_url.rstrip("/") + "/rerank"
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, json={"query": query, "texts": texts})
        resp.raise_for_status()
        data = resp.json()
    # TEI 常见返回 [{index, score}, ...]
    results = data if isinstance(data, list) else data.get("results") or []
    paired: list[Hit] = []
    for row in results:
        idx = int(row.get("index", row.get("idx", -1)))
        score = float(row.get("score", 0))
        if 0 <= idx < len(hits):
            h = hits[idx]
            paired.append(Hit(chunk=h.chunk, document=h.document, score=score))
    paired.sort(key=lambda h: h.score, reverse=True)
    return paired[:top_n] or hits[:top_n]


def _tokens(text: str) -> list[str]:
    out: list[str] = re.findall(r"[A-Za-z0-9_]{2,}", text.lower())
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(run) <= 2:
            out.append(run)
        else:
            out.extend(run[i : i + 2] for i in range(len(run) - 1))
    return out
