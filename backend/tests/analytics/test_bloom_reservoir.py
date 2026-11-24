from app.analytics.bloom import BloomFilter, content_fingerprint
from app.analytics.reservoir import ReservoirSampler


def test_bloom_membership_and_fpr_smoke():
    bf = BloomFilter(capacity=1000, error_rate=0.01)
    bf.add("alpha")
    assert bf.might_contain("alpha")
    assert bf.false_positive_rate_estimate() >= 0.0


def test_content_fingerprint_stable():
    assert content_fingerprint(b"abc") == content_fingerprint(b"abc")
    assert content_fingerprint(b"abc") != content_fingerprint(b"abd")


def test_reservoir_size_and_uniform_cap():
    sampler: ReservoirSampler[int] = ReservoirSampler(k=5, seed=1)
    for i in range(100):
        sampler.offer(i)
    assert len(sampler.sample) == 5
    assert sampler.seen == 100
