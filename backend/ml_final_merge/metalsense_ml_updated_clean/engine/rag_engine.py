from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class RAGEngine:
    """Local retrieval-only RAG layer.

    It indexes local text/markdown/CSV/PDF sources and returns evidence excerpts.
    It intentionally does not invent regulatory claims or call an LLM.
    """

    def __init__(self, rag_dir="rag_docs", standards_dir="standards"):
        self.rag_dir = Path(rag_dir)
        self.standards_dir = Path(standards_dir)
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        self.docs: list[dict[str, Any]] = []
        self.matrix = None
        self.refresh()

    def _read(self, path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            try:
                import fitz
                doc = fitz.open(path)
                return "\n".join(page.get_text("text") for page in doc)
            except Exception:
                return ""
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            try:
                return pd.read_csv(path).to_csv(index=False)
            except Exception:
                return ""

    def refresh(self):
        docs = []
        for directory in (self.rag_dir, self.standards_dir):
            if not directory.exists():
                continue
            for path in directory.rglob("*"):
                if path.suffix.lower() not in {".txt", ".md", ".csv", ".pdf"}:
                    continue
                text = self._read(path)
                if text.strip():
                    docs.append({"source": str(path), "text": text[:200000]})
        self.docs = docs
        self.matrix = self.vectorizer.fit_transform([d["text"] for d in docs]) if docs else None

    def sources(self):
        return [{"source": d["source"]} for d in self.docs]

    def retrieve(self, question: str, top_k: int = 6):
        if not self.docs or self.matrix is None:
            return []
        q = self.vectorizer.transform([question])
        scores = cosine_similarity(q, self.matrix).ravel()
        idx = np.argsort(scores)[::-1][:top_k]
        return [
            {"source": self.docs[i]["source"], "score": float(scores[i]), "text": self.docs[i]["text"][:5000]}
            for i in idx
            if scores[i] > 0
        ]

    def answer(self, question: str, context: dict | None = None, top_k: int = 6):
        hits = self.retrieve(question, top_k)
        evidence = [
            {"source": h["source"], "score": round(h["score"], 4), "excerpt": h["text"][:1200]}
            for h in hits
        ]
        if not hits:
            answer = "No sufficiently relevant indexed source was found. I cannot make an evidence-grounded claim from the current knowledge base."
        else:
            answer = (
                "Evidence-grounded retrieval found relevant source material. "
                f"Most relevant source: {hits[0]['source']}. "
                "Review the cited excerpts before using the result for a regulatory decision."
            )
        return {
            "question": question,
            "answer": answer,
            "evidence": evidence,
            "context_used": bool(context),
            "grounding": "retrieval_only",
        }
