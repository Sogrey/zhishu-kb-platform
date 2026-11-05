"""Reciprocal Rank Fusion（k=60）。"""

from __future__ import annotations

from collections import defaultdict
from typing import TypeVar

T = TypeVar("T")


def rrf_fuse(
    ranked_lists: list[list[T]],
    *,
    k: int = 60,
    key_fn=lambda x: id(x),
) -> list[tuple[T, float]]:
    """对多路有序列表做 RRF，返回 (item, score) 降序。"""
    scores: dict[object, float] = defaultdict(float)
    items: dict[object, T] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            kid = key_fn(item)
            scores[kid] += 1.0 / (k + rank)
            items[kid] = item
    fused = [(items[kid], score) for kid, score in scores.items()]
    fused.sort(key=lambda x: x[1], reverse=True)
    return fused
