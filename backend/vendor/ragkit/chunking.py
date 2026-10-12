"""Text chunking strategies for retrieval pipelines."""

from typing import List


def fixed_size_chunks(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into fixed-size character windows with overlap.

    Overlap carries context across chunk boundaries so a fact split by a
    boundary is still retrievable from at least one side.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")
    if not text:
        return []
    chunks = []
    step = chunk_size - overlap
    for start in range(0, len(text), step):
        chunk = text[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(text):
            break  # this window reached the end; later ones would only repeat its tail
    return chunks


def sentence_chunks(text: str, max_sentences: int = 4, overlap_sentences: int = 1) -> List[str]:
    """Split text into chunks of whole sentences.

    Prefers sentence boundaries over character counts, which keeps facts
    intact and usually improves retrieval quality on prose.
    """
    if max_sentences <= 0:
        raise ValueError("max_sentences must be positive")
    if overlap_sentences < 0 or overlap_sentences >= max_sentences:
        raise ValueError("overlap_sentences must be in [0, max_sentences)")
    sentences = _split_sentences(text)
    if not sentences:
        return []
    chunks = []
    step = max_sentences - overlap_sentences
    for start in range(0, len(sentences), step):
        chunk = " ".join(sentences[start:start + max_sentences]).strip()
        if chunk:
            chunks.append(chunk)
        if start + max_sentences >= len(sentences):
            break  # this window reached the last sentence; no repeat-only tail chunk
    return chunks


def _split_sentences(text: str) -> List[str]:
    """Lightweight sentence splitter that avoids a heavyweight NLP dependency."""
    import re
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text.strip())
    return [p.strip() for p in parts if p.strip()]
