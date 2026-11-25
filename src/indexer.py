"""
Indexing Korpus Cerpen menggunakan Apache Lucene (PyLucene 9.12).

Membangun DUA indeks terpisah pada korpus yang sama:
1. indexes/custom_index   -> Menggunakan WhitespaceAnalyzer di atas token hasil
                             Custom Preprocessing (CerpenPreprocessor) + term vectors.
2. indexes/baseline_index -> Menggunakan StandardAnalyzer bawaan Lucene di atas
                             teks mentah (untuk perbandingan baseline yang adil).

Juga mengekstrak Posting List nyata langsung dari indeks Lucene menggunakan
MultiTerms & PostingsEnum untuk pembuktian dan tampilan UI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import lucene
from java.nio.file import Paths
from org.apache.lucene.analysis.core import WhitespaceAnalyzer
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.document import Document, Field, FieldType, StoredField, StringField
from org.apache.lucene.index import (
    DirectoryReader,
    IndexOptions,
    IndexWriter,
    IndexWriterConfig,
    MultiTerms,
    PostingsEnum,
)
from org.apache.lucene.search import DocIdSetIterator
from org.apache.lucene.store import FSDirectory
from org.apache.lucene.util import BytesRef, BytesRefIterator

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = BASE_DIR / "indexes"
REPORTS_DIR = BASE_DIR / "reports"

CUSTOM_INDEX_PATH = INDEX_DIR / "custom_index"
BASELINE_INDEX_PATH = INDEX_DIR / "baseline_index"

SAMPLE_POSTING_TERMS = [
    "hujan",
    "rindu",
    "cinta",
    "kopi",
    "ibu",
    "malam",
    "desa",
    "mati",
    "laut",
    "rumah",
]


def ensure_jvm() -> None:
    env = lucene.getVMEnv()
    if env is None:
        lucene.initVM(vmargs=["-Djava.awt.headless=true"])
    else:
        env.attachCurrentThread()


def make_text_vector_field_type() -> FieldType:
    ft = FieldType()
    ft.setStored(True)
    ft.setTokenized(True)
    ft.setIndexOptions(IndexOptions.DOCS_AND_FREQS_AND_POSITIONS)
    ft.setStoreTermVectors(True)
    ft.setStoreTermVectorPositions(True)
    ft.freeze()
    return ft


def build_custom_index(raw_map: dict[str, dict[str, Any]], clean_docs: list[dict[str, Any]]) -> int:
    CUSTOM_INDEX_PATH.mkdir(parents=True, exist_ok=True)
    directory = FSDirectory.open(Paths.get(str(CUSTOM_INDEX_PATH)))
    analyzer = WhitespaceAnalyzer()
    config = IndexWriterConfig(analyzer)
    config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)

    writer = IndexWriter(directory, config)
    ft_vector = make_text_vector_field_type()

    for doc_data in clean_docs:
        doc_id = doc_data["doc_id"]
        raw_doc = raw_map.get(doc_id, {})
        doc = Document()
        doc.add(StringField("doc_id", doc_id, Field.Store.YES))
        doc.add(StoredField("title", doc_data.get("title", "")))
        doc.add(StoredField("author", doc_data.get("author", "Redaksi")))
        doc.add(StringField("source", doc_data.get("source", ""), Field.Store.YES))
        doc.add(StoredField("date", doc_data.get("date", "")))
        doc.add(StoredField("url", doc_data.get("url", "")))
        doc.add(StoredField("snippet_text", raw_doc.get("content_raw", "")))
        doc.add(Field("title_clean", doc_data.get("title_clean", ""), ft_vector))
        doc.add(Field("content_clean", doc_data.get("content_clean", ""), ft_vector))
        writer.addDocument(doc)

    writer.commit()
    num_docs = writer.getDocStats().numDocs
    writer.close()
    directory.close()
    return int(num_docs)


def build_baseline_index(raw_docs: list[dict[str, Any]]) -> int:
    BASELINE_INDEX_PATH.mkdir(parents=True, exist_ok=True)
    directory = FSDirectory.open(Paths.get(str(BASELINE_INDEX_PATH)))
    analyzer = StandardAnalyzer()
    config = IndexWriterConfig(analyzer)
    config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)

    writer = IndexWriter(directory, config)
    ft_vector = make_text_vector_field_type()

    for doc_data in raw_docs:
        doc = Document()
        doc.add(StringField("doc_id", doc_data["doc_id"], Field.Store.YES))
        doc.add(StoredField("title", doc_data.get("title", "")))
        doc.add(StoredField("author", doc_data.get("author", "Redaksi")))
        doc.add(StringField("source", doc_data.get("source", ""), Field.Store.YES))
        doc.add(StoredField("date", doc_data.get("date", "")))
        doc.add(StoredField("url", doc_data.get("url", "")))
        doc.add(StoredField("snippet_text", doc_data.get("content_raw", "")))
        doc.add(Field("title_raw", doc_data.get("title", ""), ft_vector))
        doc.add(Field("content_raw", doc_data.get("content_raw", ""), ft_vector))
        writer.addDocument(doc)

    writer.commit()
    num_docs = writer.getDocStats().numDocs
    writer.close()
    directory.close()
    return int(num_docs)


def extract_posting_list(
    reader: DirectoryReader, field: str, term_text: str, limit: int = 15
) -> dict[str, Any]:
    """Ekstrak posting list term secara langsung dari indeks Lucene (MultiTerms + PostingsEnum)."""
    terms = MultiTerms.getTerms(reader, field)
    if terms is None:
        return {"term": term_text, "field": field, "df": 0, "total_tf": 0, "postings": []}

    terms_enum = terms.iterator()
    found = terms_enum.seekExact(BytesRef(term_text.encode("utf-8")))
    if not found:
        return {"term": term_text, "field": field, "df": 0, "total_tf": 0, "postings": []}

    df = int(terms_enum.docFreq())
    total_tf = int(terms_enum.totalTermFreq())
    postings_enum = terms_enum.postings(None, PostingsEnum.POSITIONS)
    stored_fields = reader.storedFields()

    postings = []
    if postings_enum is not None:
        while postings_enum.nextDoc() != DocIdSetIterator.NO_MORE_DOCS:
            lucene_doc_id = int(postings_enum.docID())
            freq = int(postings_enum.freq())
            positions = []
            for _ in range(min(freq, 8)):
                positions.append(int(postings_enum.nextPosition()))
            stored_doc = stored_fields.document(lucene_doc_id)
            postings.append(
                {
                    "lucene_doc_id": lucene_doc_id,
                    "doc_id": stored_doc.get("doc_id"),
                    "title": stored_doc.get("title"),
                    "source": stored_doc.get("source"),
                    "tf": freq,
                    "positions": positions,
                }
            )
            if len(postings) >= limit:
                break

    return {
        "term": term_text,
        "field": field,
        "df": df,
        "total_tf": total_tf,
        "postings": postings,
    }


def collect_index_stats() -> dict[str, Any]:
    custom_dir = FSDirectory.open(Paths.get(str(CUSTOM_INDEX_PATH)))
    baseline_dir = FSDirectory.open(Paths.get(str(BASELINE_INDEX_PATH)))
    custom_reader = DirectoryReader.open(custom_dir)
    baseline_reader = DirectoryReader.open(baseline_dir)

    custom_terms = MultiTerms.getTerms(custom_reader, "content_clean")
    baseline_terms = MultiTerms.getTerms(baseline_reader, "content_raw")

    custom_vocab_size = int(custom_terms.size()) if custom_terms is not None else -1
    baseline_vocab_size = int(baseline_terms.size()) if baseline_terms is not None else -1

    # Jika Terms.size() mengembalikan -1 (beberapa codec), hitung via iterator
    if custom_vocab_size < 0 and custom_terms is not None:
        it = BytesRefIterator.cast_(custom_terms.iterator())
        cnt = 0
        while it.next() is not None:
            cnt += 1
        custom_vocab_size = cnt

    if baseline_vocab_size < 0 and baseline_terms is not None:
        it = BytesRefIterator.cast_(baseline_terms.iterator())
        cnt = 0
        while it.next() is not None:
            cnt += 1
        baseline_vocab_size = cnt

    posting_samples = [
        extract_posting_list(custom_reader, "content_clean", term, limit=10)
        for term in SAMPLE_POSTING_TERMS
    ]
    baseline_samples = [
        extract_posting_list(baseline_reader, "content_raw", term, limit=10)
        for term in ["hujan", "rindu", "cinta"]
    ]

    stats = {
        "custom_index": {
            "num_docs": int(custom_reader.numDocs()),
            "analyzer": "WhitespaceAnalyzer (Custom CerpenPreprocessor)",
            "unique_terms_content": custom_vocab_size,
            "total_term_freq_content": int(custom_reader.getSumTotalTermFreq("content_clean")),
        },
        "baseline_index": {
            "num_docs": int(baseline_reader.numDocs()),
            "analyzer": "StandardAnalyzer (Lucene Built-in)",
            "unique_terms_content": baseline_vocab_size,
            "total_term_freq_content": int(baseline_reader.getSumTotalTermFreq("content_raw")),
        },
        "posting_list_samples_custom": posting_samples,
        "posting_list_samples_baseline": baseline_samples,
    }

    custom_reader.close()
    baseline_reader.close()
    custom_dir.close()
    baseline_dir.close()
    return stats


def main() -> None:
    ensure_jvm()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with (DATA_DIR / "raw_corpus.json").open("r", encoding="utf-8") as f:
        raw_docs = json.load(f)
    with (DATA_DIR / "clean_corpus.json").open("r", encoding="utf-8") as f:
        clean_docs = json.load(f)

    raw_map = {d["doc_id"]: d for d in raw_docs}

    n_custom = build_custom_index(raw_map, clean_docs)
    n_baseline = build_baseline_index(raw_docs)
    stats = collect_index_stats()

    stats_path = REPORTS_DIR / "index_stats.json"
    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print("[INDEXER] PyLucene Indexing Selesai:")
    print(f"  Custom Index   : {n_custom} dokumen, {stats['custom_index']['unique_terms_content']:,} term unik")
    print(f"  Baseline Index : {n_baseline} dokumen, {stats['baseline_index']['unique_terms_content']:,} term unik")
    print(f"  Stats & Posting List tersimpan di: {stats_path}")


if __name__ == "__main__":
    main()
