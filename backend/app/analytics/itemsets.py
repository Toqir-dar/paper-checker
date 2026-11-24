"""A-Priori / PCY frequent itemsets and association rules on wrong-answer baskets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations


@dataclass
class AssociationRule:
    antecedent: list[str]
    consequent: list[str]
    support: float
    confidence: float
    lift: float


@dataclass
class ItemsetMiningResult:
    method: str
    frequent_itemsets: list[dict]
    rules: list[AssociationRule]


def _support(count: int, n_baskets: int) -> float:
    return count / n_baskets if n_baskets else 0.0


def apriori(
    baskets: list[set[str]],
    *,
    min_support: float = 0.2,
    min_confidence: float = 0.5,
) -> ItemsetMiningResult:
    n = len(baskets)
    if n == 0:
        return ItemsetMiningResult(method="apriori", frequent_itemsets=[], rules=[])

    min_count = max(1, int(np_ceil(min_support * n)))
    item_counts: Counter[str] = Counter()
    for basket in baskets:
        item_counts.update(basket)
    freq_1 = {frozenset([item]): c for item, c in item_counts.items() if c >= min_count}
    frequent: dict[frozenset[str], int] = dict(freq_1)

    prev_level = set(freq_1.keys())
    k = 2
    while prev_level:
        candidates = _generate_candidates(prev_level, k)
        counts: Counter[frozenset[str]] = Counter()
        for basket in baskets:
            for cand in candidates:
                if cand.issubset(basket):
                    counts[cand] += 1
        prev_level = {c for c, cnt in counts.items() if cnt >= min_count}
        for c in prev_level:
            frequent[c] = counts[c]
        k += 1

    itemsets = [
        {"items": sorted(items), "support": round(_support(cnt, n), 4), "count": cnt}
        for items, cnt in sorted(frequent.items(), key=lambda x: (-x[1], sorted(x[0])))
    ]
    rules = _association_rules(frequent, n, min_confidence=min_confidence)
    return ItemsetMiningResult(method="apriori", frequent_itemsets=itemsets, rules=rules)


def pcy(
    baskets: list[set[str]],
    *,
    min_support: float = 0.2,
    min_confidence: float = 0.5,
    hash_buckets: int = 64,
) -> ItemsetMiningResult:
    """PCY-style hash pruning of pair candidates, then A-Priori-style closure."""
    n = len(baskets)
    if n == 0:
        return ItemsetMiningResult(method="pcy", frequent_itemsets=[], rules=[])

    min_count = max(1, int(np_ceil(min_support * n)))
    item_counts: Counter[str] = Counter()
    bucket_counts = [0] * hash_buckets
    for basket in baskets:
        items = sorted(basket)
        item_counts.update(items)
        for a, b in combinations(items, 2):
            bucket_counts[_pair_hash(a, b, hash_buckets)] += 1

    freq_items = {item for item, c in item_counts.items() if c >= min_count}
    bitmap = [c >= min_count for c in bucket_counts]

    pair_counts: Counter[frozenset[str]] = Counter()
    for basket in baskets:
        items = sorted(i for i in basket if i in freq_items)
        for a, b in combinations(items, 2):
            if bitmap[_pair_hash(a, b, hash_buckets)]:
                pair_counts[frozenset([a, b])] += 1

    frequent: dict[frozenset[str], int] = {
        frozenset([item]): item_counts[item] for item in freq_items
    }
    for pair, cnt in pair_counts.items():
        if cnt >= min_count:
            frequent[pair] = cnt

    # Grow to larger sets without further PCY hashing.
    prev_level = {p for p in frequent if len(p) == 2}
    k = 3
    while prev_level:
        candidates = _generate_candidates(prev_level, k)
        counts: Counter[frozenset[str]] = Counter()
        for basket in baskets:
            for cand in candidates:
                if cand.issubset(basket):
                    counts[cand] += 1
        prev_level = {c for c, cnt in counts.items() if cnt >= min_count}
        for c in prev_level:
            frequent[c] = counts[c]
        k += 1

    itemsets = [
        {"items": sorted(items), "support": round(_support(cnt, n), 4), "count": cnt}
        for items, cnt in sorted(frequent.items(), key=lambda x: (-x[1], sorted(x[0])))
    ]
    rules = _association_rules(frequent, n, min_confidence=min_confidence)
    return ItemsetMiningResult(method="pcy", frequent_itemsets=itemsets, rules=rules)


def mine_itemsets(
    baskets: list[set[str]],
    *,
    method: str = "apriori",
    min_support: float = 0.2,
    min_confidence: float = 0.5,
) -> ItemsetMiningResult:
    if method == "pcy":
        return pcy(baskets, min_support=min_support, min_confidence=min_confidence)
    return apriori(baskets, min_support=min_support, min_confidence=min_confidence)


def np_ceil(x: float) -> int:
    import math

    return int(math.ceil(x))


def _pair_hash(a: str, b: str, buckets: int) -> int:
    return hash((a, b) if a < b else (b, a)) % buckets


def _generate_candidates(prev: set[frozenset[str]], k: int) -> set[frozenset[str]]:
    items = sorted({i for s in prev for i in s})
    candidates: set[frozenset[str]] = set()
    for combo in combinations(items, k):
        cand = frozenset(combo)
        if all(frozenset(sub) in prev for sub in combinations(combo, k - 1)):
            candidates.add(cand)
    return candidates


def _association_rules(
    frequent: dict[frozenset[str], int],
    n_baskets: int,
    *,
    min_confidence: float,
) -> list[AssociationRule]:
    rules: list[AssociationRule] = []
    for itemset, count in frequent.items():
        if len(itemset) < 2:
            continue
        items = list(itemset)
        for r in range(1, len(items)):
            for antecedent in combinations(items, r):
                ant = frozenset(antecedent)
                cons = itemset - ant
                if not cons or ant not in frequent:
                    continue
                conf = count / frequent[ant]
                if conf < min_confidence:
                    continue
                ant_sup = _support(frequent[ant], n_baskets)
                cons_sup = _support(frequent.get(cons, 0), n_baskets) if cons in frequent else 0.0
                lift = (conf / cons_sup) if cons_sup else 0.0
                rules.append(
                    AssociationRule(
                        antecedent=sorted(ant),
                        consequent=sorted(cons),
                        support=round(_support(count, n_baskets), 4),
                        confidence=round(conf, 4),
                        lift=round(lift, 4),
                    )
                )
    rules.sort(key=lambda r: (-r.confidence, -r.support, r.antecedent))
    return rules
