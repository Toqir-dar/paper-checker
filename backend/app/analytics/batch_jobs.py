"""Map/Reduce-style orchestrator for batch data-mining analytics."""

from __future__ import annotations

import logging
from collections import defaultdict

import numpy as np

from app.analytics.clustering import cluster_embeddings
from app.analytics.eda import analyze_batch_scores, parse_roll_numeric
from app.analytics.graph_pagerank import pagerank
from app.analytics.itemsets import mine_itemsets
from app.analytics.minhash_lsh import find_near_duplicates
from app.analytics.recommender import (
    collaborative_recommendations,
    content_recommendations,
    evaluate_recommendations,
    merge_recommendations,
)
from app.analytics.reservoir import ReservoirSampler
from app.grading.similarity import embed_texts
from app.models.batch import BatchDetail
from app.models.batch_analytics import (
    AssociationRuleOut,
    AuditSample,
    BatchAnalytics,
    ClusterAssignment,
    CorrelationOut,
    EdaOut,
    ElbowPoint,
    ItemsetAnalytics,
    LshPair,
    LshQuestionMetrics,
    PageRankScore,
    RecommendationOut,
    RecommenderEvalOut,
)

logger = logging.getLogger(__name__)


def _map_submission_records(detail: BatchDetail) -> list[dict]:
    """Map step: one record per graded submission with answers and miss basket."""
    records: list[dict] = []
    for row in detail.rows:
        sub = row.submission
        result = row.result
        if sub.id is None:
            continue
        text_by_q = {tr.question_id: tr.answer_text for tr in sub.text_responses}
        miss_basket: set[str] = set()
        score_frac = None
        if result is not None:
            if result.total_points_possible > 0:
                score_frac = result.total_points_awarded / result.total_points_possible
            for g in result.question_grades:
                if g.points_awarded < g.points_possible:
                    miss_basket.add(g.question_id)
        records.append(
            {
                "submission_id": sub.id,
                "roll_number": sub.roll_number or "",
                "text_by_q": text_by_q,
                "miss_basket": miss_basket,
                "score_frac": score_frac,
            }
        )
    return records


