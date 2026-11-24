import asyncio
from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

# Same MiniLM model as before, run through ONNX Runtime instead of PyTorch —
# fastembed has no torch dependency, which keeps the backend's install small
# enough to fit a serverless deploy's bundle size limit. Still small (~80MB
# quantized weights), CPU-friendly, and — critically for a "no rate limits"
# grading pipeline — entirely local. No API call, no key, no quota for this step.
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache
def _get_model() -> TextEmbedding:
    return TextEmbedding(model_name=_MODEL_NAME)


def _cosine_similarity_sync(text_a: str, text_b: str) -> float:
    model = _get_model()
    embedding_a, embedding_b = model.embed([text_a, text_b])
    # Normalize explicitly rather than assume fastembed's output already is —
    # cheap, and makes the dot product below a true cosine similarity either way.
    norm_a = embedding_a / np.linalg.norm(embedding_a)
    norm_b = embedding_b / np.linalg.norm(embedding_b)
    raw_similarity = float(np.dot(norm_a, norm_b))
    # Floor at 0 — a negative cosine just means "unrelated", not "negative credit".
    return max(0.0, min(1.0, raw_similarity))


async def cosine_similarity(text_a: str, text_b: str) -> float:
    """Semantic similarity between two texts, in [0, 1].

    Runs the (CPU-bound, synchronous) embedding model in a thread so it doesn't
    block the event loop alongside the async LLM calls elsewhere in grading.
    """
    return await asyncio.to_thread(_cosine_similarity_sync, text_a, text_b)


def _embed_texts_sync(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    vectors = list(model.embed(texts))
    out: list[list[float]] = []
    for vec in vectors:
        arr = np.asarray(vec, dtype=float)
        norm = np.linalg.norm(arr)
        if norm:
            arr = arr / norm
        out.append(arr.tolist())
    return out


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embed texts with MiniLM; returns L2-normalized vectors."""
    return await asyncio.to_thread(_embed_texts_sync, texts)
