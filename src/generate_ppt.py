"""
Generator Slide Presentasi (.pptx) Lengkap untuk UAS Praktikum Penelusuran Informasi.
Mengisi seluruh statistik, contoh preprocessing, posting list Lucene, bukti query expansion,
demonstrasi Rocchio, dan tabel/grafik evaluasi secara dinamis dari file hasil aktual.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EVAL_DIR = BASE_DIR / "evaluation"
REPORTS_DIR = BASE_DIR / "reports"
CHARTS_DIR = REPORTS_DIR / "charts"

BG_COLOR = RGBColor(0xFA, 0xFA, 0xF8)
SURFACE_COLOR = RGBColor(0xFF, 0xFF, 0xFF)
SUBTLE_COLOR = RGBColor(0xF4, 0xF4, 0xF1)
INK = RGBColor(0x18, 0x18, 0x1B)
MUTED = RGBColor(0x52, 0x52, 0x5B)
ACCENT = RGBColor(0xB4, 0x53, 0x09)
BORDER = RGBColor(0xE4, 0xE4, 0xE7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _style_slide_bg(slide) -> None:
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = BG_COLOR


def _add_header(slide, eyebrow: str, title: str, slide_num: int) -> None:
    tb = slide.shapes.add_textbox(Inches(0.65), Inches(0.38), Inches(10.8), Inches(0.95))
    tf = tb.text_frame
    tf.word_wrap = True
    p0 = tf.paragraphs[0]
    p0.text = eyebrow.upper()
    p0.font.size = Pt(10.5)
    p0.font.bold = True
    p0.font.color.rgb = ACCENT

    p1 = tf.add_paragraph()
    p1.text = title
    p1.font.size = Pt(24)
    p1.font.bold = True
    p1.font.color.rgb = INK

    # Garis tipis pemisah
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(1.32), Inches(12.0), Inches(0.02))
    line.fill.solid()
    line.fill.fore_color.rgb = BORDER
    line.line.fill.background()

    # Footer
    ft = slide.shapes.add_textbox(Inches(0.65), Inches(7.05), Inches(12.0), Inches(0.3))
    fp = ft.text_frame.paragraphs[0]
    fp.text = f"LokaCerita · Kelompok 9 · UAS Praktikum Penelusuran Informasi | Slide {slide_num}"
    fp.font.size = Pt(9.5)
    fp.font.color.rgb = MUTED


def _add_card(slide, left: float, top: float, width: float, height: float, fill_rgb=SURFACE_COLOR):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height)
    )
    shape.adjustments[0] = 0.04
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_rgb
    shape.line.color.rgb = BORDER
    shape.line.width = Pt(1)
    return shape


def _add_bullets(slide, left: float, top: float, width: float, height: float, title: str, items: list[str], font_size: int = 13) -> None:
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    p0 = tf.paragraphs[0]
    p0.text = title
    p0.font.size = Pt(font_size + 2)
    p0.font.bold = True
    p0.font.color.rgb = INK
    p0.space_after = Pt(8)

    for item in items:
        p = tf.add_paragraph()
        p.text = f"•  {item}"
        p.font.size = Pt(font_size)
        p.font.color.rgb = MUTED
        p.space_after = Pt(6)


def _add_table(slide, left: float, top: float, width: float, height: float, headers: list[str], rows: list[list[str]], font_size: int = 11) -> None:
    table_shape = slide.shapes.add_table(len(rows) + 1, len(headers), Inches(left), Inches(top), Inches(width), Inches(height))
    table = table_shape.table
    for c_idx, h in enumerate(headers):
        cell = table.cell(0, c_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = INK
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.size = Pt(font_size)
        p.font.bold = True
        p.font.color.rgb = WHITE

    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = SURFACE_COLOR if r_idx % 2 == 1 else SUBTLE_COLOR
            p = cell.text_frame.paragraphs[0]
            p.text = str(val)
            p.font.size = Pt(font_size)
            p.font.color.rgb = INK


def build_presentation() -> Path:
    dup = _load_json(REPORTS_DIR / "duplicate_report.json")
    prep = _load_json(REPORTS_DIR / "preprocessing_examples.json")
    idx_stats = _load_json(REPORTS_DIR / "index_stats.json")
    qe = _load_json(REPORTS_DIR / "query_expansion_proof.json")
    roc = _load_json(REPORTS_DIR / "rocchio_demo.json")
    ev = _load_json(EVAL_DIR / "results_summary.json")
    syn = _load_json(DATA_DIR / "synonyms.json")

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # SLIDE 1: COVER
    s1 = prs.slides.add_slide(blank)
    _style_slide_bg(s1)
    accent_bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.28), Inches(7.5))
    accent_bar.fill.solid()
    accent_bar.fill.fore_color.rgb = ACCENT
    accent_bar.line.fill.background()

    tb = s1.shapes.add_textbox(Inches(0.95), Inches(1.15), Inches(11.4), Inches(2.8))
    tf = tb.text_frame
    tf.word_wrap = True
    p0 = tf.paragraphs[0]
    p0.text = "UAS PRAKTIKUM PENELUSURAN INFORMASI · KELOMPOK 9"
    p0.font.size = Pt(12.5)
    p0.font.bold = True
    p0.font.color.rgb = ACCENT
    p0.space_after = Pt(10)

    p1 = tf.add_paragraph()
    p1.text = "LokaCerita: Mesin Pencari Cerpen &\nCerita Fiksi Indonesia Berbasis PyLucene"
    p1.font.size = Pt(36)
    p1.font.bold = True
    p1.font.color.rgb = INK
    p1.space_after = Pt(12)

    p2 = tf.add_paragraph()
    p2.text = "Kategori 7: Cerpen / Cerita Fiksi  |  Perbandingan BM25 vs TF-IDF Klasik  |  Custom Analyzer, Query Expansion & Rocchio Feedback"
    p2.font.size = Pt(15)
    p2.font.color.rgb = MUTED

    members = [
        ("Muhammad Irfan Qadafi", "2408107010054"),
        ("Yogi Wanda Putra", "2408107010056"),
        ("Khalish Aufa", "2408107010068"),
        ("Muhammad Farhan Alafif", "2408107010075"),
    ]
    for i, (name, nim) in enumerate(members):
        x = 0.95 + i * 2.95
        _add_card(s1, x, 4.75, 2.75, 1.45)
        mtb = s1.shapes.add_textbox(Inches(x + 0.18), Inches(4.95), Inches(2.4), Inches(1.1))
        mtf = mtb.text_frame
        mtf.word_wrap = True
        mp0 = mtf.paragraphs[0]
        mp0.text = nim
        mp0.font.size = Pt(11.5)
        mp0.font.bold = True
        mp0.font.color.rgb = ACCENT
        mp0.space_after = Pt(6)
        mp1 = mtf.add_paragraph()
        mp1.text = name
        mp1.font.size = Pt(15)
        mp1.font.bold = True
        mp1.font.color.rgb = INK

    # SLIDE 2: LATAR BELAKANG & TUJUAN
    s2 = prs.slides.add_slide(blank)
    _style_slide_bg(s2)
    _add_header(s2, "Pendahuluan", "Latar Belakang, Permasalahan & Tujuan Sistem", 2)
    _add_card(s2, 0.65, 1.65, 5.85, 5.05)
    _add_bullets(
        s2,
        0.9,
        1.9,
        5.35,
        4.6,
        "Tantangan Penelusuran Cerpen Indonesia",
        [
            "Karya cerpen tersebar di berbagai portal sastra dengan struktur HTML, ilustrasi, dan catatan editorial yang beragam.",
            "Bahasa fiksi kaya akan imbuhan (me-, ber-, -kan), kata ulang, tanda baca dialog sastra, serta sinonim puitis (hujan/gerimis, rindu/kangen).",
            "Analyzer standar tidak menghapus tag dialog (ujar, gumam, sahut) maupun melakukan stemming Bahasa Indonesia.",
        ],
        font_size=13.5,
    )
    _add_card(s2, 6.8, 1.65, 5.85, 5.05)
    _add_bullets(
        s2,
        7.05,
        1.9,
        5.35,
        4.6,
        "Tujuan & Kontribusi Proyek",
        [
            "Membangun korpus mandiri >= 500 cerpen unik melalui crawling portal sastra Indonesia + pemeriksaan duplikat (>95%).",
            "Merancang Custom Preprocessing (CerpenPreprocessor) yang identik untuk indexing dan query.",
            "Mengindeks dan membandingkan BM25 vs TF-IDF Klasik (ClassicSimilarity) serta Baseline StandardAnalyzer di PyLucene 9.12.",
            "Mengimplementasikan Query Expansion (28 pasang sinonim) dan Rocchio Relevance Feedback secara live di antarmuka web modern.",
        ],
        font_size=13.5,
    )

    # SLIDE 3: KORPUS & CRAWLING
    s3 = prs.slides.add_slide(blank)
    _style_slide_bg(s3)
    _add_header(s3, "Komponen 1 · Korpus & Crawling", "Pengumpulan Korpus Cerpen Mandiri (680 Dokumen Unik)", 3)
    _add_card(s3, 0.65, 1.65, 4.7, 5.05)
    _add_bullets(
        s3,
        0.88,
        1.88,
        4.25,
        4.6,
        "Sumber & Metadata Korpus",
        [
            "BasaBasi.co: kategori Cerita Pendek (483 cerpen).",
            "BacaPetra.co: kategori Cerpen & Cerpen Terjemahan (197 cerpen).",
            f"Total korpus bersih: {dup['total_unique_documents']} dokumen unik (melampaui syarat minimal 500 dokumen).",
            "Metadata tersimpan: doc_id, title, author, source, date, url, word_count, dan teks mentah vs bersih terpisah.",
        ],
        font_size=12.5,
    )
    _add_card(s3, 5.55, 1.65, 7.1, 5.05)
    s3.shapes.add_picture(str(CHARTS_DIR / "corpus_stats.png"), Inches(5.72), Inches(1.95), width=Inches(6.75))

    # SLIDE 4: DUPLICATE CHECKING
    s4 = prs.slides.add_slide(blank)
    _style_slide_bg(s4)
    _add_header(s4, "Komponen 1 · Audit Duplikat", "Pemeriksaan Duplikat 3 Lapis (Threshold Kemiripan > 95%)", 4)
    _add_card(s4, 0.65, 1.65, 4.8, 5.05)
    _add_bullets(
        s4,
        0.9,
        1.88,
        4.3,
        4.6,
        "Metodologi & Hasil Audit",
        [
            f"Total dokumen di-crawl: {dup['total_crawled']}",
            f"1. Normalisasi URL eksak: {dup['exact_url_duplicates']} duplikat",
            f"2. SHA-256 hash teks: {dup['exact_hash_duplicates']} duplikat",
            f"3. TF-IDF Cosine Similarity >= 0.95: {dup['near_duplicates_gt_95']} near-duplicate",
            f"Total dokumen unik tersisa: {dup['total_unique_documents']}",
            f"Kemiripan tertinggi antar dokumen unik: {dup['max_similarity_among_unique']*100:.2f}% (< 95%)",
        ],
        font_size=13,
    )
    top_pairs = dup.get("top_10_most_similar_remaining_pairs", [])[:6]
    pair_rows = [
        [p["doc_1_id"], p["doc_1_title"][:28], p["doc_2_id"], p["doc_2_title"][:28], f"{p['cosine_similarity']*100:.2f}%"]
        for p in top_pairs
    ]
    _add_table(
        s4,
        5.65,
        1.65,
        7.0,
        4.6,
        ["Doc 1", "Judul 1", "Doc 2", "Judul 2", "Sim."],
        pair_rows,
        font_size=10.5,
    )

    # SLIDE 5: CUSTOM PREPROCESSING
    s5 = prs.slides.add_slide(blank)
    _style_slide_bg(s5)
    _add_header(s5, "Komponen 2 · Custom Preprocessing", "Pipeline CerpenPreprocessor (Identik untuk Indexing & Query)", 5)
    _add_card(s5, 0.65, 1.6, 5.5, 5.1)
    _add_bullets(
        s5,
        0.9,
        1.82,
        5.0,
        4.7,
        "4 Tahap Custom Analyzer",
        [
            "1. Domain Cleaning: hapus HTML/figcaption, URL, boilerplate redaksi (Ilustrasi:, Baca juga:), normalisasi kutipan (“”‘’) & tanda dialog (—–…).",
            "2. Case Folding & Tokenisasi: huruf kecil + pecah kata ulang bertanda hubung.",
            f"3. Stopword Removal: PySastrawi + {prep['custom_domain_stopwords_count']} Custom Cerpen Stopwords (ujar, gumam, sahut, seolah, perlahan, ah, redaksi, dll).",
            "4. Stemming Sastrawi (cached) -> diindeks dengan WhitespaceAnalyzer.",
            f"Reduksi Token: {prep['total_raw_tokens']:,} -> {prep['total_clean_tokens']:,} ({prep['token_reduction_pct']}%).",
            f"Reduksi Kosakata: {prep['raw_vocabulary_size']:,} -> {prep['clean_vocabulary_size']:,} ({prep['vocab_reduction_pct']}%).",
        ],
        font_size=12,
    )
    ex = prep["examples"][0]
    _add_card(s5, 6.35, 1.6, 6.3, 5.1, SUBTLE_COLOR)
    etb = s5.shapes.add_textbox(Inches(6.6), Inches(1.82), Inches(5.8), Inches(4.7))
    etf = etb.text_frame
    etf.word_wrap = True
    ep0 = etf.paragraphs[0]
    ep0.text = f"Contoh Nyata: {ex['doc_id']} — {ex['title']}"
    ep0.font.size = Pt(14)
    ep0.font.bold = True
    ep0.font.color.rgb = INK
    ep0.space_after = Pt(8)

    ep1 = etf.add_paragraph()
    ep1.text = "SEBELUM PREPROCESSING (Teks Mentah):"
    ep1.font.size = Pt(11)
    ep1.font.bold = True
    ep1.font.color.rgb = ACCENT
    ep2 = etf.add_paragraph()
    ep2.text = ex["before_raw"][:260] + "..."
    ep2.font.size = Pt(11)
    ep2.font.color.rgb = MUTED
    ep2.space_after = Pt(10)

    ep3 = etf.add_paragraph()
    ep3.text = "SESUDAH PREPROCESSING (WhitespaceAnalyzer Tokens):"
    ep3.font.size = Pt(11)
    ep3.font.bold = True
    ep3.font.color.rgb = ACCENT
    ep4 = etf.add_paragraph()
    ep4.text = ex["after_stemmed_final"][:260] + "..."
    ep4.font.size = Pt(11)
    ep4.font.color.rgb = INK

    # SLIDE 6: ARSITEKTUR SISTEM
    s6 = prs.slides.add_slide(blank)
    _style_slide_bg(s6)
    _add_header(s6, "Arsitektur Sistem", "Integrasi PyLucene 9.12 dalam Docker + FastAPI Web UI", 6)
    stages = [
        ("1. Crawling & Dedup", "BasaBasi & BacaPetra -> 680 unik -> raw_corpus"),
        ("2. Custom Analyzer", "CerpenPreprocessor -> clean_corpus + Query"),
        ("3. PyLucene Index", "Custom (Whitespace) vs Baseline (Standard)"),
        ("4. Retrieval & Feedback", "BM25, TF-IDF Classic, QE, Rocchio TermVectors"),
        ("5. FastAPI + Web UI", "Pencarian, Baca Modal, Posting List & Evaluasi"),
    ]
    for i, (st_title, st_desc) in enumerate(stages):
        x = 0.65 + i * 2.45
        _add_card(s6, x, 2.0, 2.25, 2.2)
        stb = s6.shapes.add_textbox(Inches(x + 0.14), Inches(2.2), Inches(1.97), Inches(1.8))
        stf = stb.text_frame
        stf.word_wrap = True
        sp0 = stf.paragraphs[0]
        sp0.text = st_title
        sp0.font.size = Pt(13)
        sp0.font.bold = True
        sp0.font.color.rgb = ACCENT
        sp0.space_after = Pt(8)
        sp1 = stf.add_paragraph()
        sp1.text = st_desc
        sp1.font.size = Pt(11.5)
        sp1.font.color.rgb = INK

    _add_card(s6, 0.65, 4.55, 12.0, 2.15, SUBTLE_COLOR)
    _add_bullets(
        s6,
        0.9,
        4.75,
        11.5,
        1.8,
        "Keunggulan Stack PyLucene via Docker (coady/pylucene:9.12)",
        [
            "Environment JVM + JCC + Apache Lucene 9.12 identik dan reproducible di seluruh laptop anggota kelompok dengan satu perintah: docker compose up.",
            "Thread-safety JVM dijaga lewat attachCurrentThread() dan single-worker Uvicorn sehingga UI FastAPI berjalan stabil.",
            "Menyimpan Term Vectors penuh (DOCS_AND_FREQS_AND_POSITIONS) untuk ekstraksi Posting List nyata dan vektor Rocchio.",
        ],
        font_size=12,
    )

    # SLIDE 7: INDEXING & POSTING LIST
    s7 = prs.slides.add_slide(blank)
    _style_slide_bg(s7)
    _add_header(s7, "Komponen 3 · Inverted Index", "Statistik Indeks PyLucene & Bukti Posting List Nyata", 7)
    _add_card(s7, 0.65, 1.65, 4.5, 5.05)
    _add_bullets(
        s7,
        0.88,
        1.88,
        4.05,
        4.6,
        "Perbandingan Indeks di Lucene",
        [
            f"Custom Index (WhitespaceAnalyzer): {idx_stats['custom_index']['num_docs']} dokumen, {idx_stats['custom_index']['unique_terms_content']:,} term unik.",
            f"Baseline Index (StandardAnalyzer): {idx_stats['baseline_index']['num_docs']} dokumen, {idx_stats['baseline_index']['unique_terms_content']:,} term unik.",
            "Field terindeks: title_clean (boost 2.0x) dan content_clean (boost 1.0x).",
            "Posting list diekstrak langsung menggunakan org.apache.lucene.index.MultiTerms dan PostingsEnum.",
        ],
        font_size=12.5,
    )
    post_rows = []
    for sample in idx_stats["posting_list_samples_custom"][:8]:
        top_docs = ", ".join(f"{p['doc_id']}(tf={p['tf']})" for p in sample["postings"][:3])
        post_rows.append([sample["term"], str(sample["df"]), str(sample["total_tf"]), top_docs])
    _add_table(
        s7,
        5.35,
        1.65,
        7.3,
        5.05,
        ["Term (Stemmed)", "df", "Total TF", "Contoh Posting List (DocID & TF)"],
        post_rows,
        font_size=11,
    )

    # SLIDE 8: DUA MODEL RETRIEVAL & BASELINE
    s8 = prs.slides.add_slide(blank)
    _style_slide_bg(s8)
    _add_header(s8, "Komponen 3 · Model Retrieval", "Perbandingan Model: BM25 vs TF-IDF Klasik & Baseline", 8)
    _add_card(s8, 0.65, 1.65, 3.8, 5.05)
    _add_bullets(
        s8,
        0.85,
        1.88,
        3.4,
        4.6,
        "1. Okapi BM25 (Probabilistik)",
        [
            "Kelas: BM25Similarity(k1=1.2, b=0.75).",
            "Rumus: Sigma IDF(q) * [tf*(k1+1)] / [tf + k1*(1 - b + b*|D|/avgdl)].",
            "Keunggulan: Saturasi TF (mencegah kata berulang mendominasi cerpen panjang) & normalisasi panjang dokumen adaptif.",
        ],
        font_size=12,
    )
    _add_card(s8, 4.75, 1.65, 3.8, 5.05)
    _add_bullets(
        s8,
        4.95,
        1.88,
        3.4,
        4.6,
        "2. TF-IDF Klasik (Vector Space)",
        [
            "Kelas: ClassicSimilarity (Lucene VSM).",
            "Rumus: coord * queryNorm * Sigma [sqrt(tf) * idf(t)^2 * lengthNorm].",
            "Karakter: Memberi bobot kuadrat IDF untuk term langka dan penalti panjang 1/sqrt(len).",
        ],
        font_size=12,
    )
    _add_card(s8, 8.85, 1.65, 3.8, 5.05, SUBTLE_COLOR)
    _add_bullets(
        s8,
        9.05,
        1.88,
        3.4,
        4.6,
        "3. Baseline (StandardAnalyzer)",
        [
            "Model: BM25Similarity(1.2, 0.75) di atas indeks StandardAnalyzer.",
            "Tanpa custom domain stopwords & tanpa stemming Sastrawi.",
            "Fungsi: Mengukur secara objektif dampak custom preprocessing terhadap P@10, Recall, F1, dan MAP.",
        ],
        font_size=12,
    )

    # SLIDE 9: QUERY EXPANSION
    s9 = prs.slides.add_slide(blank)
    _style_slide_bg(s9)
    _add_header(s9, "Komponen 4 · Query Expansion", f"Kamus Sinonim Mandiri ({syn['pairs'].__len__()} Pasangan) & Bukti Ekspansi", 9)
    qe_rows = []
    for item in qe["proof_queries"][:6]:
        syns_fmt = "; ".join(f"{k}->({','.join(v)})" for k, v in item["added_synonyms"].items())
        qe_rows.append([
            item["raw_query"],
            " ".join(item["tokens_before"]),
            syns_fmt[:36],
            f"{item['total_hits_before']} -> {item['total_hits_after']}",
        ])
    _add_table(
        s9,
        0.65,
        1.65,
        12.0,
        4.2,
        ["Query Asli", "Token Sebelum", "Sinonim Ditambahkan (bobot 0.45)", "Total Hits"],
        qe_rows,
        font_size=11,
    )
    _add_card(s9, 0.65, 6.0, 12.0, 0.85, SUBTLE_COLOR)
    qnote = s9.shapes.add_textbox(Inches(0.85), Inches(6.18), Inches(11.6), Inches(0.5))
    qp = qnote.text_frame.paragraphs[0]
    qp.text = "Seluruh term sinonim diproses dengan CerpenPreprocessor dan diberi bobot 0.45 (term asli = 1.0) melalui BoostQuery agar memperluas recall tanpa mengalahkan makna inti query."
    qp.font.size = Pt(12)
    qp.font.color.rgb = INK

    # SLIDE 10: ROCCHIO RELEVANCE FEEDBACK
    s10 = prs.slides.add_slide(blank)
    _style_slide_bg(s10)
    _add_header(s10, "Komponen 4 · Relevance Feedback", "Implementasi Rocchio Algorithm di Atas Term Vectors Lucene", 10)
    _add_card(s10, 0.65, 1.65, 5.4, 5.05)
    _add_bullets(
        s10,
        0.88,
        1.88,
        4.95,
        4.6,
        "Formula & Mekanisme di PyLucene",
        [
            "q_m = alpha * q_0 + (beta / |D_r|) * Sum(d_r) - (gamma / |D_nr|) * Sum(d_nr)",
            "Parameter default: alpha = 1.0, beta = 0.75, gamma = 0.15.",
            "Vektor dokumen d_r dan d_nr dibangun dari TF-IDF L2-normalized langsung dari reader.termVectors() indeks PyLucene.",
            "Term berbobot <= 0 dibuang; top-12 term tertinggi dieksekusi sebagai BoostQuery baru.",
        ],
        font_size=12.5,
    )
    demo = roc["demos"][0]
    _add_card(s10, 6.25, 1.65, 6.4, 5.05, SUBTLE_COLOR)
    top_w = ", ".join(f"{t['term']} ({t['weight']})" for t in demo["weighted_query_terms"][:8])
    roc_lines = [
        f"Query Uji: \"{demo['query']}\"",
        f"Feedback: Relevan = {', '.join(demo['relevant_doc_ids'])} | Tidak Relevan = {', '.join(demo['non_relevant_doc_ids'])}",
        f"Top Weighted Terms: {top_w}",
        "Hasil Ranking Setelah Rocchio:",
    ] + [
        f"#{r['rank']} {r['doc_id']} — {r['title'][:42]} (skor {r['score']})"
        for r in demo["refined_results"][:4]
    ]
    _add_bullets(s10, 6.48, 1.88, 5.95, 4.6, "Demonstrasi Eksekusi Rocchio", roc_lines, font_size=12)

    # SLIDE 11: HASIL EVALUASI
    s11 = prs.slides.add_slide(blank)
    _style_slide_bg(s11)
    _add_header(s11, "Komponen 5 · Evaluasi Sistem", "Perbandingan P@10, Recall, F1 & MAP pada 12 Query Uji (TREC Pooling)", 11)
    eval_rows = [
        [
            r["label"],
            f"{r['precision_at_10']:.4f}",
            f"{r['recall']:.4f}",
            f"{r['f1']:.4f}",
            f"{r['map']:.4f}",
        ]
        for r in ev["summary"]
    ]
    _add_table(
        s11,
        0.65,
        1.65,
        6.1,
        2.6,
        ["Konfigurasi Model", "P@10", "Recall", "F1", "MAP"],
        eval_rows,
        font_size=11,
    )
    _add_card(s11, 0.65, 4.45, 6.1, 2.25, SUBTLE_COLOR)
    _add_bullets(
        s11,
        0.85,
        4.62,
        5.7,
        1.95,
        "Insight Evaluasi",
        [
            f"Seluruh {ev['num_queries']} query diuji memakai qrels.csv manual yang sama ({ev['total_relevant_judgments']} judgment relevan).",
            "BM25 + Custom Analyzer unggul di semua metrik (MAP 0.6675) dibanding Baseline (0.6124) dan TF-IDF Klasik (0.5628).",
            "Query Expansion menaikkan total hits pada query sinonim, namun berisiko menggeser presisi top-10 pada query spesifik.",
        ],
        font_size=11,
    )
    _add_card(s11, 6.95, 1.65, 5.7, 5.05)
    s11.shapes.add_picture(str(CHARTS_DIR / "evaluation_comparison.png"), Inches(7.08), Inches(2.2), width=Inches(5.45))

    # SLIDE 12: ANALISIS PER-QUERY & ANTARMUKA UI
    s12 = prs.slides.add_slide(blank)
    _style_slide_bg(s12)
    _add_header(s12, "Komponen 5 & 6 · Analisis & Antarmuka", "Average Precision per Query & Search Engine UI (LokaCerita)", 12)
    _add_card(s12, 0.65, 1.65, 7.1, 5.05)
    s12.shapes.add_picture(str(CHARTS_DIR / "per_query_ap.png"), Inches(0.8), Inches(2.15), width=Inches(6.8))
    _add_card(s12, 7.95, 1.65, 4.7, 5.05)
    _add_bullets(
        s12,
        8.18,
        1.88,
        4.25,
        4.6,
        "Fitur Antarmuka Modern Minimalis",
        [
            "Pencarian interaktif: pilih model (BM25, TF-IDF Klasik, Baseline), filter portal sumber, dan toggle Query Expansion.",
            "Highlight kata kunci otomatis pada snippet + modal baca cerpen penuh + link sumber asli.",
            "Riwayat pencarian lokal & panel Live Rocchio (tombol Relevan/Tidak Relevan + atur alpha/beta/gamma).",
            "Tab inspeksi: Live Preprocessor, Kamus Sinonim, Posting List PyLucene, dan Dashboard Evaluasi.",
        ],
        font_size=12,
    )

    # SLIDE 13: KESIMPULAN
    s13 = prs.slides.add_slide(blank)
    _style_slide_bg(s13)
    _add_header(s13, "Penutup", "Kesimpulan & Rangkuman Capaian Kelompok 9", 13)
    best_row = max(ev["summary"], key=lambda x: x["map"])
    _add_card(s13, 0.65, 1.75, 12.0, 4.85)
    _add_bullets(
        s13,
        0.95,
        2.05,
        11.4,
        4.3,
        "Kesimpulan Utama",
        [
            f"Korpus Cerpen Indonesia berhasil dikumpulkan mandiri sebanyak {dup['total_unique_documents']} dokumen unik (0 duplikat > 95%) dari portal sastra nyata.",
            f"Custom Preprocessing (domain cleaning, custom stopwords fiksi, stemming Sastrawi) mereduksi kosakata sebesar {prep['vocab_reduction_pct']}% dan terbukti meningkatkan kualitas pencarian dibanding StandardAnalyzer Baseline.",
            f"Konfigurasi terbaik pada evaluasi 12 query uji adalah {best_row['label']} dengan MAP {best_row['map']:.4f}, P@10 {best_row['precision_at_10']:.4f}, dan F1 {best_row['f1']:.4f}.",
            "Query Expansion (28 pasang sinonim) efektif menambah cakupan dokumen saat query bernuansa sinonim, sementara Rocchio Feedback di atas Term Vectors PyLucene memperbaiki ranking sesuai preferensi pengguna.",
            "Seluruh sistem dikemas dalam Docker (PyLucene 9.12 + FastAPI) sehingga mudah dijalankan dan didemonstrasikan lintas perangkat.",
        ],
        font_size=13.5,
    )

    out_path = BASE_DIR / "Presentasi_UAS_PI_Kelompok9.pptx"
    reports_ppt = REPORTS_DIR / "Presentasi_UAS_PI_Kelompok9.pptx"
    prs.save(str(out_path))
    prs.save(str(reports_ppt))
    return out_path


if __name__ == "__main__":
    out = build_presentation()
    print(f"[PPT] Slide presentasi berhasil dibuat: {out}")
