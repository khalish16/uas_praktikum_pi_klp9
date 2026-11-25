"""
Evaluasi Sistem IR (TREC Pooling + Metrik P@10, Recall, F1, MAP) & Generator Grafik.

Dua mode:
1. python src/evaluate.py --build-pool
   Mengumpulkan top-10 hasil dari bm25_custom, tfidf_custom, dan bm25_baseline
   untuk seluruh query uji menjadi pool unik teracak (tanpa skor/asal model)
   agar relevance judgment manual dilakukan murni berdasarkan isi dokumen.
2. python src/evaluate.py --evaluate
   Menghitung Precision@10, Recall, F1, dan MAP dari evaluation/qrels.csv yang SAMA
   untuk seluruh konfigurasi model (bm25_custom, tfidf_custom, bm25_baseline,
   dan bm25_custom_qe), lalu menyimpan tabel perbandingan dan grafik resolusi tinggi.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.retriever import SearchEngine

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EVAL_DIR = BASE_DIR / "evaluation"
CHARTS_DIR = BASE_DIR / "reports" / "charts"

EVAL_CONFIGS = [
    ("bm25_custom", "BM25 + Custom Analyzer", False),
    ("tfidf_custom", "TF-IDF Klasik + Custom Analyzer", False),
    ("bm25_baseline", "BM25 + StandardAnalyzer (Baseline)", False),
    ("bm25_custom_qe", "BM25 + Custom + Query Expansion", True),
]


def build_pool(top_k: int = 10) -> dict[str, Any]:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with (EVAL_DIR / "queries.json").open("r", encoding="utf-8") as f:
        queries = json.load(f)
    with (DATA_DIR / "raw_corpus.json").open("r", encoding="utf-8") as f:
        raw_docs = {d["doc_id"]: d for d in json.load(f)}

    engine = SearchEngine()
    rng = random.Random(42)
    pooled_queries = []

    for q in queries:
        qid = q["query_id"]
        qtext = q["query"]
        doc_ids_set: set[str] = set()
        for model_key, _, use_qe in EVAL_CONFIGS[:3]:
            res = engine.search(qtext, model=model_key, top_k=top_k, use_expansion=use_qe)
            for item in res["results"]:
                doc_ids_set.add(item["doc_id"])

        doc_ids = sorted(doc_ids_set)
        rng.shuffle(doc_ids)

        candidates = []
        for did in doc_ids:
            doc = raw_docs.get(did, {})
            candidates.append(
                {
                    "doc_id": did,
                    "title": doc.get("title", ""),
                    "source": doc.get("source", ""),
                    "excerpt": doc.get("content_raw", "")[:900],
                }
            )

        pooled_queries.append(
            {
                "query_id": qid,
                "query": qtext,
                "description": q.get("description", ""),
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        )

    pool_path = EVAL_DIR / "pool.json"
    with pool_path.open("w", encoding="utf-8") as f:
        json.dump(pooled_queries, f, ensure_ascii=False, indent=2)

    total_pairs = sum(p["candidate_count"] for p in pooled_queries)
    return {"queries": len(pooled_queries), "total_pooled_pairs": total_pairs, "path": str(pool_path)}


def average_precision_at_k(ranked_doc_ids: list[str], relevant_set: set[str], k: int = 10) -> float:
    if not relevant_set:
        return 0.0
    hits = 0
    sum_prec = 0.0
    for idx, did in enumerate(ranked_doc_ids[:k], start=1):
        if did in relevant_set:
            hits += 1
            sum_prec += hits / idx
    return sum_prec / len(relevant_set)


def generate_charts(summary_rows: list[dict[str, Any]], per_query_rows: list[dict[str, Any]]) -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
    plt.rcParams["axes.edgecolor"] = "#D4D4D8"
    plt.rcParams["axes.linewidth"] = 0.8

    # 1. Grafik Perbandingan Evaluasi (P@10, Recall, F1, MAP)
    metrics = ["precision_at_10", "recall", "f1", "map"]
    metric_labels = ["Precision@10", "Recall", "F1-Score", "MAP"]
    colors = ["#B45309", "#18181B", "#A1A1AA", "#047857"]

    x = np.arange(len(metric_labels))
    width = 0.19
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=220)
    fig.patch.set_facecolor("#FAFAF8")
    ax.set_facecolor("#FFFFFF")

    for i, row in enumerate(summary_rows):
        vals = [row[m] for m in metrics]
        offset = (i - (len(summary_rows) - 1) / 2) * width
        bars = ax.bar(x + offset, vals, width, label=row["label"], color=colors[i % len(colors)], edgecolor="none", zorder=3)
        for bar in bars:
            h = bar.get_height()
            ax.annotate(
                f"{h:.2f}",
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7.5,
                color="#27272A",
            )

    ax.set_ylabel("Skor Metrik (0 - 1)", fontsize=10, color="#27272A")
    ax.set_title("Perbandingan Kualitas Retrieval pada 12 Query Uji (Cerpen)", fontsize=12, fontweight="bold", color="#18181B", pad=14)
    ax.set_xticks(x)
    ax.set_xticklabels(metric_labels, fontsize=10, color="#18181B")
    ax.set_ylim(0, 1.08)
    ax.grid(axis="y", linestyle="--", alpha=0.45, color="#D4D4D8", zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=True, facecolor="#FAFAF8", edgecolor="#E4E4E7", fontsize=8.5, loc="upper right")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "evaluation_comparison.png", dpi=220)
    plt.close(fig)

    # 2. Grafik Average Precision per Query (BM25 Custom vs TF-IDF Custom vs Baseline)
    qids = sorted({r["query_id"] for r in per_query_rows})
    model_map = {
        "bm25_custom": ("BM25 + Custom", "#B45309"),
        "tfidf_custom": ("TF-IDF + Custom", "#18181B"),
        "bm25_baseline": ("BM25 + Baseline", "#A1A1AA"),
    }
    ap_lookup = {(r["query_id"], r["config"]): r["ap"] for r in per_query_rows}

    fig, ax = plt.subplots(figsize=(11, 4.8), dpi=220)
    fig.patch.set_facecolor("#FAFAF8")
    ax.set_facecolor("#FFFFFF")
    xq = np.arange(len(qids))
    w2 = 0.26
    for idx, (mkey, (mlabel, mcolor)) in enumerate(model_map.items()):
        vals = [ap_lookup.get((qid, mkey), 0.0) for qid in qids]
        ax.bar(xq + (idx - 1) * w2, vals, w2, label=mlabel, color=mcolor, zorder=3)

    ax.set_ylabel("Average Precision (AP@10)", fontsize=10, color="#27272A")
    ax.set_title("Average Precision per Query Uji (Q01 - Q12)", fontsize=12, fontweight="bold", color="#18181B", pad=12)
    ax.set_xticks(xq)
    ax.set_xticklabels(qids, fontsize=9.5, color="#18181B")
    ax.set_ylim(0, 1.08)
    ax.grid(axis="y", linestyle="--", alpha=0.45, color="#D4D4D8", zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=True, facecolor="#FAFAF8", edgecolor="#E4E4E7", fontsize=8.5)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "per_query_ap.png", dpi=220)
    plt.close(fig)

    # 3. Grafik Distribusi Sumber & Panjang Dokumen Korpus
    with (DATA_DIR / "raw_corpus.json").open("r", encoding="utf-8") as f:
        raw_docs = json.load(f)

    src_counts = Counter(d["source"] for d in raw_docs)
    word_counts = [d.get("word_count", 0) for d in raw_docs]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.2), dpi=220)
    fig.patch.set_facecolor("#FAFAF8")
    for a in (ax1, ax2):
        a.set_facecolor("#FFFFFF")
        a.spines["top"].set_visible(False)
        a.spines["right"].set_visible(False)

    sources = list(src_counts.keys())
    counts = [src_counts[s] for s in sources]
    bar_colors = ["#B45309", "#27272A", "#71717A"][: len(sources)]
    bars = ax1.bar(sources, counts, color=bar_colors, width=0.52, zorder=3)
    for bar in bars:
        h = bar.get_height()
        ax1.annotate(f"{int(h)}", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9, fontweight="bold")
    ax1.set_title("Distribusi Sumber Korpus Cerpen", fontsize=11, fontweight="bold", color="#18181B")
    ax1.set_ylabel("Jumlah Dokumen Unik", fontsize=9.5)
    ax1.set_ylim(0, max(counts) * 1.18)
    ax1.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)

    ax2.hist(word_counts, bins=22, color="#B45309", alpha=0.85, edgecolor="#FAFAF8", zorder=3)
    mean_wc = float(np.mean(word_counts))
    ax2.axvline(mean_wc, color="#18181B", linestyle="--", linewidth=1.4, label=f"Rata-rata: {mean_wc:.0f} kata")
    ax2.set_title("Sebaran Panjang Cerpen (Jumlah Kata)", fontsize=11, fontweight="bold", color="#18181B")
    ax2.set_xlabel("Jumlah Kata per Cerpen", fontsize=9.5)
    ax2.set_ylabel("Frekuensi Dokumen", fontsize=9.5)
    ax2.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax2.legend(frameon=True, facecolor="#FAFAF8", edgecolor="#E4E4E7", fontsize=8.5)

    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "corpus_stats.png", dpi=220)
    plt.close(fig)


def evaluate_all(top_k: int = 10) -> dict[str, Any]:
    with (EVAL_DIR / "queries.json").open("r", encoding="utf-8") as f:
        queries = json.load(f)

    qrels: dict[str, set[str]] = {}
    with (EVAL_DIR / "qrels.csv").open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row["query_id"].strip()
            did = row["doc_id"].strip()
            rel = int(row["relevant"])
            if rel == 1:
                qrels.setdefault(qid, set()).add(did)

    engine = SearchEngine()
    summary_rows: list[dict[str, Any]] = []
    per_query_rows: list[dict[str, Any]] = []

    for config_key, label, use_qe in EVAL_CONFIGS:
        lucene_model = "bm25_custom" if config_key == "bm25_custom_qe" else config_key
        precs, recalls, f1s, aps = [], [], [], []

        for q in queries:
            qid = q["query_id"]
            qtext = q["query"]
            rel_set = qrels.get(qid, set())
            res = engine.search(qtext, model=lucene_model, top_k=top_k, use_expansion=use_qe)
            retrieved_ids = [r["doc_id"] for r in res["results"]]

            tp = sum(1 for did in retrieved_ids[:top_k] if did in rel_set)
            p_at_10 = tp / top_k
            recall = (tp / len(rel_set)) if rel_set else 0.0
            f1 = (2 * p_at_10 * recall / (p_at_10 + recall)) if (p_at_10 + recall) > 0 else 0.0
            ap = average_precision_at_k(retrieved_ids, rel_set, k=top_k)

            precs.append(p_at_10)
            recalls.append(recall)
            f1s.append(f1)
            aps.append(ap)

            per_query_rows.append(
                {
                    "config": config_key,
                    "label": label,
                    "query_id": qid,
                    "query": qtext,
                    "relevant_in_pool": len(rel_set),
                    "relevant_retrieved_top10": tp,
                    "precision_at_10": round(p_at_10, 4),
                    "recall": round(recall, 4),
                    "f1": round(f1, 4),
                    "ap": round(ap, 4),
                }
            )

        summary_rows.append(
            {
                "config": config_key,
                "label": label,
                "num_queries": len(queries),
                "precision_at_10": round(float(np.mean(precs)), 4),
                "recall": round(float(np.mean(recalls)), 4),
                "f1": round(float(np.mean(f1s)), 4),
                "map": round(float(np.mean(aps)), 4),
            }
        )

    # Simpan ringkasan JSON & CSV
    summary_payload = {
        "num_queries": len(queries),
        "top_k": top_k,
        "total_relevant_judgments": sum(len(v) for v in qrels.values()),
        "summary": summary_rows,
        "per_query": per_query_rows,
    }
    with (EVAL_DIR / "results_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary_payload, f, ensure_ascii=False, indent=2)

    with (EVAL_DIR / "results_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["config", "label", "num_queries", "precision_at_10", "recall", "f1", "map"],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    with (EVAL_DIR / "per_query_metrics.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "config",
                "label",
                "query_id",
                "query",
                "relevant_in_pool",
                "relevant_retrieved_top10",
                "precision_at_10",
                "recall",
                "f1",
                "ap",
            ],
        )
        writer.writeheader()
        writer.writerows(per_query_rows)

    generate_charts(summary_rows, per_query_rows)
    return summary_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluasi Sistem IR Cerpen (PyLucene)")
    parser.add_argument("--build-pool", action="store_true", help="Bangun pool dokumen untuk manual relevance judgment")
    parser.add_argument("--evaluate", action="store_true", help="Hitung metrik P@10, Recall, F1, MAP dari qrels.csv")
    args = parser.parse_args()

    if args.build_pool:
        info = build_pool()
        print(f"[POOL] Berhasil membuat pool evaluasi: {info['queries']} query, {info['total_pooled_pairs']} pasangan dokumen.")
    elif args.evaluate:
        res = evaluate_all()
        print("[EVALUATE] Tabel Perbandingan Evaluasi (12 Query Uji, K=10):")
        for row in res["summary"]:
            print(
                f"  {row['label']:<38} | P@10={row['precision_at_10']:.4f} | Recall={row['recall']:.4f} | F1={row['f1']:.4f} | MAP={row['map']:.4f}"
            )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