async def run_batch_analytics(
    detail: BatchDetail,
    *,
    itemset_method: str = "apriori",
    lsh_threshold: float = 0.5,
    reservoir_k: int = 8,
) -> BatchAnalytics:
    """Reduce mapped submission records into LSH, clusters, itemsets, PR, EDA."""
    batch = detail.batch
    if batch.id is None:
        raise ValueError("batch.id is required")

    mapped = _map_submission_records(detail)
    warnings: list[str] = []
    if not mapped:
        warnings.append("Batch has no submissions to analyze.")
        return BatchAnalytics(
            batch_id=batch.id,
            answer_key_id=batch.answer_key_id,
            warnings=warnings,
        )

    # --- LSH per question (reduce over mapped text answers) ---
    texts_by_q: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for rec in mapped:
        for qid, text in rec["text_by_q"].items():
            if text and text.strip():
                texts_by_q[qid].append((rec["submission_id"], rec["roll_number"], text))

    lsh_pairs: list[LshPair] = []
    lsh_metrics: list[LshQuestionMetrics] = []
    similarity_edges: list[tuple[str, str, float]] = []

    for qid, entries in texts_by_q.items():
        texts = [e[2] for e in entries]
        run = find_near_duplicates(texts, threshold=lsh_threshold)
        lsh_metrics.append(
            LshQuestionMetrics(
                question_id=qid,
                brute_similar_pairs=run.brute_similar_pairs,
                lsh_candidates=run.lsh_candidates,
                false_positives=run.false_positives,
                false_negatives=run.false_negatives,
                threshold=run.threshold,
            )
        )
        # Optional cosine second signal for candidate pairs.
        cosine_cache: dict[tuple[int, int], float] = {}
        try:
            if run.pairs:
                vectors = await embed_texts(texts)
                for pair in run.pairs:
                    va = np.asarray(vectors[pair.index_a])
                    vb = np.asarray(vectors[pair.index_b])
                    cosine_cache[(pair.index_a, pair.index_b)] = float(max(0.0, np.dot(va, vb)))
        except Exception as exc:  # noqa: BLE001 — analytics must not fail grading UX
            logger.warning("Embedding cosine for LSH pairs failed: %s", exc)
            warnings.append(f"Cosine second signal unavailable for {qid}.")

        for pair in run.pairs:
            a = entries[pair.index_a]
            b = entries[pair.index_b]
            cosine = cosine_cache.get((pair.index_a, pair.index_b))
            # Two-signal keep: strong Jaccard, or LSH candidate rescued by cosine.
            jaccard_hit = pair.jaccard >= lsh_threshold
            cosine_hit = (
                pair.lsh_candidate
                and cosine is not None
                and cosine >= lsh_threshold
            )
            if not (jaccard_hit or cosine_hit):
                continue
            lsh_pairs.append(
                LshPair(
                    question_id=qid,
                    submission_id_a=a[0],
                    submission_id_b=b[0],
                    roll_a=a[1],
                    roll_b=b[1],
                    jaccard=round(pair.jaccard, 4),
                    cosine=round(cosine, 4) if cosine is not None else None,
                    lsh_candidate=pair.lsh_candidate,
                )
            )
            weight = pair.jaccard if cosine is None else max(pair.jaccard, cosine)
            similarity_edges.append((a[0], b[0], weight))
            warnings.append(f"possible_near_duplicate:{a[1] or a[0]}-{b[1] or b[0]}:{qid}")

    # --- Clustering on concatenated answer embeddings ---
    concat_texts = [
        " ".join(rec["text_by_q"].values()).strip() or "(empty)"
        for rec in mapped
    ]
    clusters: list[ClusterAssignment] = []
    elbow_points: list[ElbowPoint] = []
    chosen_k = 0
    try:
        vectors = await embed_texts(concat_texts)
        clustering = cluster_embeddings(vectors)
        chosen_k = clustering.chosen_k
        elbow_points = [ElbowPoint(k=k, inertia=round(inertia, 4)) for k, inertia in clustering.elbow]
        for rec, label in zip(mapped, clustering.labels):
            clusters.append(
                ClusterAssignment(
                    submission_id=rec["submission_id"],
                    roll_number=rec["roll_number"],
                    cluster_id=int(label),
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Clustering failed: %s", exc)
        warnings.append("Clustering unavailable (embedding error).")

    # --- Frequent wrong-answer itemsets ---
    baskets = [rec["miss_basket"] for rec in mapped if rec["miss_basket"]]
    mining = mine_itemsets(baskets, method=itemset_method)
    itemsets = ItemsetAnalytics(
        method=mining.method,
        frequent_itemsets=mining.frequent_itemsets,
        rules=[
            AssociationRuleOut(
                antecedent=r.antecedent,
                consequent=r.consequent,
                support=r.support,
                confidence=r.confidence,
                lift=r.lift,
            )
            for r in mining.rules
        ],
    )

    # --- PageRank on similarity graph ---
    node_ids = [rec["submission_id"] for rec in mapped]
    pr = pagerank(node_ids, similarity_edges)
    roll_by_id = {rec["submission_id"]: rec["roll_number"] for rec in mapped}
    pagerank_scores = [
        PageRankScore(
            submission_id=sid,
            roll_number=roll_by_id.get(sid, ""),
            score=round(score, 6),
        )
        for sid, score in sorted(pr.scores.items(), key=lambda x: -x[1])
    ]

    # --- Reservoir audit samples ---
    sampler: ReservoirSampler[AuditSample] = ReservoirSampler(k=reservoir_k, seed=7)
    for rec in mapped:
        for qid, text in rec["text_by_q"].items():
            if text.strip():
                sampler.offer(
                    AuditSample(
                        submission_id=rec["submission_id"],
                        question_id=qid,
                        roll_number=rec["roll_number"],
                        answer_text=text[:500],
                    )
                )

    # --- Recommenders ---
    miss_matrix = {rec["submission_id"]: set(rec["miss_basket"]) for rec in mapped}
    question_ids = sorted({qid for rec in mapped for qid in rec["text_by_q"]})
    # Content embeddings: use question id strings as proxy when stem text is absent.
    q_embeddings: dict[str, list[float]] = {}
    try:
        if question_ids:
            q_vecs = await embed_texts(question_ids)
            q_embeddings = dict(zip(question_ids, q_vecs))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Question embedding for recommender failed: %s", exc)

    recommendations: dict[str, list[RecommendationOut]] = {}
    for rec in mapped:
        sid = rec["submission_id"]
        content = content_recommendations(list(rec["miss_basket"]), q_embeddings)
        collab = collaborative_recommendations(sid, miss_matrix)
        merged = merge_recommendations(content, collab)
        recommendations[sid] = [
            RecommendationOut(question_id=r.question_id, reason=r.reason, score=r.score)
            for r in merged
        ]
    eval_result = evaluate_recommendations(miss_matrix)
    recommender_eval = RecommenderEvalOut(
        rmse=eval_result.rmse,
        precision_at_k=eval_result.precision_at_k,
        k=eval_result.k,
        held_out=eval_result.held_out,
    )

    # --- EDA / Bonferroni ---
    scores = [rec["score_frac"] for rec in mapped if rec["score_frac"] is not None]
    rolls = [
        parse_roll_numeric(rec["roll_number"])
        for rec in mapped
        if rec["score_frac"] is not None
    ]
    eda_raw = analyze_batch_scores(scores, rolls)
    warnings.extend(eda_raw.warnings)
    eda = EdaOut(
        n_students=eda_raw.n_students,
        mean_score=eda_raw.mean_score,
        std_score=eda_raw.std_score,
        correlations=[
            CorrelationOut(
                feature_a=c.feature_a,
                feature_b=c.feature_b,
                pearson_r=c.pearson_r,
                p_value_approx=c.p_value_approx,
                significant_raw=c.significant_raw,
                significant_bonferroni=c.significant_bonferroni,
            )
            for c in eda_raw.correlations
        ],
    )

    return BatchAnalytics(
        batch_id=batch.id,
        answer_key_id=batch.answer_key_id,
        lsh_pairs=lsh_pairs,
        lsh_metrics=lsh_metrics,
        clusters=clusters,
        elbow=elbow_points,
        chosen_k=chosen_k,
        itemsets=itemsets,
        pagerank=pagerank_scores,
        audit_samples=sampler.sample,
        recommendations=recommendations,
        recommender_eval=recommender_eval,
        eda=eda,
        metrics={
            "mapped_submissions": len(mapped),
            "lsh_pair_count": len(lsh_pairs),
            "pagerank_iterations": pr.iterations,
            "pagerank_damping": pr.damping,
            "itemset_method": mining.method,
            "reservoir_seen": sampler.seen,
            "map_reduce": "map=per_submission; reduce=lsh+cluster+itemsets+pagerank+eda",
        },
        warnings=warnings,
    )
