"""
Pemeriksaan Duplikat Korpus Cerpen (3 Lapis):
1. Normalisasi URL (Exact URL duplicate)
2. SHA-256 Hash teks ternormalisasi (Exact text duplicate)
3. Cosine Similarity TF-IDF >= 0.95 (Near-duplicate > 95%)

Menghasilkan korpus mentah unik (>= 500 dokumen) dan laporan bukti
duplicate checking di reports/duplicate_report.json serta .csv.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"

SIMILARITY_THRESHOLD = 0.95


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip().lower())
    path = parsed.path.rstrip("/")
    return f"{parsed.netloc}{path}"


def normalize_for_hash(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def compute_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_hash(text).encode("utf-8")).hexdigest()


def run_deduplication(
    raw_json_path: Path | None = None,
    threshold: float = SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    raw_path = raw_json_path or (DATA_DIR / "raw_corpus.json")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with raw_path.open("r", encoding="utf-8") as f:
        docs: list[dict[str, Any]] = json.load(f)

    total_crawled = len(docs)
    removed_pairs: list[dict[str, Any]] = []

    # Tahap 1 & 2: Exact URL & Exact SHA-256 Hash
    seen_urls: dict[str, str] = {}
    seen_hashes: dict[str, str] = {}
    stage12_docs: list[dict[str, Any]] = []
    exact_url_dups = 0
    exact_hash_dups = 0

    for doc in docs:
        norm_url = normalize_url(doc.get("url", ""))
        text_hash = compute_hash(f"{doc.get('title', '')} {doc.get('content_raw', '')}")

        if norm_url in seen_urls:
            exact_url_dups += 1
            removed_pairs.append(
                {
                    "kept_doc_id": seen_urls[norm_url],
                    "removed_doc_id": doc["doc_id"],
                    "removed_title": doc["title"],
                    "removed_url": doc["url"],
                    "reason": "exact_url_duplicate",
                    "similarity": 1.0,
                }
            )
            continue

        if text_hash in seen_hashes:
            exact_hash_dups += 1
            removed_pairs.append(
                {
                    "kept_doc_id": seen_hashes[text_hash],
                    "removed_doc_id": doc["doc_id"],
                    "removed_title": doc["title"],
                    "removed_url": doc["url"],
                    "reason": "exact_sha256_hash_duplicate",
                    "similarity": 1.0,
                }
            )
            continue

        seen_urls[norm_url] = doc["doc_id"]
        seen_hashes[text_hash] = doc["doc_id"]
        stage12_docs.append(doc)

    # Tahap 3: Near-duplicate detection (> 95% TF-IDF cosine similarity)
    texts = [
        normalize_for_hash(f"{d.get('title', '')} {d.get('content_raw', '')}")
        for d in stage12_docs
    ]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=30000)
    tfidf_matrix = vectorizer.fit_transform(texts)
    sim_matrix = cosine_similarity(tfidf_matrix)

    n = len(stage12_docs)
    removed_indices: set[int] = set()
    near_dups = 0

    # Catat semua pasangan dengan similarity tertinggi untuk bukti audit
    for i in range(n):
        if i in removed_indices:
            continue
        row = sim_matrix[i]
        for j in range(i + 1, n):
            if j in removed_indices:
                continue
            sim = float(row[j])
            if sim >= threshold:
                near_dups += 1
                removed_indices.add(j)
                removed_pairs.append(
                    {
                        "kept_doc_id": stage12_docs[i]["doc_id"],
                        "kept_title": stage12_docs[i]["title"],
                        "removed_doc_id": stage12_docs[j]["doc_id"],
                        "removed_title": stage12_docs[j]["title"],
                        "removed_url": stage12_docs[j]["url"],
                        "reason": f"near_duplicate_cosine_ge_{threshold}",
                        "similarity": round(sim, 6),
                    }
                )

    unique_docs = [
        doc for idx, doc in enumerate(stage12_docs) if idx not in removed_indices
    ]

    # Hitung top-10 pasangan paling mirip di antara dokumen unik yang dipertahankan
    kept_indices = [idx for idx in range(n) if idx not in removed_indices]
    kept_submatrix = sim_matrix[np.ix_(kept_indices, kept_indices)]
    np.fill_diagonal(kept_submatrix, 0.0)
    upper_rows, upper_cols = np.triu_indices(len(kept_indices), k=1)
    upper_sims = kept_submatrix[upper_rows, upper_cols]
    top_k_idx = np.argsort(upper_sims)[::-1][:10]

    top_remaining_pairs = []
    for k in top_k_idx:
        r_idx = kept_indices[int(upper_rows[k])]
        c_idx = kept_indices[int(upper_cols[k])]
        top_remaining_pairs.append(
            {
                "doc_1_id": stage12_docs[r_idx]["doc_id"],
                "doc_1_title": stage12_docs[r_idx]["title"],
                "doc_2_id": stage12_docs[c_idx]["doc_id"],
                "doc_2_title": stage12_docs[c_idx]["title"],
                "cosine_similarity": round(float(upper_sims[k]), 6),
                "status": "kept (< 95%)",
            }
        )

    max_remaining_sim = (
        top_remaining_pairs[0]["cosine_similarity"] if top_remaining_pairs else 0.0
    )

    # Re-number doc_id secara rapi pada korpus mentah unik
    for new_idx, doc in enumerate(unique_docs, start=1):
        doc["doc_id"] = f"CERPEN-{new_idx:04d}"

    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(unique_docs, f, ensure_ascii=False, indent=2)

    raw_csv_path = DATA_DIR / "raw_corpus.csv"
    fieldnames = [
        "doc_id",
        "title",
        "author",
        "source",
        "date",
        "url",
        "word_count",
        "content_raw",
    ]
    with raw_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in unique_docs:
            writer.writerow({k: d.get(k, "") for k in fieldnames})

    report = {
        "total_crawled": total_crawled,
        "exact_url_duplicates": exact_url_dups,
        "exact_hash_duplicates": exact_hash_dups,
        "near_duplicates_gt_95": near_dups,
        "total_removed": len(removed_pairs),
        "total_unique_documents": len(unique_docs),
        "threshold": threshold,
        "max_similarity_among_unique": max_remaining_sim,
        "removed_pairs": removed_pairs,
        "top_10_most_similar_remaining_pairs": top_remaining_pairs,
    }

    report_json = REPORTS_DIR / "duplicate_report.json"
    with report_json.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    report_csv = REPORTS_DIR / "duplicate_report.csv"
    with report_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "pair_type",
                "doc_1_id",
                "doc_1_title",
                "doc_2_id",
                "doc_2_title",
                "cosine_similarity",
                "status",
            ],
        )
        writer.writeheader()
        for pair in removed_pairs:
            writer.writerow(
                {
                    "pair_type": "duplicate_removed",
                    "doc_1_id": pair.get("kept_doc_id", ""),
                    "doc_1_title": pair.get("kept_title", ""),
                    "doc_2_id": pair.get("removed_doc_id", ""),
                    "doc_2_title": pair.get("removed_title", ""),
                    "cosine_similarity": pair.get("similarity", 1.0),
                    "status": pair.get("reason", "removed"),
                }
            )
        for pair in top_remaining_pairs:
            writer.writerow(
                {
                    "pair_type": "top_unique_audit",
                    "doc_1_id": pair["doc_1_id"],
                    "doc_1_title": pair["doc_1_title"],
                    "doc_2_id": pair["doc_2_id"],
                    "doc_2_title": pair["doc_2_title"],
                    "cosine_similarity": pair["cosine_similarity"],
                    "status": pair["status"],
                }
            )

    return report


def main() -> None:
    report = run_deduplication()
    print("[DEDUPLICATE] Ringkasan Pemeriksaan Duplikat (>95%):")
    print(f"  Total di-crawl        : {report['total_crawled']}")
    print(f"  Duplikat URL eksak    : {report['exact_url_duplicates']}")
    print(f"  Duplikat Hash SHA-256 : {report['exact_hash_duplicates']}")
    print(f"  Near-duplicate >= 95% : {report['near_duplicates_gt_95']}")
    print(f"  Total dihapus         : {report['total_removed']}")
    print(f"  Total dokumen unik    : {report['total_unique_documents']}")
    print(f"  Skor kemiripan maks.  : {report['max_similarity_among_unique']}")


if __name__ == "__main__":
    main()
