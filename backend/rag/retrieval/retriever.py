"""Public entry point for the RAG module (the contract Person 1 calls):

    from rag.retrieval.retriever import retrieve_context
    retrieve_context(question: str, top_k: int = 5) -> dict
    {"context": "...", "sources": [{"document_id", "title", "chunk_id", ...}], "retrieval_metadata": {...}}

Behaviour
  * hybrid search = BM25 keyword search + vector search, fused with Reciprocal Rank Fusion
  * ABSTAINS (context "", sources []) when the evidence is weak or the question is empty; metadata says why
  * every returned passage carries its verification status; demo-labelled text is marked as such in the context
  * raises RagUnavailable when the store or model cannot be used - the backend should turn that into a safe error reply
Configuration comes from environment variables (see .env.example).
"""

import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

from rag.retrieval.bm25_retriever import BM25Retriever
from rag.retrieval.vector_retriever import VectorRetriever
from rag.retrieval.hybrid_retriever import rrf_fuse
from rag.retrieval.guards import unknown_phrases

MAX_QUESTION_CHARS = 500
MAX_PER_DOC = 2
DUPLICATE_SIMILARITY_THRESHOLD = 0.90
CALIBRATION = Path("rag/evaluation/calibration.json")


class RagUnavailable(RuntimeError):
    """Search could not run (database down, wrong embedding model, missing files)."""


def _empty(top_k, reason, **meta):
    return {
        "context": "",
        "sources": [],
        "retrieval_metadata": {
            "top_k": top_k,
            "returned": 0,
            "abstained": True,
            "reason": reason,
            **meta,
        },
    }


