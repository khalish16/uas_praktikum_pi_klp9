"""
Retrieval Engine berbasis Apache Lucene (PyLucene 9.12).

Mendukung 3 konfigurasi pencarian pada korpus yang sama:
1. bm25_custom   -> BM25Similarity(k1=1.2, b=0.75) + Custom Preprocessing (WhitespaceAnalyzer)
2. tfidf_custom  -> ClassicSimilarity (TF-IDF VSM) + Custom Preprocessing (WhitespaceAnalyzer)
3. bm25_baseline -> BM25Similarity(k1=1.2, b=0.75) + StandardAnalyzer bawaan Lucene (tanpa custom preprocessing)

Juga menyediakan ekstraksi Posting List langsung dari indeks Lucene serta
pengambilan dokumen lengkap untuk modal baca di antarmuka web.
"""

from __future__ import annotations

import html
import re
import time
from pathlib import Path
from typing import Any

import lucene
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.index import DirectoryReader, Term
from org.apache.lucene.queryparser.classic import QueryParser
from org.apache.lucene.search import BooleanClause, BooleanQuery, BoostQuery, IndexSearcher, TermQuery
from org.apache.lucene.search.similarities import BM25Similarity, ClassicSimilarity
from org.apache.lucene.store import FSDirectory
from java.nio.file import Paths

from src.indexer import BASELINE_INDEX_PATH, CUSTOM_INDEX_PATH, ensure_jvm, extract_posting_list
from src.preprocessing import CerpenPreprocessor
from src.query_expansion import QueryExpander

SUPPORTED_MODELS = {
    "bm25_custom": {
        "label": "BM25 + Custom Analyzer",
        "index_type": "custom",
        "similarity": "BM25Similarity(k1=1.2, b=0.75)",
    },
    "tfidf_custom": {
        "label": "TF-IDF Klasik (ClassicSimilarity) + Custom Analyzer",
        "index_type": "custom",
        "similarity": "ClassicSimilarity (TF-IDF VSM)",
    },
    "bm25_baseline": {
        "label": "BM25 + StandardAnalyzer (Baseline)",
        "index_type": "baseline",
        "similarity": "BM25Similarity(k1=1.2, b=0.75) + StandardAnalyzer",
    },
}


def build_snippet(
    raw_text: str, highlight_terms: list[str], max_chars: int = 340
) -> tuple[str, str]:
    """Buat potongan isi cerpen di sekitar kata kunci dan versi HTML ber-highlight."""
    clean_spaces = re.sub(r"\s+", " ", raw_text or "").strip()
    if not clean_spaces:
        return "", ""

    terms = [t for t in dict.fromkeys(highlight_terms) if len(t) >= 3]
    best_pos = 0
    lower_text = clean_spaces.lower()
    for term in terms:
        idx = lower_text.find(term.lower())
        if idx != -1:
            best_pos = max(0, idx - 90)
            break

    start = best_pos
    if start > 0:
        space_before = clean_spaces.rfind(" ", 0, start + 15)
        if space_before != -1:
            start = space_before + 1

    excerpt = clean_spaces[start : start + max_chars].strip()
    if start > 0:
        excerpt = "..." + excerpt
    if start + max_chars < len(clean_spaces):
        excerpt = excerpt + "..."

    escaped = html.escape(excerpt)
    if terms:
        sorted_terms = sorted(terms, key=len, reverse=True)
        pattern = re.compile(
            r"\b[a-z]*(?:" + "|".join(re.escape(t) for t in sorted_terms) + r")[a-z]*\b",
            re.IGNORECASE,
        )
        highlighted = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", escaped)
    else:
        highlighted = escaped

    return excerpt, highlighted


