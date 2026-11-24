import numpy as np

from app.analytics.clustering import cluster_embeddings, kmeans
from app.analytics.graph_pagerank import pagerank
from app.analytics.itemsets import mine_itemsets
from app.analytics.recommender import collaborative_recommendations, evaluate_recommendations
from app.analytics.eda import analyze_batch_scores


def test_apriori_finds_planted_co_wrongs():
    baskets = [
        {"q1", "q2"},
        {"q1", "q2"},
        {"q1", "q2", "q3"},
        {"q4"},
        {"q1", "q2"},
    ]
    result = mine_itemsets(baskets, method="apriori", min_support=0.5, min_confidence=0.5)
    itemsets = {frozenset(row["items"]) for row in result.frequent_itemsets}
    assert frozenset(["q1", "q2"]) in itemsets


def test_pcy_runs_on_same_baskets():
    baskets = [{"q1", "q2"}, {"q1", "q2"}, {"q1", "q3"}, {"q2", "q3"}]
    result = mine_itemsets(baskets, method="pcy", min_support=0.4)
    assert result.method == "pcy"
    assert result.frequent_itemsets


def test_kmeans_separates_two_blobs():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 0.1, size=(10, 4))
    b = rng.normal(5, 0.1, size=(10, 4))
    vectors = np.vstack([a, b])
    labels, inertia = kmeans(vectors, k=2, seed=0)
    assert len(set(labels.tolist())) == 2
    assert inertia >= 0


def test_cluster_embeddings_empty():
    result = cluster_embeddings([])
    assert result.labels == []


def test_pagerank_prefers_hub():
    nodes = ["a", "b", "c"]
    edges = [("a", "b", 1.0), ("a", "c", 1.0), ("b", "c", 0.2)]
    result = pagerank(nodes, edges, damping=0.85)
    assert abs(sum(result.scores.values()) - 1.0) < 1e-6
    assert result.scores["a"] > 0


def test_cf_and_eval():
    miss = {
        "s1": {"q1", "q2"},
        "s2": {"q1", "q2", "q3"},
        "s3": {"q4"},
    }
    recs = collaborative_recommendations("s1", miss, top_k=3)
    assert any(r.question_id == "q3" for r in recs)
    ev = evaluate_recommendations(miss, k=2)
    assert ev.held_out >= 1


def test_eda_bonferroni_warning_path():
    # Strong artificial correlation between score and roll digits
    scores = [i / 10 for i in range(10)]
    rolls = [float(i) for i in range(10)]
    metrics = analyze_batch_scores(scores, rolls, alpha=0.05)
    assert metrics.n_students == 10
    assert metrics.correlations
