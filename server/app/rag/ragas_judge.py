"""RAGAS 风格四指标裁判（C-103）。

- citation_hit / context_recall：启发式（期望文档 + 关键词）
- answer_relevancy / faithfulness：优先 LLM JSON 打分；失败回退启发式
对齐 RAGAS 口径，不强制引入 ragas 重依赖（stub/内网友好）。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _tokens(text: str) -> set[str]:
    chars = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{2,}", text or "")
    out: set[str] = set()
    for t in chars:
        if len(t) <= 2:
            out.add(t)
        else:
            if re.search(r"[\u4e00-\u9fff]", t):
                for i in range(len(t) - 1):
                    out.add(t[i : i + 2])
            else:
                out.add(t.lower())
    return out


def _overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a))


def heuristic_scores(
    *,
    question: str,
    answer: str,
    context: str,
    hit_titles: list[str],
    expected_titles: list[str],
    expected_answer: str | None,
) -> dict[str, float]:
    q_tok = _tokens(question)
    a_tok = _tokens(answer)
    c_tok = _tokens(context)
    exp_a = _tokens(expected_answer or "")

    if expected_titles:
        joined = " ".join(hit_titles).lower()
        hits = sum(1 for t in expected_titles if (t or "").strip().lower() in joined)
        citation_hit = hits / max(1, len(expected_titles))
    else:
        citation_hit = 1.0 if hit_titles else 0.0

    recall_src = exp_a or q_tok
    context_recall = _overlap(recall_src, c_tok)
    answer_relevancy = _overlap(q_tok, a_tok)
    if exp_a:
        answer_relevancy = 0.5 * answer_relevancy + 0.5 * _overlap(exp_a, a_tok)
    faithfulness = _overlap(a_tok, c_tok) if a_tok else 0.0

    return {
        "citation_hit": round(citation_hit, 4),
        "context_recall": round(context_recall, 4),
        "answer_relevancy": round(answer_relevancy, 4),
        "faithfulness": round(faithfulness, 4),
    }


def use_llm_judge() -> bool:
    from app.rag.llm_client import load_runtime

    s = get_settings()
    if s.eval_llm_judge:
        return True
    # 设置页已切到真实渠道时，评测默认走 LLM 裁判
    return load_runtime().use_llm


def _extract_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    # 容错：截取首个 {...}
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _clamp01(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, x))


def llm_judge_scores(
    *,
    question: str,
    answer: str,
    context: str,
    expected_answer: str | None,
) -> dict[str, float] | None:
    """调用当前设置页渠道，返回 faithfulness / answer_relevancy（0~1）。"""
    from app.rag.llm_client import completion_text, load_runtime

    settings = get_settings()
    rt = load_runtime()
    if not rt.use_llm:
        return None
    ctx = (context or "")[:3500]
    ans = (answer or "")[:2000]
    exp = (expected_answer or "").strip()
    user = (
        "你是 RAG 评测裁判。仅输出 JSON，不要解释。字段：\n"
        '{"faithfulness":0到1小数,"answer_relevancy":0到1小数}\n'
        "faithfulness=回答是否完全由资料支持（无编造）；"
        "answer_relevancy=回答与问题相关程度"
        + ("；可参考期望要点：" + exp if exp else "")
        + f"。\n\n问题：{question}\n\n资料：\n{ctx}\n\n回答：\n{ans}"
    )
    try:
        content = completion_text(
            [
                {
                    "role": "system",
                    "content": "你是严格的 RAGAS 风格评分器，只输出合法 JSON。",
                },
                {"role": "user", "content": user},
            ],
            temperature=0,
            timeout=settings.eval_judge_timeout,
            runtime=rt,
        )
        obj = _extract_json(content or "")
        if not obj:
            return None
        faith = _clamp01(obj.get("faithfulness"))
        rel = _clamp01(obj.get("answer_relevancy"))
        if faith is None or rel is None:
            return None
        return {
            "faithfulness": round(faith, 4),
            "answer_relevancy": round(rel, 4),
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("llm judge failed: %s", e)
        return None


def judge_case(
    *,
    question: str,
    answer: str,
    context: str,
    hit_titles: list[str],
    expected_titles: list[str],
    expected_answer: str | None,
) -> tuple[dict[str, float], str]:
    """返回 (scores, engine)。engine: heuristic | llm_judge | llm_judge_fallback。"""
    base = heuristic_scores(
        question=question,
        answer=answer,
        context=context,
        hit_titles=hit_titles,
        expected_titles=expected_titles,
        expected_answer=expected_answer,
    )
    if not use_llm_judge():
        return base, "heuristic"

    llm = llm_judge_scores(
        question=question,
        answer=answer,
        context=context,
        expected_answer=expected_answer,
    )
    if not llm:
        return base, "llm_judge_fallback"

    merged = dict(base)
    merged["faithfulness"] = llm["faithfulness"]
    merged["answer_relevancy"] = llm["answer_relevancy"]
    return merged, "llm_judge"
