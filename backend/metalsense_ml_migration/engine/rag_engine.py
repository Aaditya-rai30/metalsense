from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class RAGEngine:
    def __init__(self, rag_dir="rag_docs", standards_dir="standards"):
        self.rag_dir = Path(rag_dir)
        self.standards_dir = Path(standards_dir)
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True)
        self.docs = []
        self.matrix = None
        self.refresh()

    def refresh(self):
        docs = []
        for directory in [self.rag_dir, self.standards_dir]:
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

    def _read(self, path):
        if path.suffix.lower() == ".pdf":
            try:
                import fitz
                doc = fitz.open(path)
                return "\n".join(p.get_text("text") for p in doc)
            except Exception:
                return ""
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            try:
                return pd.read_csv(path).to_csv(index=False)
            except Exception:
                return ""

    def sources(self):
        return [{"source": d["source"]} for d in self.docs]

    def retrieve(self, question, top_k=6):
        if not self.docs or self.matrix is None:
            return []
        q = self.vectorizer.transform([question])
        scores = cosine_similarity(q, self.matrix).ravel()
        idx = np.argsort(scores)[::-1][:top_k]
        return [{"source": self.docs[i]["source"], "score": float(scores[i]), "text": self.docs[i]["text"][:5000]} for i in idx if scores[i] > 0]

    def answer(self, question, context=None, top_k=6):
        hits = self.retrieve(question, top_k)
        context = context or {}
        evidence = []
        for h in hits:
            evidence.append({"source": h["source"], "score": round(h["score"], 4), "excerpt": h["text"][:1200]})
        if not hits:
            answer = "No sufficiently relevant indexed source was found. I cannot make an evidence-grounded claim from the current knowledge base."
        else:
            best = hits[0]
            answer = (
                "Evidence-grounded retrieval found the following relevant source(s). "
                "The backend does not invent unsupported regulatory values or conclusions. "
                f"Most relevant source: {best['source']}. "
                "Review the cited excerpts before using the result for a regulatory decision."
            )
        return {"question": question, "answer": answer, "evidence": evidence, "context_used": bool(context), "grounding": "retrieval_only"}
