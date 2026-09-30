"""
RAG Retriever (M9)
Simple keyword-based retrieval over KB documents (no embeddings needed for offline mode).
"""
import os
import re
from typing import Any

KB_DIR = os.path.join(os.path.dirname(__file__), "kb")
SIMILARITY_THRESHOLD = 0.15  # Minimum similarity to provide an answer


def load_kb() -> list[dict[str, Any]]:
    """Load all KB documents from the kb/ directory."""
    docs = []
    for fname in sorted(os.listdir(KB_DIR)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(KB_DIR, fname)
        with open(fpath, encoding="utf-8") as f:
            content = f.read()

        # Parse frontmatter
        meta: dict[str, str] = {}
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip()
                body = parts[2].strip()

        docs.append({
            "doc_id": meta.get("doc_id", fname),
            "title": meta.get("title", fname),
            "source_name": meta.get("source_name", ""),
            "source_url": meta.get("source_url", ""),
            "last_reviewed": meta.get("last_reviewed", ""),
            "content": body,
            "words": set(re.findall(r'\b\w+\b', body.lower())),
        })
    return docs


class RAGRetriever:
    """
    Keyword-based retriever for the approved knowledge base.
    Returns top-k matching documents above a similarity threshold.
    """

    def __init__(self, k: int = 3, threshold: float = SIMILARITY_THRESHOLD):
        self.docs = load_kb()
        self.k = k
        self.threshold = threshold

    def retrieve(self, query: str) -> list[dict[str, Any]]:
        """Return top-k docs matching the query, above threshold."""
        query_words = set(re.findall(r'\b\w+\b', query.lower()))
        # Remove common stop words
        stop = {"i", "a", "the", "is", "it", "my", "me", "do", "what", "how",
                "can", "should", "to", "for", "in", "on", "at", "of", "and"}
        query_words -= stop

        scored = []
        for doc in self.docs:
            if not query_words:
                continue
            overlap = len(query_words & doc["words"])
            score = overlap / len(query_words)
            if score >= self.threshold:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"score": s, **{k: v for k, v in d.items() if k != "words"}}
                for s, d in scored[:self.k]]

    def answer(self, query: str) -> dict[str, Any] | None:
        """Return an answer context or None if below threshold."""
        results = self.retrieve(query)
        if not results:
            return None
        return {
            "docs": results,
            "context": "\n\n".join(r["content"][:400] for r in results),
            "doc_ids": [r["doc_id"] for r in results],
        }


DEFERRAL_MESSAGE = "That's a great question. I'll note it for your doctor to address at your next visit."
