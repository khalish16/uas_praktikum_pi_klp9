"""
Custom Preprocessing Pipeline untuk Korpus Cerpen / Cerita Fiksi Indonesia.
Digunakan IDENTIK untuk proses indexing dan query processing.

Tahapan:
1. Domain Cleaning: hapus sisa HTML, URL, email, boilerplate redaksi/ilustrasi,
   normalisasi kutipan sastra (“”‘’), tanda baca dialog (—–…), hapus emoji & angka.
2. Case Folding & Tokenisasi: huruf kecil + ekstraksi token alfabetis Indonesia
   (pemecahan kata ulang berimbuhan/tanda hubung).
3. Stopword Removal: gabungan Stopword Bahasa Indonesia (PySastrawi) +
   Custom Domain Stopwords Cerpen/Fiksi (tag dialog, pengisi narasi, kata seru,
   dan boilerplate portal sastra).
4. Stemming: Sastrawi Stemmer dengan memoization cache agar cepat pada 600+ cerpen.
"""

from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"

# Kata tematik penting dalam cerpen yang keliru terhapus oleh daftar stopword umum PySastrawi
PRESERVE_DOMAIN_WORDS: set[str] = {"ibu", "hari"}

# Custom domain stopwords khusus korpus Cerpen / Cerita Fiksi Indonesia
CUSTOM_CERPEN_STOPWORDS: set[str] = {
    # Tag dialog & pengait ujaran yang sangat sering muncul namun tidak deskriptif secara tematik
    "ujar", "ucap", "sahut", "gumam", "bisik", "seru", "tanya", "jawab",
    "kata", "berkata", "katanya", "ujarnya", "ucapnya", "sahutnya", "tanyanya", "jawabnya",
    "tutur", "keluh", "celutuk", "celetuk", "imbuh", "lanjut", "potong",
    # Kata penghubung & pengisi narasi fiksi
    "seolah", "seakan", "bagaikan", "laksana", "ibarat", "barangkali", "rupanya",
    "ternyata", "entah", "seketika", "perlahan", "pelan", "kemudian", "lalu",
    "ketika", "tatkala", "sewaktu", "suatu", "seseorang", "sesuatu", "sekadar",
    "cuma", "hanya", "memang", "padahal", "namun", "meski", "walaupun", "kendati",
    "bahkan", "apalagi", "mungkin", "barusan", "tadi", "nanti", "kelak",
    "pun", "lah", "kah", "tah", "nya", "ku", "mu",
    # Kata ganti & penunjuk umum yang lolos stopword dasar
    "aku", "saya", "engkau", "kau", "kamu", "beliau", "mereka", "kita", "kami",
    "dirinya", "diriku", "dirimu", "kalian", "ia", "dia", "itu", "ini", "situ", "sini", "sana",
    # Interjeksi / kata seru dialog fiksi
    "ah", "eh", "oh", "wah", "hmm", "hm", "hah", "huh", "heh", "aih", "astaga", "ya", "nah", "dong", "deh", "sih", "kok", "lho", "loh",
    # Boilerplate portal sastra & metadata editorial
    "ilustrasi", "redaksi", "editor", "kurator", "basabasi", "bacapetra", "litera",
    "cerpen", "cerita", "pendek", "fiksi", "halaman", "baca", "klik", "edisi",
    "terbit", "dimuat", "sumber", "gambar", "foto", "penulis", "catatan", "bersambung",
}

BOILERPLATE_LINE_PATTERNS = [
    re.compile(r"^\s*(ilustrasi|sumber gambar|foto|editor|kurator|catatan redaksi|baca juga)\s*:.*$", re.IGNORECASE),
    re.compile(r"^\s*\*{2,}.*\*{2,}\s*$"),
    re.compile(r"^\s*[-_=~]{3,}\s*$"),
]


