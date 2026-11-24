"""Power-iteration PageRank on a student similarity graph."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PageRankResult:
    scores: dict[str, float]
    iterations: int
    damping: float


def pagerank(
    nodes: list[str],
    edges: list[tuple[str, str, float]],
    *,
    damping: float = 0.85,
    max_iter: int = 100,
    tol: float = 1e-8,
) -> PageRankResult:
    """Weighted PageRank; edge weight is similarity (higher = stronger link)."""
    n = len(nodes)
    if n == 0:
        return PageRankResult(scores={}, iterations=0, damping=damping)

    index = {node: i for i, node in enumerate(nodes)}
    out_weight = [0.0] * n
    adjacency: list[list[tuple[int, float]]] = [[] for _ in range(n)]

    for a, b, w in edges:
        if a not in index or b not in index or w <= 0:
            continue
        i, j = index[a], index[b]
        adjacency[i].append((j, w))
        adjacency[j].append((i, w))
        out_weight[i] += w
        out_weight[j] += w

    ranks = [1.0 / n] * n
    teleport = (1.0 - damping) / n
    iterations = 0
    for iterations in range(1, max_iter + 1):
        new_ranks = [teleport] * n
        for i, neighbors in enumerate(adjacency):
            if out_weight[i] == 0:
                # Dead end: distribute uniformly.
                share = damping * ranks[i] / n
                for j in range(n):
                    new_ranks[j] += share
                continue
            for j, w in neighbors:
                new_ranks[j] += damping * ranks[i] * (w / out_weight[i])
        delta = sum(abs(new_ranks[i] - ranks[i]) for i in range(n))
        ranks = new_ranks
        if delta < tol:
            break

    total = sum(ranks) or 1.0
    scores = {node: ranks[i] / total for node, i in index.items()}
    return PageRankResult(scores=scores, iterations=iterations, damping=damping)
