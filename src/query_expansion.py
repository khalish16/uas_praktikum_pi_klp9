"""
Query Expansion menggunakan Kamus Sinonim Mandiri Domain Cerpen / Cerita Fiksi.
Semua term kamus diproses ulang dengan CerpenPreprocessor agar cocok 100%
dengan token term hasil stemming di indeks PyLucene.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.preprocessing import CerpenPreprocessor

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"


class QueryExpander:
    def __init__(
        self,
        synonyms_path: Path | None = None,
        preprocessor: CerpenPreprocessor | None = None,
    ) -> None:
        self.synonyms_path = synonyms_path or (DATA_DIR / "synonyms.json")
        self.preprocessor = preprocessor or CerpenPreprocessor()
        self.raw_pairs: list[dict[str, Any]] = []
        self.synonym_map: dict[str, list[str]] = {}
        self._load_dictionary()

    def _load_dictionary(self) -> None:
        with self.synonyms_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        self.raw_pairs = payload.get("pairs", [])

        # Bangun mapping dua arah berbasis kata dasar (stemmed) agar konsisten dengan indeks
        mapping: dict[str, set[str]] = {}
        for entry in self.raw_pairs:
            root_tokens = self.preprocessor.preprocess_tokens(entry["term"])
            if not root_tokens:
                continue
            root = root_tokens[0]
            syns: list[str] = []
            for s in entry.get("synonyms", []):
                stoks = self.preprocessor.preprocess_tokens(s)
                if stoks and stoks[0] != root:
                    syns.append(stoks[0])
            if not syns:
                continue
            mapping.setdefault(root, set()).update(syns)
            for syn in syns:
                mapping.setdefault(syn, set()).add(root)

        self.synonym_map = {k: sorted(v) for k, v in mapping.items()}

    def expand(
        self,
        query_text: str,
        max_synonyms_per_term: int = 3,
        synonym_weight: float = 0.45,
    ) -> dict[str, Any]:
        """Ekspansi query dengan mengembalikan bobot term asli (1.0) dan sinonim (0.45)."""
        original_tokens = self.preprocessor.preprocess_tokens(query_text)
        term_weights: dict[str, float] = {}
        added_synonyms: dict[str, list[str]] = {}

        for tok in original_tokens:
            term_weights[tok] = max(term_weights.get(tok, 0.0), 1.0)
            syns = [s for s in self.synonym_map.get(tok, []) if s not in original_tokens]
            chosen = syns[:max_synonyms_per_term]
            if chosen:
                added_synonyms[tok] = chosen
                for s in chosen:
                    term_weights[s] = max(term_weights.get(s, 0.0), synonym_weight)

        expanded_tokens = list(term_weights.keys())
        return {
            "raw_query": query_text,
            "original_tokens": original_tokens,
            "added_synonyms": added_synonyms,
            "expanded_tokens": expanded_tokens,
            "weighted_terms": term_weights,
            "expanded_query_str": " ".join(expanded_tokens),
        }


def generate_proof_report() -> dict[str, Any]:
    from src.retriever import SearchEngine

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    engine = SearchEngine()
    proof_queries = [
        "hujan malam sunyi",
        "rindu ibu di kampung",
        "cinta sedih di pantai",
        "kubur ayah yang pergi",
        "mimpi di warung kopi",
        "kereta senja pulang desa",
    ]

    proofs = []
    for q in proof_queries:
        res_before = engine.search(q, model="bm25_custom", top_k=5, use_expansion=False)
        res_after = engine.search(q, model="bm25_custom", top_k=5, use_expansion=True)
        proofs.append(
            {
                "raw_query": q,
                "tokens_before": res_before["processed_tokens"],
                "tokens_after": res_after["expanded_tokens"],
                "added_synonyms": res_after["added_synonyms"],
                "total_hits_before": res_before["total_hits"],
                "total_hits_after": res_after["total_hits"],
                "top5_before": [
                    {"doc_id": r["doc_id"], "title": r["title"], "score": r["score"]}
                    for r in res_before["results"]
                ],
                "top5_after": [
                    {"doc_id": r["doc_id"], "title": r["title"], "score": r["score"]}
                    for r in res_after["results"]
                ],
            }
        )

    output = {
        "dictionary_pair_count": len(engine.expander.raw_pairs),
        "indexed_synonym_keys": len(engine.expander.synonym_map),
        "proof_queries": proofs,
    }
    out_path = REPORTS_DIR / "query_expansion_proof.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return output


if __name__ == "__main__":
    report = generate_proof_report()
    print(f"[QUERY EXPANSION] Kamus: {report['dictionary_pair_count']} pasangan.")
    for item in report["proof_queries"]:
        print(
            f"  '{item['raw_query']}' -> hits {item['total_hits_before']} -> {item['total_hits_after']} | sinonim: {item['added_synonyms']}"
        )
