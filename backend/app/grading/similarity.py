import asyncio
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

# Small (~80MB), CPU-friendly, and — critically for a "no rate limits" grading
# pipeline — entirely local. No API call, no key, no quota for this step.
_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(_MODEL_NAME)


def _cosine_similarity_sync(text_a: str, text_b: str) -> float:
    model = _get_model()
    embeddings = model.encode([text_a, text_b], normalize_embeddings=True)
    raw_similarity = float(np.dot(embeddings[0], embeddings[1]))
    # Floor at 0 — a negative cosine just means "unrelated", not "negative credit".
    return max(0.0, min(1.0, raw_similarity))


async def cosine_similarity(text_a: str, text_b: str) -> float:
    """Semantic similarity between two texts, in [0, 1].

    Runs the (CPU-bound, synchronous) embedding model in a thread so it doesn't
    block the event loop alongside the async LLM calls elsewhere in grading.
    """
    return await asyncio.to_thread(_cosine_similarity_sync, text_a, text_b)
