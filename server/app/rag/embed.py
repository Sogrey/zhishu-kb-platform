"""嵌入：stub 用确定性伪向量；正式模式调 TEI。"""

from __future__ import annotations

import hashlib
import math

import httpx
import numpy as np

from app.core.config import get_settings


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    if settings.zhishu_dev_stub:
        return [_stub_vector(t, settings.embedding_dim) for t in texts]
    return _tei_embed(texts, settings.tei_embed_url, settings.embedding_dim)


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def _stub_vector(text: str, dim: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    vec = rng.standard_normal(dim).astype(np.float32)
    # 混入长度信号，避免完全随机无关
    vec[0] += math.log1p(len(text)) * 0.01
    norm = float(np.linalg.norm(vec)) or 1.0
    return (vec / norm).tolist()


def _tei_embed(texts: list[str], base_url: str, dim: int) -> list[list[float]]:
    url = base_url.rstrip("/") + "/embed"
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, json={"inputs": texts})
        resp.raise_for_status()
        data = resp.json()
    # TEI 可能返回 list[list[float]] 或带 embeddings 字段
    if isinstance(data, list):
        vectors = data
    else:
        vectors = data.get("embeddings") or data.get("data") or []
    out: list[list[float]] = []
    for v in vectors:
        if len(v) != dim:
            # 截断或填充以匹配库维度
            if len(v) > dim:
                v = v[:dim]
            else:
                v = list(v) + [0.0] * (dim - len(v))
        out.append(v)
    return out