class SearchEngine:
    def __init__(self) -> None:
        ensure_jvm()
        self.preprocessor = CerpenPreprocessor()
        self.expander = QueryExpander(preprocessor=self.preprocessor)
        self.standard_analyzer = StandardAnalyzer()

        self._custom_dir = FSDirectory.open(Paths.get(str(CUSTOM_INDEX_PATH)))
        self._baseline_dir = FSDirectory.open(Paths.get(str(BASELINE_INDEX_PATH)))
        self._custom_reader = DirectoryReader.open(self._custom_dir)
        self._baseline_reader = DirectoryReader.open(self._baseline_dir)

    def _get_searcher(self, model: str) -> tuple[IndexSearcher, DirectoryReader, str]:
        ensure_jvm()
        if model not in SUPPORTED_MODELS:
            raise ValueError(f"Model tidak dikenal: {model}")

        if model == "bm25_baseline":
            searcher = IndexSearcher(self._baseline_reader)
            searcher.setSimilarity(BM25Similarity(1.2, 0.75))
            return searcher, self._baseline_reader, "baseline"

        searcher = IndexSearcher(self._custom_reader)
        if model == "tfidf_custom":
            searcher.setSimilarity(ClassicSimilarity())
        else:
            searcher.setSimilarity(BM25Similarity(1.2, 0.75))
        return searcher, self._custom_reader, "custom"

    def _build_weighted_custom_query(
        self, weighted_terms: dict[str, float], source_filter: str | None = None
    ) -> BooleanQuery:
        builder = BooleanQuery.Builder()
        terms_builder = BooleanQuery.Builder()

        for term, weight in weighted_terms.items():
            if not term or weight <= 0:
                continue
            title_q = BoostQuery(TermQuery(Term("title_clean", term)), float(weight * 2.0))
            content_q = BoostQuery(TermQuery(Term("content_clean", term)), float(weight))
            terms_builder.add(title_q, BooleanClause.Occur.SHOULD)
            terms_builder.add(content_q, BooleanClause.Occur.SHOULD)

        builder.add(terms_builder.build(), BooleanClause.Occur.MUST)
        if source_filter and source_filter.lower() != "all":
            builder.add(
                TermQuery(Term("source", source_filter)), BooleanClause.Occur.FILTER
            )
        return builder.build()

    def _build_baseline_query(
        self, raw_query: str, source_filter: str | None = None
    ) -> BooleanQuery | None:
        escaped = QueryParser.escape(raw_query.strip())
        if not escaped:
            return None
        title_parser = QueryParser("title_raw", self.standard_analyzer)
        content_parser = QueryParser("content_raw", self.standard_analyzer)
        q_title = BoostQuery(title_parser.parse(escaped), 2.0)
        q_content = content_parser.parse(escaped)

        terms_builder = BooleanQuery.Builder()
        terms_builder.add(q_title, BooleanClause.Occur.SHOULD)
        terms_builder.add(q_content, BooleanClause.Occur.SHOULD)

        builder = BooleanQuery.Builder()
        builder.add(terms_builder.build(), BooleanClause.Occur.MUST)
        if source_filter and source_filter.lower() != "all":
            builder.add(
                TermQuery(Term("source", source_filter)), BooleanClause.Occur.FILTER
            )
        return builder.build()

    def execute_weighted_query(
        self,
        weighted_terms: dict[str, float],
        model: str = "bm25_custom",
        top_k: int = 10,
        source_filter: str | None = None,
        highlight_terms: list[str] | None = None,
    ) -> dict[str, Any]:
        ensure_jvm()
        if model == "bm25_baseline":
            model = "bm25_custom"
        t0 = time.perf_counter()
        searcher, reader, _ = self._get_searcher(model)
        if not weighted_terms:
            return {"total_hits": 0, "latency_ms": 0.0, "results": []}

        query = self._build_weighted_custom_query(weighted_terms, source_filter)
        top_docs = searcher.search(query, int(top_k))
        stored_fields = reader.storedFields()
        hl_terms = highlight_terms or list(weighted_terms.keys())

        results = []
        for rank, score_doc in enumerate(top_docs.scoreDocs, start=1):
            doc = stored_fields.document(score_doc.doc)
            raw_content = doc.get("snippet_text") or ""
            excerpt, highlighted = build_snippet(raw_content, hl_terms)
            results.append(
                {
                    "rank": rank,
                    "lucene_doc_id": int(score_doc.doc),
                    "doc_id": doc.get("doc_id"),
                    "title": doc.get("title"),
                    "author": doc.get("author"),
                    "source": doc.get("source"),
                    "date": doc.get("date"),
                    "url": doc.get("url"),
                    "score": round(float(score_doc.score), 4),
                    "snippet": excerpt,
                    "snippet_html": highlighted,
                    "word_count": len(raw_content.split()),
                }
            )

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "total_hits": int(top_docs.totalHits.value),
            "latency_ms": latency_ms,
            "results": results,
        }

    def search(
        self,
        query_text: str,
        model: str = "bm25_custom",
        top_k: int = 10,
        use_expansion: bool = False,
        source_filter: str | None = None,
    ) -> dict[str, Any]:
        ensure_jvm()
        t0 = time.perf_counter()
        raw_query = (query_text or "").strip()
        if not raw_query:
            return {
                "query": "",
                "model": model,
                "model_label": SUPPORTED_MODELS.get(model, {}).get("label", model),
                "processed_tokens": [],
                "expanded_tokens": [],
                "added_synonyms": {},
                "total_hits": 0,
                "latency_ms": 0.0,
                "results": [],
            }

        searcher, reader, index_type = self._get_searcher(model)
        stored_fields = reader.storedFields()

        processed_tokens = self.preprocessor.preprocess_tokens(raw_query)
        added_synonyms: dict[str, list[str]] = {}
        expanded_tokens = list(processed_tokens)

        if index_type == "baseline":
            lucene_query = self._build_baseline_query(raw_query, source_filter)
            hl_terms = [
                w for w in re.findall(r"[a-zA-Z]{3,}", raw_query.lower())
                if w not in self.preprocessor.stopwords
            ]
        else:
            if use_expansion:
                exp = self.expander.expand(raw_query)
                weighted_terms = exp["weighted_terms"]
                added_synonyms = exp["added_synonyms"]
                expanded_tokens = exp["expanded_tokens"]
            else:
                weighted_terms = {tok: 1.0 for tok in processed_tokens}

            if not weighted_terms:
                return {
                    "query": raw_query,
                    "model": model,
                    "model_label": SUPPORTED_MODELS[model]["label"],
                    "processed_tokens": [],
                    "expanded_tokens": [],
                    "added_synonyms": {},
                    "total_hits": 0,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                    "results": [],
                }
            lucene_query = self._build_weighted_custom_query(weighted_terms, source_filter)
            raw_content_words = [
                w for w in re.findall(r"[a-zA-Z]{3,}", raw_query.lower())
                if w not in self.preprocessor.stopwords
            ]
            hl_terms = list(dict.fromkeys(raw_content_words + expanded_tokens))

        if lucene_query is None:
            return {
                "query": raw_query,
                "model": model,
                "model_label": SUPPORTED_MODELS[model]["label"],
                "processed_tokens": processed_tokens,
                "expanded_tokens": expanded_tokens,
                "added_synonyms": added_synonyms,
                "total_hits": 0,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "results": [],
            }

        top_docs = searcher.search(lucene_query, int(top_k))
        results = []
        for rank, score_doc in enumerate(top_docs.scoreDocs, start=1):
            doc = stored_fields.document(score_doc.doc)
            raw_content = doc.get("snippet_text") or ""
            excerpt, highlighted = build_snippet(raw_content, hl_terms)
            results.append(
                {
                    "rank": rank,
                    "lucene_doc_id": int(score_doc.doc),
                    "doc_id": doc.get("doc_id"),
                    "title": doc.get("title"),
                    "author": doc.get("author"),
                    "source": doc.get("source"),
                    "date": doc.get("date"),
                    "url": doc.get("url"),
                    "score": round(float(score_doc.score), 4),
                    "snippet": excerpt,
                    "snippet_html": highlighted,
                    "word_count": len(raw_content.split()),
                }
            )

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "query": raw_query,
            "model": model,
            "model_label": SUPPORTED_MODELS[model]["label"],
            "processed_tokens": processed_tokens,
            "expanded_tokens": expanded_tokens,
            "added_synonyms": added_synonyms,
            "total_hits": int(top_docs.totalHits.value),
            "latency_ms": latency_ms,
            "results": results,
        }

    def get_document_by_id(self, doc_id: str) -> dict[str, Any] | None:
        ensure_jvm()
        searcher, reader, _ = self._get_searcher("bm25_custom")
        top_docs = searcher.search(TermQuery(Term("doc_id", doc_id)), 1)
        if top_docs.totalHits.value == 0:
            return None
        doc = reader.storedFields().document(top_docs.scoreDocs[0].doc)
        return {
            "doc_id": doc.get("doc_id"),
            "title": doc.get("title"),
            "author": doc.get("author"),
            "source": doc.get("source"),
            "date": doc.get("date"),
            "url": doc.get("url"),
            "content_raw": doc.get("snippet_text"),
            "title_clean": doc.get("title_clean"),
            "content_clean": doc.get("content_clean"),
        }

    def get_posting_list(
        self, term: str, index_type: str = "custom", limit: int = 25
    ) -> dict[str, Any]:
        ensure_jvm()
        clean_input = term.strip()
        if index_type == "baseline":
            field = "content_raw"
            lookup_term = clean_input.lower()
            reader = self._baseline_reader
        else:
            field = "content_clean"
            tokens = self.preprocessor.preprocess_tokens(clean_input)
            lookup_term = tokens[0] if tokens else clean_input.lower()
            reader = self._custom_reader

        data = extract_posting_list(reader, field, lookup_term, limit=limit)
        data["input_term"] = term
        data["resolved_term"] = lookup_term
        data["index_type"] = index_type
        return data

    def get_health_stats(self) -> dict[str, Any]:
        ensure_jvm()
        return {
            "status": "ok",
            "custom_doc_count": int(self._custom_reader.numDocs()),
            "baseline_doc_count": int(self._baseline_reader.numDocs()),
            "models": SUPPORTED_MODELS,
        }
