"""Content-based and collaborative recommenders for review topics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np


@dataclass
class Recommendation:
    question_id: str
    reason: str
    score: float


@dataclass
class RecommenderEval:
    rmse: float | None
    precision_at_k: float | None
    k: int
    held_out: int


def content_recommendations(
    missed_question_ids: list[str],
    question_embeddings: dict[str, list[float]],
    *,
    top_k: int = 5,
) -> list[Recommendation]:
    """Recommend questions similar (in embedding space) to ones the student missed."""
    if not missed_question_ids or not question_embeddings:
        return []

    missed_vecs = [
        np.asarray(question_embeddings[qid], dtype=float)
        for qid in missed_question_ids
        if qid in question_embeddings
    ]
    if not missed_vecs:
        return []

    profile = np.mean(missed_vecs, axis=0)
    profile_norm = np.linalg.norm(profile) or 1.0
    profile = profile / profile_norm

    scored: list[Recommendation] = []
    missed_set = set(missed_question_ids)
    for qid, vec in question_embeddings.items():
        if qid in missed_set:
            continue
        v = np.asarray(vec, dtype=float)
        denom = (np.linalg.norm(v) * profile_norm) or 1.0
        sim = float(np.dot(profile, v) / denom)
        scored.append(
            Recommendation(
                question_id=qid,
                reason="similar to missed questions (content)",
                score=round(max(0.0, sim), 4),
            )
        )
    scored.sort(key=lambda r: -r.score)
    return scored[:top_k]


def collaborative_recommendations(
    target_submission_id: str,
    miss_matrix: dict[str, set[str]],
    *,
    top_k: int = 5,
) -> list[Recommendation]:
    """User-user CF: students with similar miss patterns suggest review questions."""
    target_misses = miss_matrix.get(target_submission_id, set())
    if not target_misses:
        return []

    scores: dict[str, float] = defaultdict(float)
    for other_id, other_misses in miss_matrix.items():
        if other_id == target_submission_id or not other_misses:
            continue
        inter = len(target_misses & other_misses)
        union = len(target_misses | other_misses)
        sim = inter / union if union else 0.0
        if sim <= 0:
            continue
        for qid in other_misses - target_misses:
            scores[qid] += sim

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return [
        Recommendation(
            question_id=qid,
            reason="students with similar misses also missed this (CF)",
            score=round(score, 4),
        )
        for qid, score in ranked[:top_k]
    ]


def evaluate_recommendations(
    miss_matrix: dict[str, set[str]],
    *,
    k: int = 3,
) -> RecommenderEval:
    """Leave-one-out: hide one miss per student, Precision@k on CF predictions."""
    if len(miss_matrix) < 2:
        return RecommenderEval(rmse=None, precision_at_k=None, k=k, held_out=0)

    hits = 0
    held = 0
    sq_err = 0.0
    err_n = 0

    for sid, misses in miss_matrix.items():
        if len(misses) < 2:
            continue
        held_qid = sorted(misses)[0]
        reduced = {s: (m - {held_qid} if s == sid else set(m)) for s, m in miss_matrix.items()}
        recs = collaborative_recommendations(sid, reduced, top_k=k)
        predicted_ids = {r.question_id for r in recs}
        held += 1
        if held_qid in predicted_ids:
            hits += 1
        # Treat "would miss" probability as min(1, CF score); target is 1 for held miss.
        pred = next((r.score for r in recs if r.question_id == held_qid), 0.0)
        pred = min(1.0, pred)
        sq_err += (1.0 - pred) ** 2
        err_n += 1

    precision = hits / held if held else None
    rmse = (sq_err / err_n) ** 0.5 if err_n else None
    return RecommenderEval(
        rmse=round(rmse, 4) if rmse is not None else None,
        precision_at_k=round(precision, 4) if precision is not None else None,
        k=k,
        held_out=held,
    )


def merge_recommendations(
    content: list[Recommendation],
    collab: list[Recommendation],
    *,
    top_k: int = 5,
) -> list[Recommendation]:
    best: dict[str, Recommendation] = {}
    for rec in content + collab:
        existing = best.get(rec.question_id)
        if existing is None or rec.score > existing.score:
            best[rec.question_id] = rec
    return sorted(best.values(), key=lambda r: -r.score)[:top_k]
