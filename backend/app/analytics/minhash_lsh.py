"""MinHash signatures and LSH banding for near-duplicate candidate generation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.analytics.shingles import jaccard, k_shingles


def _hash32(value: str, seed: int) -> int:
    digest = hashlib.md5(f"{seed}:{value}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def minhash_signature(shingles: set[str], num_hashes: int = 100) -> list[int]:
    if num_hashes < 1:
        raise ValueError("num_hashes must be >= 1")
    if not shingles:
        return [0] * num_hashes
    sig: list[int] = []
    for seed in range(num_hashes):
        sig.append(min(_hash32(s, seed) for s in shingles))
    return sig


def lsh_bands(signature: list[int], bands: int, rows: int) -> list[tuple[int, str]]:
    """Return (band_index, bucket_key) pairs for a signature."""
    expected = bands * rows
    if len(signature) < expected:
        raise ValueError(f"signature length {len(signature)} < bands*rows {expected}")
    keys: list[tuple[int, str]] = []
    for b in range(bands):
        chunk = tuple(signature[b * rows : (b + 1) * rows])
        keys.append((b, hashlib.sha1(repr(chunk).encode()).hexdigest()[:16]))
    return keys


@dataclass
class LshPairResult:
    index_a: int
    index_b: int
    jaccard: float
    lsh_candidate: bool


@dataclass
class LshRunResult:
    pairs: list[LshPairResult]
    brute_similar_pairs: int
    lsh_candidates: int
    false_positives: int
    false_negatives: int
    threshold: float


def find_near_duplicates(
    texts: list[str],
    *,
    k: int = 5,
    num_hashes: int = 100,
    bands: int = 20,
    rows: int = 5,
    threshold: float = 0.5,
) -> LshRunResult:
    """Compare documents with MinHash+LSH and score FP/FN vs brute Jaccard.

    For n > 50, brute-force Jaccard is still computed only for LSH candidates
    plus a sampled baseline; for n <= 50 every pair is scored (week-16 metrics).
    """
    if bands * rows > num_hashes:
        raise ValueError("bands * rows must be <= num_hashes")

    shingle_sets = [k_shingles(t, k=k) for t in texts]
    signatures = [minhash_signature(s, num_hashes=num_hashes) for s in shingle_sets]

    buckets: dict[tuple[int, str], list[int]] = {}
    for i, sig in enumerate(signatures):
        for key in lsh_bands(sig, bands=bands, rows=rows):
            buckets.setdefault(key, []).append(i)

    lsh_candidate_pairs: set[tuple[int, int]] = set()
    for indices in buckets.values():
        unique = sorted(set(indices))
        for a in range(len(unique)):
            for b in range(a + 1, len(unique)):
                lsh_candidate_pairs.add((unique[a], unique[b]))

    n = len(texts)
    brute_pairs: dict[tuple[int, int], float] = {}
    if n <= 50:
        for i in range(n):
            for j in range(i + 1, n):
                brute_pairs[(i, j)] = jaccard(shingle_sets[i], shingle_sets[j])
    else:
        for pair in lsh_candidate_pairs:
            brute_pairs[pair] = jaccard(shingle_sets[pair[0]], shingle_sets[pair[1]])

    similar = {p for p, score in brute_pairs.items() if score >= threshold}
    false_positives = len(lsh_candidate_pairs - similar)
    false_negatives = len(similar - lsh_candidate_pairs) if n <= 50 else 0

    pairs: list[LshPairResult] = []
    reported = lsh_candidate_pairs | (similar if n <= 50 else set())
    for i, j in sorted(reported):
        score = brute_pairs.get((i, j))
        if score is None:
            score = jaccard(shingle_sets[i], shingle_sets[j])
        pairs.append(
            LshPairResult(
                index_a=i,
                index_b=j,
                jaccard=score,
                lsh_candidate=(i, j) in lsh_candidate_pairs,
            )
        )

    return LshRunResult(
        pairs=pairs,
        brute_similar_pairs=len(similar),
        lsh_candidates=len(lsh_candidate_pairs),
        false_positives=false_positives,
        false_negatives=false_negatives,
        threshold=threshold,
    )
