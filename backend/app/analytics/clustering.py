"""Hierarchical clustering and k-means/elbow on answer embedding vectors."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ClusteringResult:
    labels: list[int]
    elbow: list[tuple[int, float]]
    chosen_k: int
    linkage_condensed: list[float]


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return matrix / norms


def kmeans(
    vectors: np.ndarray,
    k: int,
    *,
    max_iter: int = 50,
    seed: int = 42,
) -> tuple[np.ndarray, float]:
    """Lloyd k-means; returns (labels, inertia)."""
    n = vectors.shape[0]
    if k < 1 or k > n:
        raise ValueError("k must be in 1..n")
    rng = np.random.default_rng(seed)
    centroids = vectors[rng.choice(n, size=k, replace=False)].copy()
    labels = np.zeros(n, dtype=int)
    for _ in range(max_iter):
        distances = ((vectors[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
        new_labels = distances.argmin(axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for c in range(k):
            members = vectors[labels == c]
            if len(members):
                centroids[c] = members.mean(axis=0)
    inertia = float(((vectors - centroids[labels]) ** 2).sum())
    return labels, inertia


def elbow_curve(vectors: np.ndarray, k_max: int | None = None) -> list[tuple[int, float]]:
    n = vectors.shape[0]
    if n == 0:
        return []
    upper = min(k_max or 10, n)
    return [(k, kmeans(vectors, k)[1]) for k in range(1, upper + 1)]


def choose_k_from_elbow(elbow: list[tuple[int, float]]) -> int:
    """Pick k at the largest drop in inertia (simple elbow heuristic)."""
    if not elbow:
        return 1
    if len(elbow) == 1:
        return elbow[0][0]
    best_k = elbow[0][0]
    best_drop = -1.0
    for (k0, i0), (k1, i1) in zip(elbow, elbow[1:]):
        drop = i0 - i1
        if drop > best_drop:
            best_drop = drop
            best_k = k1
    return max(1, best_k)


def hierarchical_labels(vectors: np.ndarray, k: int) -> tuple[list[int], list[float]]:
    """Agglomerative clustering via scipy if available; else fall back to k-means labels."""
    n = vectors.shape[0]
    if n == 0:
        return [], []
    if n == 1:
        return [0], []
    try:
        from scipy.cluster.hierarchy import fcluster, linkage
        from scipy.spatial.distance import pdist

        condensed = pdist(vectors, metric="euclidean")
        Z = linkage(condensed, method="average")
        labels = fcluster(Z, t=min(k, n), criterion="maxclust")
        return (labels - 1).astype(int).tolist(), condensed.astype(float).tolist()
    except ImportError:
        labels, _ = kmeans(vectors, min(k, n))
        return labels.tolist(), []


def cluster_embeddings(vectors: list[list[float]], k: int | None = None) -> ClusteringResult:
    if not vectors:
        return ClusteringResult(labels=[], elbow=[], chosen_k=0, linkage_condensed=[])
    matrix = _normalize_rows(np.asarray(vectors, dtype=float))
    elbow = elbow_curve(matrix)
    chosen = k if k is not None else choose_k_from_elbow(elbow)
    chosen = max(1, min(chosen, matrix.shape[0]))
    labels, condensed = hierarchical_labels(matrix, chosen)
    return ClusteringResult(
        labels=labels,
        elbow=elbow,
        chosen_k=chosen,
        linkage_condensed=condensed,
    )