def _normalise_text(text):
    """Normalize passage text before comparing it for near-duplicates."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _is_duplicate(text, selected_texts, threshold=DUPLICATE_SIMILARITY_THRESHOLD):
    """Return True when text is identical or very similar to a selected passage."""
    normalized = _normalise_text(text)
    if not normalized:
        return False

    for existing_text in selected_texts:
        existing = _normalise_text(existing_text)
        if not existing:
            continue
        if normalized == existing:
            return True
        if SequenceMatcher(None, normalized, existing).ratio() >= threshold:
            return True

    return False


class RagEngine:
    def __init__(self, store, model, keyword_backend="bm25", weights=None, thresholds=None):
        stored = (store.manifest or {}).get("model_id")
        if stored and stored != model.model_id:
            raise RagUnavailable(
                f"stored vectors came from '{stored}' but the query model is '{model.model_id}'. Use the same model."
            )

        self.store, self.model, self.keyword_backend = store, model, keyword_backend
        self.weights = weights or {"keyword": 1.0, "vector": 1.0}
        self.vector = VectorRetriever(model, store)
        ids, texts = store.chunk_texts()
        self.bm25 = BM25Retriever(ids, texts)
        self.corpus_lower = "\n".join(texts).lower()  # for the unknown-product guard
        self.thresholds, self.calibrated = self._load_thresholds(thresholds)

    def _load_thresholds(self, override):
        if override:
            return override, True

        if CALIBRATION.exists():
            cal = json.loads(CALIBRATION.read_text()).get(self.model.model_id)
            if cal:
                return {
                    "min_cosine": cal["min_cosine"],
                    "min_coverage": cal["min_coverage"],
                }, True

        return {
            "min_cosine": float(os.getenv("RAG_MIN_COSINE", 0.5)),
            "min_coverage": float(os.getenv("RAG_MIN_COVERAGE", 0.2)),
        }, False

    def rank(self, question, n=30, mode="hybrid"):
        """Raw ranking, used by the evaluation script: [(chunk_id, fused_score, {search: rank})]"""
        kw = (
            self.store.keyword_fts(question, n)
            if self.keyword_backend == "fts"
            else self.bm25.search(question, n)
        )
        vec = self.vector.search(question, n)

        if mode == "keyword":
            return [(c, s, {"keyword": r}) for r, (c, s) in enumerate(kw, 1)], kw, vec
        if mode == "vector":
            return [(c, s, {"vector": r}) for r, (c, s) in enumerate(vec, 1)], kw, vec

        return rrf_fuse({"keyword": kw, "vector": vec}, self.weights, n), kw, vec

    def retrieve(self, question, top_k=5):
        top_k = max(1, min(int(top_k), 20))
        q = " ".join(str(question or "").split())[:MAX_QUESTION_CHARS]
        base = {
            "embedding_model": self.model.model_id,
            "standin_model": self.model.is_standin,
            "retrieval_mode": "hybrid_rrf",
            "keyword_backend": self.keyword_backend,
            "calibrated": self.calibrated,
        }

        if not q:
            return _empty(top_k, "empty_question", **base)

        unk = unknown_phrases(q, self.corpus_lower)
        if unk:
            return _empty(top_k, "unknown_named_product", unknown_terms=unk, **base)

        fused, kw, vec = self.rank(q, n=max(30, top_k * 6))
        if not fused:
            return _empty(top_k, "no_candidates", **base)

        cos_top = vec[0][1] if vec else 0.0
        head = [c for c, _, _ in fused[:3]]
        cov_top = max(self.bm25.coverage_by_id(q, c) for c in head)
        sig = {
            "confidence": round(cos_top, 4),
            "lexical_coverage": round(cov_top, 4),
            **base,
        }

        if (
            cos_top < self.thresholds["min_cosine"]
            or cov_top < self.thresholds["min_coverage"]
        ):
            return _empty(top_k, "low_confidence", **sig)

        # Fetch candidate records once, then select the highest-ranked unique passages.
        chosen = []
        per_doc = {}
        selected_texts = []
        recs = self.store.fetch([c for c, _, _ in fused])

        for cid, score, ranks in fused:
            record = recs.get(cid)
            if not record:
                continue

            document_id = record["document_id"]
            chunk_text = record["chunk_text"]

            # Keep the existing limit on chunks selected from one document.
            if per_doc.get(document_id, 0) >= MAX_PER_DOC:
                continue

            # Also skip near-identical text, even when it has a different document ID.
            if _is_duplicate(chunk_text, selected_texts):
                continue

            per_doc[document_id] = per_doc.get(document_id, 0) + 1
            selected_texts.append(chunk_text)
            chosen.append((cid, score, ranks, record))

            if len(chosen) == top_k:
                break

        if not chosen:
            return _empty(top_k, "no_unique_candidates", **sig)

        parts = []
        sources = []
        for number, (cid, score, ranks, record) in enumerate(chosen, 1):
            if record["verification_status"] == "DEMO_LABELLED":
                label = record["answer_label"]
            else:
                label = f"Verified public source: {record['source_url']}"

            parts.append(
                f"[Source {number}: {record['title']} | {record['document_id']} | {label}]\n"
                f"{record['chunk_text']}"
            )
            sources.append(
                {
                    "document_id": record["document_id"],
                    "title": record["title"],
                    "chunk_id": cid,
                    "verification_status": record["verification_status"],
                    "score": round(score, 5),
                }
            )

        return {
            "context": "\n\n".join(parts),
            "sources": sources,
            "retrieval_metadata": {
                "top_k": top_k,
                "returned": len(sources),
                "abstained": False,
                "reason": "ok",
                **sig,
            },
        }


_engine = None


def get_engine() -> RagEngine:
    global _engine
    if _engine is None:
        try:
            from rag.embeddings.embedding_model import EmbeddingModel

            model = EmbeddingModel()
            kind = os.getenv("RAG_STORE") or ("pg" if os.getenv("DATABASE_URL") else "file")

            if kind == "pg":
                from rag.retrieval.stores import PgStore

                store = PgStore()
            else:
                from rag.retrieval.stores import FileStore
                from rag.embeddings.generate_embeddings import tag_for

                store = FileStore(
                    os.getenv("RAG_EMBEDDINGS_DIR")
                    or f"rag/data/embeddings/{tag_for(model.model_id)}"
                )

            _engine = RagEngine(
                store,
                model,
                keyword_backend=os.getenv("KEYWORD_BACKEND", "bm25"),
            )
        except RagUnavailable:
            raise
        except Exception as error:
            raise RagUnavailable(f"{type(error).__name__}: {error}") from error

    return _engine


def retrieve_context(question: str, top_k: int = int(os.getenv("TOP_K", 5))) -> dict:
    return get_engine().retrieve(question, top_k)