class CerpenPreprocessor:
    """Pipeline preprocessing custom yang konsisten untuk dokumen & query."""

    def __init__(self) -> None:
        stop_factory = StopWordRemoverFactory()
        base_stopwords = set(stop_factory.get_stop_words()) - PRESERVE_DOMAIN_WORDS
        self.stopwords: set[str] = base_stopwords | CUSTOM_CERPEN_STOPWORDS
        self.stemmer = StemmerFactory().create_stemmer()
        self._stem_cache: dict[str, str] = {}

    def clean_domain_text(self, text: str) -> str:
        """Hapus HTML, URL, boilerplate portal, karakter non-alfabetis/emoji, dan normalisasi tanda baca fiksi."""
        if not text:
            return ""
        # Hapus tag HTML jika masih tersisa (mis. input mentah / snippet HTML)
        if "<" in text and ">" in text:
            soup = BeautifulSoup(text, "lxml")
            for tag in soup(["script", "style", "noscript", "figure", "figcaption"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
        text = html.unescape(text)

        # Hapus URL & email
        text = re.sub(r"https?://\S+|www\.\S+", " ", text)
        text = re.sub(r"\S+@\S+\.\S+", " ", text)

        # Hapus baris boilerplate portal cerpen
        cleaned_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if any(pat.match(stripped) for pat in BOILERPLATE_LINE_PATTERNS):
                continue
            cleaned_lines.append(stripped)
        text = " ".join(cleaned_lines)

        # Normalisasi kutipan sastra & tanda hubung dialog (em-dash, en-dash)
        text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        text = text.replace("—", " ").replace("–", " ").replace("…", " ")

        # Case folding
        text = text.lower()

        # Pertahankan huruf latin & tanda hubung kata ulang (nanti dipecah saat tokenisasi)
        text = re.sub(r"[^a-z\s-]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def tokenize(self, cleaned_text: str) -> list[str]:
        """Pecah teks bersih menjadi token alfabetis (memecah kata ulang bertanda hubung)."""
        if not cleaned_text:
            return []
        raw_tokens = re.findall(r"[a-z]{2,}", cleaned_text.replace("-", " "))
        return raw_tokens

    def remove_stopwords(self, tokens: list[str]) -> list[str]:
        """Hapus stopword umum Bahasa Indonesia + custom domain stopwords Cerpen."""
        return [tok for tok in tokens if tok not in self.stopwords and len(tok) >= 2]

    def stem_token(self, token: str) -> str:
        """Stemming Sastrawi dengan cache memoization."""
        cached = self._stem_cache.get(token)
        if cached is not None:
            return cached
        stemmed = self.stemmer.stem(token)
        self._stem_cache[token] = stemmed
        return stemmed

    def stem_tokens(self, tokens: list[str]) -> list[str]:
        stemmed = []
        for tok in tokens:
            s = self.stem_token(tok)
            if s and len(s) >= 2 and s not in self.stopwords:
                stemmed.append(s)
        return stemmed

    def preprocess_detailed(self, text: str) -> dict[str, Any]:
        """Jalankan seluruh pipeline dan kembalikan output tiap tahap (untuk inspeksi & UI)."""
        cleaned = self.clean_domain_text(text)
        tokens = self.tokenize(cleaned)
        no_stop = self.remove_stopwords(tokens)
        stemmed = self.stem_tokens(no_stop)
        return {
            "cleaned_text": cleaned,
            "tokens": tokens,
            "after_stopwords": no_stop,
            "stemmed_tokens": stemmed,
            "final_text": " ".join(stemmed),
        }

    def preprocess_tokens(self, text: str) -> list[str]:
        cleaned = self.clean_domain_text(text)
        tokens = self.tokenize(cleaned)
        no_stop = self.remove_stopwords(tokens)
        return self.stem_tokens(no_stop)

    def preprocess_to_string(self, text: str) -> str:
        return " ".join(self.preprocess_tokens(text))


def run_corpus_preprocessing() -> dict[str, Any]:
    raw_path = DATA_DIR / "raw_corpus.json"
    clean_json_path = DATA_DIR / "clean_corpus.json"
    clean_csv_path = DATA_DIR / "clean_corpus.csv"
    examples_path = REPORTS_DIR / "preprocessing_examples.json"

    with raw_path.open("r", encoding="utf-8") as f:
        raw_docs: list[dict[str, Any]] = json.load(f)

    preprocessor = CerpenPreprocessor()
    clean_docs: list[dict[str, Any]] = []

    raw_vocab: set[str] = set()
    clean_vocab: set[str] = set()
    total_raw_tokens = 0
    total_clean_tokens = 0

    for doc in raw_docs:
        raw_title = doc.get("title", "")
        raw_content = doc.get("content_raw", "")
        raw_tokens_sample = re.findall(r"[a-zA-Z]+", raw_content.lower())
        raw_vocab.update(raw_tokens_sample)
        total_raw_tokens += len(raw_tokens_sample)

        title_tokens = preprocessor.preprocess_tokens(raw_title)
        content_tokens = preprocessor.preprocess_tokens(raw_content)

        clean_vocab.update(content_tokens)
        total_clean_tokens += len(content_tokens)

        clean_docs.append(
            {
                "doc_id": doc["doc_id"],
                "title": raw_title,
                "author": doc.get("author", "Redaksi"),
                "source": doc.get("source", ""),
                "date": doc.get("date", ""),
                "url": doc.get("url", ""),
                "title_clean": " ".join(title_tokens),
                "content_clean": " ".join(content_tokens),
                "clean_token_count": len(content_tokens),
            }
        )

    with clean_json_path.open("w", encoding="utf-8") as f:
        json.dump(clean_docs, f, ensure_ascii=False, indent=2)

    fieldnames = [
        "doc_id",
        "title",
        "author",
        "source",
        "date",
        "url",
        "clean_token_count",
        "title_clean",
        "content_clean",
    ]
    with clean_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in clean_docs:
            writer.writerow({k: d.get(k, "") for k in fieldnames})

    # Ambil 5 contoh before/after dari dokumen nyata yang representatif
    sample_indices = [0, min(50, len(raw_docs) - 1), min(150, len(raw_docs) - 1), min(300, len(raw_docs) - 1), min(450, len(raw_docs) - 1)]
    seen_idx = []
    for idx in sample_indices:
        if idx not in seen_idx:
            seen_idx.append(idx)

    examples = []
    for idx in seen_idx:
        raw_doc = raw_docs[idx]
        snippet_raw = raw_doc["content_raw"][:420]
        detail = preprocessor.preprocess_detailed(snippet_raw)
        examples.append(
            {
                "doc_id": raw_doc["doc_id"],
                "title": raw_doc["title"],
                "source": raw_doc["source"],
                "before_raw": snippet_raw,
                "after_cleaned": detail["cleaned_text"],
                "tokens_before_stopwords": detail["tokens"][:35],
                "tokens_after_stopwords": detail["after_stopwords"][:30],
                "after_stemmed_final": detail["final_text"],
            }
        )

    summary = {
        "total_documents": len(clean_docs),
        "total_raw_tokens": total_raw_tokens,
        "total_clean_tokens": total_clean_tokens,
        "raw_vocabulary_size": len(raw_vocab),
        "clean_vocabulary_size": len(clean_vocab),
        "token_reduction_pct": round((1 - total_clean_tokens / max(total_raw_tokens, 1)) * 100, 2),
        "vocab_reduction_pct": round((1 - len(clean_vocab) / max(len(raw_vocab), 1)) * 100, 2),
        "custom_domain_stopwords_count": len(CUSTOM_CERPEN_STOPWORDS),
        "custom_domain_stopwords_sample": sorted(CUSTOM_CERPEN_STOPWORDS)[:40],
        "examples": examples,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with examples_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


def main() -> None:
    summary = run_corpus_preprocessing()
    print("[PREPROCESS] Ringkasan Custom Preprocessing Cerpen:")
    print(f"  Dokumen diproses    : {summary['total_documents']}")
    print(f"  Token mentah        : {summary['total_raw_tokens']:,}")
    print(f"  Token bersih        : {summary['total_clean_tokens']:,} (reduksi {summary['token_reduction_pct']}%)")
    print(f"  Kosakata mentah     : {summary['raw_vocabulary_size']:,}")
    print(f"  Kosakata bersih     : {summary['clean_vocabulary_size']:,} (reduksi {summary['vocab_reduction_pct']}%)")


if __name__ == "__main__":
    main()
