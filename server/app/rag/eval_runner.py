"""评测 Runner（C-103）：检索+生成后由 ragas_judge 打四指标。"""

from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.eval import EvalCase, EvalRun, EvalRunItem, EvalSet
from app.rag.context_inject import prefer_full_tables
from app.rag.generate import stream_answer
from app.rag.ragas_judge import judge_case
from app.rag.rerank import rerank
from app.rag.retrieve import hybrid_search


def _passed(scores: dict[str, float], threshold: float = 0.45) -> bool:
    if scores.get("citation_hit", 0) < 0.5:
        return False
    avg = sum(scores.values()) / max(1, len(scores))
    return avg >= threshold


def run_eval_set(
    db: Session,
    *,
    eval_set: EvalSet,
    workspace_id: int,
    clearance: int,
    user_id: int | None,
    limit: int | None = None,
) -> EvalRun:
    cases = (
        db.query(EvalCase)
        .filter(EvalCase.set_id == eval_set.id, EvalCase.active.is_(True))
        .order_by(EvalCase.id.asc())
        .all()
    )
    if limit:
        cases = cases[:limit]

    run = EvalRun(
        set_id=eval_set.id,
        workspace_id=workspace_id,
        status="running",
        triggered_by=user_id,
        case_count=len(cases),
        metrics={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    score_sums: dict[str, float] = {
        "citation_hit": 0.0,
        "context_recall": 0.0,
        "answer_relevancy": 0.0,
        "faithfulness": 0.0,
    }
    engines: Counter[str] = Counter()
    passed = 0

    try:
        for case in cases:
            t0 = time.perf_counter()
            fused, _debug = hybrid_search(
                db,
                case.question,
                workspace_id=workspace_id,
                clearance=clearance,
                recall_k=50,
                top_k=20,
            )
            hits = prefer_full_tables(rerank(case.question, fused, top_n=8))
            answer = "".join(stream_answer(case.question, hits))
            context = "\n\n".join(h.chunk.content for h in hits)
            titles: list[str] = []
            seen: set[str] = set()
            for h in hits:
                title = h.document.title or ""
                if title and title not in seen:
                    seen.add(title)
                    titles.append(title)
            expected = list(case.expected_doc_titles or [])
            scores, engine = judge_case(
                question=case.question,
                answer=answer,
                context=context,
                hit_titles=titles,
                expected_titles=expected,
                expected_answer=case.expected_answer,
            )
            engines[engine] += 1
            ok = _passed(scores)
            if ok:
                passed += 1
            for k, v in scores.items():
                score_sums[k] = score_sums.get(k, 0.0) + v

            db.add(
                EvalRunItem(
                    run_id=run.id,
                    case_id=case.id,
                    question=case.question,
                    answer=answer,
                    hit_doc_titles=titles,
                    scores={**scores, "engine": engine},
                    passed=ok,
                    latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                )
            )
            db.commit()

        n = max(1, len(cases))
        metrics: dict[str, Any] = {
            k: round(v / n, 4) for k, v in score_sums.items()
        }
        metrics["pass_rate"] = round(passed / n, 4)
        # 主引擎：多数票
        metrics["engine"] = engines.most_common(1)[0][0] if engines else "heuristic"
        metrics["engine_counts"] = dict(engines)
        run.metrics = metrics
        run.passed_count = passed
        run.status = "done"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return run
    except Exception as e:  # noqa: BLE001
        run.status = "failed"
        run.error_message = str(e)[:2000]
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        raise
