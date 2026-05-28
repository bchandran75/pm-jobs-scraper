"""Lightweight RAG index over resume text (TF-IDF, no extra ML deps)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1]


def chunk_resume(text: str, *, chunk_chars: int = 450, overlap: int = 80) -> list[str]:
    """Split resume into overlapping sections for retrieval."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    score: float


class ResumeRAG:
    """In-memory TF-IDF index over resume chunks."""

    def __init__(self, resume_text: str) -> None:
        self.chunks = chunk_resume(resume_text)
        self._chunk_tokens = [_tokenize(c) for c in self.chunks]
        self._idf = self._build_idf(self._chunk_tokens)
        self._vectors = [self._tfidf(tokens) for tokens in self._chunk_tokens]

    @staticmethod
    def _build_idf(all_tokens: list[list[str]]) -> dict[str, float]:
        n = len(all_tokens) or 1
        df: dict[str, int] = {}
        for tokens in all_tokens:
            for term in set(tokens):
                df[term] = df.get(term, 0) + 1
        return {term: math.log((n + 1) / (count + 1)) + 1.0 for term, count in df.items()}

    def _tfidf(self, tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        tf: dict[str, float] = {}
        for term in tokens:
            tf[term] = tf.get(term, 0.0) + 1.0
        total = float(len(tokens))
        vec: dict[str, float] = {}
        for term, count in tf.items():
            weight = (count / total) * self._idf.get(term, 1.0)
            if weight > 0:
                vec[term] = weight
        return vec

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(v * b.get(k, 0.0) for k, v in a.items())
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def retrieve(self, query: str, *, top_k: int = 5) -> list[RetrievedChunk]:
        if not self.chunks:
            return []
        q_vec = self._tfidf(_tokenize(query))
        scored = [
            (i, self._cosine(q_vec, self._vectors[i]))
            for i in range(len(self.chunks))
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        out: list[RetrievedChunk] = []
        for idx, score in scored[:top_k]:
            if score <= 0:
                continue
            out.append(RetrievedChunk(text=self.chunks[idx], score=score))
        return out

    def context_block(self, query: str, *, top_k: int = 5) -> str:
        chunks = self.retrieve(query, top_k=top_k)
        if not chunks:
            return ""
        return "\n---\n".join(c.text for c in chunks)
