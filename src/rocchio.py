"""
Rocchio Relevance Feedback di atas Indeks PyLucene (Term Vectors).

Formula klasik Rocchio:
    q_m = alpha * q_0 + (beta / |D_r|) * sum(d_j in D_r) - (gamma / |D_nr|) * sum(d_k in D_nr)

Membaca term vectors dokumen langsung dari indeks PyLucene (reader.termVectors()),
menghitung vektor TF-IDF ternormalisasi L2, membentuk query berbobot baru,
dan mengeksekusi pencarian ulang pada model pilihan (BM25 / TF-IDF Klasik).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import lucene
from org.apache.lucene.index import DirectoryReader, Term
from org.apache.lucene.search import IndexSearcher, TermQuery
from org.apache.lucene.util import BytesRefIterator

from src.indexer import ensure_jvm
from src.retriever import SearchEngine

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"


def _get_doc_term_vector(reader: DirectoryReader, lucene_doc_id: int, field: str):
    """Kompatibel dengan API TermVectors di Lucene 9.x."""
    try:
        tvs = reader.termVectors()
        if tvs is not None:
            return tvs.get(lucene_doc_id, field)
    except Exception:
        pass
    try:
        return reader.getTermVector(lucene_doc_id, field)
    except Exception:
        return None


def _build_l2_tfidf_vector(
    reader: DirectoryReader, lucene_doc_id: int, num_docs: int
) -> dict[str, float]:
    terms = _get_doc_term_vector(reader, lucene_doc_id, "content_clean")
    if terms is None:
        return {}

    vec: dict[str, float] = {}
    terms_enum = terms.iterator()
    bytes_it = BytesRefIterator.cast_(terms_enum)
    while True:
        term_bytes = bytes_it.next()
        if term_bytes is None:
            break
        term_text = term_bytes.utf8ToString()
        tf = int(terms_enum.totalTermFreq())
        if tf <= 0:
            continue
        df = int(reader.docFreq(Term("content_clean", term_text)))
        idf = math.log((num_docs + 1.0) / (df + 1.0)) + 1.0
        weight = (1.0 + math.log(tf)) * idf
        vec[term_text] = weight

    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm > 0:
        vec = {k: v / norm for k, v in vec.items()}
    return vec


def _resolve_lucene_doc_ids(
    reader: DirectoryReader, doc_ids: list[str]
) -> dict[str, int]:
    searcher = IndexSearcher(reader)
    resolved: dict[str, int] = {}
    for did in doc_ids:
        top = searcher.search(TermQuery(Term("doc_id", did)), 1)
        if top.totalHits.value > 0:
            resolved[did] = int(top.scoreDocs[0].doc)
    return resolved


class RocchioFeedback:
    def __init__(self, engine: SearchEngine) -> None:
        self.engine = engine

    def refine(
        self,
        query_text: str,
        relevant_doc_ids: list[str],
        non_relevant_doc_ids: list[str] | None = None,
        model: str = "bm25_custom",
        alpha: float = 1.0,
        beta: float = 0.75,
        gamma: float = 0.15,
        top_terms: int = 12,
        top_k: int = 10,
    ) -> dict[str, Any]:
        ensure_jvm()
        non_relevant_doc_ids = non_relevant_doc_ids or []
        if model == "bm25_baseline":
            model = "bm25_custom"

        # Jalankan query awal untuk perbandingan peringkat
        initial = self.engine.search(query_text, model=model, top_k=top_k)
        initial_ranks = {r["doc_id"]: r["rank"] for r in initial["results"]}

        reader = self.engine._custom_reader
        num_docs = int(reader.numDocs())

        # Vektor query awal q_0 (TF-IDF ternormalisasi L2)
        q_tokens = self.engine.preprocessor.preprocess_tokens(query_text)
        q_counts: dict[str, int] = {}
        for tok in q_tokens:
            q_counts[tok] = q_counts.get(tok, 0) + 1

        q0_vec: dict[str, float] = {}
        for tok, tf in q_counts.items():
            df = int(reader.docFreq(Term("content_clean", tok)))
            idf = math.log((num_docs + 1.0) / (df + 1.0)) + 1.0
            q0_vec[tok] = (1.0 + math.log(tf)) * idf
        q0_norm = math.sqrt(sum(v * v for v in q0_vec.values()))
        if q0_norm > 0:
            q0_vec = {k: v / q0_norm for k, v in q0_vec.items()}

        all_ids = list(dict.fromkeys(relevant_doc_ids + non_relevant_doc_ids))
        lucene_id_map = _resolve_lucene_doc_ids(reader, all_ids)

        rel_vecs = [
            _build_l2_tfidf_vector(reader, lucene_id_map[did], num_docs)
            for did in relevant_doc_ids
            if did in lucene_id_map
        ]
        non_rel_vecs = [
            _build_l2_tfidf_vector(reader, lucene_id_map[did], num_docs)
            for did in non_relevant_doc_ids
            if did in lucene_id_map
        ]

        combined: dict[str, float] = {}
        for term, w in q0_vec.items():
            combined[term] = combined.get(term, 0.0) + alpha * w

        if rel_vecs:
            scale_rel = beta / len(rel_vecs)
            for dvec in rel_vecs:
                for term, w in dvec.items():
                    combined[term] = combined.get(term, 0.0) + scale_rel * w

        if non_rel_vecs:
            scale_nonrel = gamma / len(non_rel_vecs)
            for dvec in non_rel_vecs:
                for term, w in dvec.items():
                    combined[term] = combined.get(term, 0.0) - scale_nonrel * w

        # Buang bobot negatif/nol dan ambil top_terms
        positive_terms = {t: round(w, 4) for t, w in combined.items() if w > 0.0}
        sorted_terms = sorted(positive_terms.items(), key=lambda x: x[1], reverse=True)

        # Pastikan semua term asli query tetap ikut selama berbobot positif
        selected: dict[str, float] = {}
        for t in q0_vec:
            if t in positive_terms:
                selected[t] = positive_terms[t]
        for t, w in sorted_terms:
            if len(selected) >= top_terms:
                break
            selected.setdefault(t, w)

        refined_search = self.engine.execute_weighted_query(
            selected,
            model=model,
            top_k=top_k,
            highlight_terms=list(selected.keys()),
        )

        # Hitung perubahan peringkat dibanding hasil sebelum Rocchio
        for item in refined_search["results"]:
            prev_rank = initial_ranks.get(item["doc_id"])
            item["previous_rank"] = prev_rank
            item["rank_change"] = (prev_rank - item["rank"]) if prev_rank else None

        new_feedback_terms = [
            {"term": t, "weight": w, "from_original_query": t in q0_vec}
            for t, w in sorted(selected.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "query": query_text,
            "model": model,
            "parameters": {"alpha": alpha, "beta": beta, "gamma": gamma},
            "relevant_doc_ids": relevant_doc_ids,
            "non_relevant_doc_ids": non_relevant_doc_ids,
            "original_query_terms": q_tokens,
            "weighted_query_terms": new_feedback_terms,
            "initial_top_results": initial["results"],
            "refined_results": refined_search["results"],
            "total_hits": refined_search["total_hits"],
            "latency_ms": refined_search["latency_ms"],
        }


def generate_rocchio_demo() -> dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    engine = SearchEngine()
    rocchio = RocchioFeedback(engine)

    demo_queries = ["hujan malam di stasiun", "rindu ibu di kampung"]
    demos = []
    for q in demo_queries:
        init = engine.search(q, model="bm25_custom", top_k=10)
        results = init["results"]
        if len(results) >= 5:
            # Pilih 2 dokumen relevan (rank 2 & 4) dan 1 dokumen tidak relevan (rank 5) sebagai skenario demonstrasi
            rel_ids = [results[1]["doc_id"], results[3]["doc_id"]]
            non_rel_ids = [results[4]["doc_id"]]
        elif len(results) >= 2:
            rel_ids = [results[0]["doc_id"]]
            non_rel_ids = [results[-1]["doc_id"]]
        else:
            continue

        demo = rocchio.refine(
            q,
            relevant_doc_ids=rel_ids,
            non_relevant_doc_ids=non_rel_ids,
            model="bm25_custom",
            alpha=1.0,
            beta=0.75,
            gamma=0.15,
            top_k=5,
        )
        demos.append(demo)

    payload = {"demos": demos}
    out_path = REPORTS_DIR / "rocchio_demo.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


if __name__ == "__main__":
    data = generate_rocchio_demo()
    print(f"[ROCCHIO] {len(data['demos'])} demonstrasi Rocchio selesai.")
    for d in data["demos"]:
        top_terms_str = ", ".join(
            f"{t['term']}({t['weight']})" for t in d["weighted_query_terms"][:8]
        )
        print(f"  Query '{d['query']}' -> Weighted terms: {top_terms_str}")
