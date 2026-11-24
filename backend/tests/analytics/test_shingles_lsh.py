from app.analytics.minhash_lsh import find_near_duplicates, minhash_signature
from app.analytics.shingles import jaccard, k_shingles


def test_identical_texts_jaccard_one():
    a = k_shingles("The quick brown fox jumps over the lazy dog")
    b = k_shingles("The quick brown fox jumps over the lazy dog")
    assert jaccard(a, b) == 1.0


def test_lsh_finds_near_copies():
    base = "Machine learning models require careful feature engineering and validation."
    texts = [
        base,
        base,  # exact copy
        "Completely unrelated answer about photosynthesis and chlorophyll.",
        "Machine learning models require careful feature engineering and validation!",
    ]
    result = find_near_duplicates(texts, threshold=0.5)
    pair_indexes = {(p.index_a, p.index_b) for p in result.pairs if p.jaccard >= 0.5}
    assert (0, 1) in pair_indexes
    assert result.lsh_candidates >= 1


def test_minhash_deterministic():
    s = k_shingles("deterministic shingle text for hashing")
    assert minhash_signature(s, num_hashes=32) == minhash_signature(s, num_hashes=32)
