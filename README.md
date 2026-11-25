# LokaCerita — Mesin Pencari Cerpen & Cerita Fiksi Indonesia (PyLucene)

**UAS Praktikum Penelusuran Informasi — Kelompok 9**  
**Kategori 7:** Cerpen / Cerita Fiksi Indonesia

---

## Anggota Kelompok 9

| No | Nama Lengkap | NIM |
| :--- | :--- | :--- |
| 1 | Muhammad Irfan Qadafi | `2408107010054` |
| 2 | Yogi Wanda Putra | `2408107010056` |
| 3 | Khalish Aufa | `2408107010068` |
| 4 | Muhammad Farhan Alafif | `2408107010075` |

---

## Deskripsi Project

**LokaCerita** adalah mesin pencari (*Search Engine*) khusus karya cerpen dan cerita fiksi berbahasa Indonesia yang dibangun menggunakan **Apache Lucene (PyLucene 9.12)** dalam lingkungan **Docker**, dilengkapi antarmuka web modern minimalis berbasis **FastAPI + HTML/CSS/JavaScript**.

Sistem ini mengimplementasikan seluruh tahapan *Information Retrieval* secara utuh:
1. **Crawling Korpus Mandiri** dari portal sastra Indonesia (**BasaBasi.co** dan **BacaPetra.co**) sebanyak **680 dokumen unik** (melampaui batas minimal 500 dokumen).
2. **Duplicate Checking 3 Lapis** (normalisasi URL, SHA-256 hash teks, dan TF-IDF Cosine Similarity >= 0.95) dengan laporan audit lengkap.
3. **Custom Preprocessing (`CerpenPreprocessor`)** yang identik untuk proses *indexing* maupun *query* (pembersihan HTML & tanda baca sastra, *case folding*, tokenisasi, *stopword removal* + custom domain *stopwords* cerpen, serta *stemming* Sastrawi).
4. **Indexing & Perbandingan 2 Model Retrieval + Baseline**:
   - **Okapi BM25** (`BM25Similarity(k1=1.2, b=0.75)`) + Custom Analyzer (`WhitespaceAnalyzer`)
   - **TF-IDF Klasik** (`ClassicSimilarity`) + Custom Analyzer (`WhitespaceAnalyzer`)
   - **Baseline** (`BM25Similarity(1.2, 0.75)` + `StandardAnalyzer` bawaan Lucene pada teks mentah)
5. **Query Expansion** dengan kamus sinonim mandiri (**28 pasangan sinonim** domain cerpen) dan **Rocchio Relevance Feedback** langsung di atas *Term Vectors* indeks PyLucene.
6. **Evaluasi Sistem** pada **12 query uji** menggunakan metode **TREC Pooling** dan *relevance judgment* manual (`0`/`1`) dengan metrik **Precision@10, Recall, F1-Score, dan MAP**.

---

## Struktur Direktori

```text
uas_praktikum_pi_klp9/
├── Dockerfile                         # Image coady/pylucene:9.12 + dependensi Python
├── docker-compose.yml                 # Orkestrasi container LokaCerita
├── requirements.txt                   # Daftar dependensi Python
├── README.md                          # Dokumentasi proyek lengkap
├── Presentasi_UAS_PI_Kelompok9.pptx   # Slide presentasi lengkap
├── data/
│   ├── raw_corpus.json / .csv         # Korpus mentah hasil crawling (680 dokumen unik)
│   ├── clean_corpus.json / .csv       # Korpus bersih hasil custom preprocessing (terpisah)
│   └── synonyms.json                  # Kamus sinonim mandiri (28 pasangan)
├── indexes/
│   ├── custom_index/                  # Indeks Lucene (WhitespaceAnalyzer + TermVectors)
│   └── baseline_index/                # Indeks Lucene (StandardAnalyzer)
├── src/
│   ├── crawler.py                     # Crawler WordPress REST API (BasaBasi.co & BacaPetra.co)
│   ├── deduplicate.py                 # Pemeriksaan duplikat 3 lapis (>95%)
│   ├── preprocessing.py               # Custom preprocessing pipeline (index & query)
│   ├── indexer.py                     # PyLucene indexer & ekstraksi posting list
│   ├── retriever.py                   # SearchEngine (BM25, TF-IDF Klasik, Baseline)
│   ├── query_expansion.py             # Query Expansion berbasis kamus sinonim
│   ├── rocchio.py                     # Rocchio Relevance Feedback dari Lucene TermVectors
│   ├── evaluate.py                    # Evaluasi P@10, Recall, F1, MAP & generator grafik
│   └── generate_ppt.py                # Generator Presentasi_UAS_PI_Kelompok9.pptx
├── evaluation/
│   ├── queries.json                   # 12 query uji tematik cerpen
│   ├── pool.json                      # Pool kandidat dokumen tanpa skor/asal model
│   ├── qrels.csv                      # Relevance judgment manual (187 pasangan, 108 relevan)
│   ├── results_summary.json / .csv    # Tabel perbandingan metrik evaluasi
│   └── per_query_metrics.csv          # Metrik per query (Q01 - Q12)
├── reports/
│   ├── duplicate_report.json / .csv   # Bukti audit duplicate checking (>95%)
│   ├── preprocessing_examples.json    # Contoh before/after preprocessing & statistik reduksi
│   ├── index_stats.json               # Statistik indeks & sampel posting list Lucene
│   ├── query_expansion_proof.json     # 6 bukti query sebelum vs sesudah ekspansi
│   ├── rocchio_demo.json              # Demonstrasi Rocchio relevance feedback
│   └── charts/                        # Grafik evaluasi & statistik korpus (.png)
└── app/
    ├── main.py                        # FastAPI server
    └── static/                        # Antarmuka Web UI modern minimalis
```

---

## Dependencies (`requirements.txt`)

- `fastapi`, `uvicorn[standard]`, `pydantic` — Backend API & web server
- `PySastrawi` — Stemmer & stopword Bahasa Indonesia
- `beautifulsoup4`, `lxml`, `requests` — Crawling & ekstraksi HTML
- `scikit-learn`, `numpy` — TF-IDF Cosine Similarity untuk audit duplikat & perhitungan evaluasi
- `matplotlib`, `Pillow`, `python-pptx` — Grafik evaluasi & pembuatan slide presentasi
- **PyLucene 9.12** (disediakan otomatis oleh base image Docker `coady/pylucene:9.12`)

---

## Cara Instalasi & Menjalankan PyLucene + Search Engine (Docker)

Prasyarat: **Docker Desktop** sudah terinstal dan berjalan.

### 1. Build & Jalankan Search Engine
```bash
docker compose up -d --build
```
Setelah berjalan, buka browser dan akses:
- **Antarmuka Web Search Engine:** http://localhost:8000
- **API Docs (Swagger):** http://localhost:8000/docs

### 2. Menjalankan Ulang Pipeline Secara Bertahap (Opsional)
Data korpus, indeks PyLucene, hasil evaluasi, dan slide sudah siap pakai. Jika ingin mengulang tahap tertentu:

```bash
# 1. Crawling & pemeriksaan duplikat (>95%) [di Python lokal / container]
python src/crawler.py
python src/deduplicate.py

# 2. Custom preprocessing (menghasilkan data/clean_corpus.json & .csv)
python src/preprocessing.py

# 3. Indexing PyLucene (Custom WhitespaceAnalyzer & Baseline StandardAnalyzer)
docker compose run --rm search-engine python src/indexer.py

# 4. Pembuktian Query Expansion & Demonstrasi Rocchio
docker compose run --rm search-engine python src/query_expansion.py
docker compose run --rm search-engine python src/rocchio.py

# 5. Evaluasi Sistem & Pembuatan Grafik
docker compose run --rm search-engine python src/evaluate.py --evaluate

# 6. Generate Slide Presentasi (.pptx)
docker compose run --rm search-engine python src/generate_ppt.py
```

Untuk menghentikan container:
```bash
docker compose down
```

---

## Ringkasan Teknis & Hasil Eksperimen

### 1. Korpus & Audit Duplikat
- **Sumber:** BasaBasi.co (`483` cerpen) dan BacaPetra.co (`197` cerpen).
- **Total Di-crawl:** `680` cerpen | **Duplikat URL / SHA-256 / Near-Duplicate (>=95%):** `0` | **Total Unik:** `680` dokumen.
- **Kemiripan Maksimal Antar Dokumen Unik:** `0.716882` (`71.69%`, jauh di bawah ambang `95%`). Bukti lengkap tersedia di [duplicate_report.csv](reports/duplicate_report.csv).

### 2. Custom Preprocessing (`CerpenPreprocessor`)
- **Reduksi Token:** `1,233,141` -> `579,121` token (`53.04%`).
- **Reduksi Kosakata:** `43,010` -> `21,573` term unik (`49.84%`).
- **Custom Domain Stopwords:** `128` kata khusus fiksi/cerpen (seperti `ujar`, `ucap`, `sahut`, `gumam`, `seolah`, `perlahan`, `ilustrasi`, `redaksi`), dengan tetap mempertahankan kata tematik penting (`ibu`, `hari`) dari daftar stopword umum.

### 3. Model Retrieval & Parameter di PyLucene
- **Okapi BM25 (`BM25Similarity`):** parameter `k1 = 1.2`, `b = 0.75`, dengan bobot field judul `2.0x` dan isi `1.0x`.
  $$\text{Score}(D, Q) = \sum_{q_i \in Q} \text{IDF}(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$
- **TF-IDF Klasik (`ClassicSimilarity`):** Vector Space Model klasik Apache Lucene dengan pembobotan $\sqrt{tf} \cdot \text{idf}^2 \cdot \text{lengthNorm}$ serta normalisasi koordinasi query.
- **Rocchio Relevance Feedback:** parameter default $\alpha = 1.0$, $\beta = 0.75$, $\gamma = 0.15$ di atas *Term Vectors* L2-normalized langsung dari indeks `indexes/custom_index`.

### 4. Contoh Query & Hasil Nyata

**Contoh Query:** `"hujan malam di stasiun"`
- **Token setelah Custom Preprocessing:** `['hujan', 'malam', 'stasiun']`
- **Top-3 Hasil Awal (`BM25 + Custom`):**
  1. `CERPEN-0035` — *Kala itu Hujan Belum Reda* (Skor: `6.1776`)
  2. `CERPEN-0079` — *TARIAN HUJAN* (Skor: `6.0695`)
  3. `CERPEN-0173` — *Kesaksian Pawang Hujan* (Skor: `5.5718`)
- **Rocchio Feedback** (menandai `CERPEN-0079`, `CERPEN-0321` relevan & `CERPEN-0585` tidak relevan):
  - **Term berbobot baru:** `stasiun (0.844)`, `hujan (0.5262)`, `malam (0.2751)`, `sampan (0.0712)`, `dermaga (0.0622)`, `apartemen (0.0601)`, `gadis (0.0567)`, `balkon (0.0556)`

**Contoh Query Expansion:** `"hujan malam sunyi"`
- **Sebelum:** `['hujan', 'malam', 'sunyi']` (`588` hits)
- **Sesudah:** ditambah sinonim berbobot `0.45` (`deras`, `gerimis`, `mendung`, `gelap`, `gulita`, `kelam`, `hening`, `senyap`, `sepi`) -> `640` hits.

### 5. Tabel Perbandingan Evaluasi Sistem (12 Query Uji, K=10)

| Konfigurasi Model | Precision@10 | Recall | F1-Score | MAP |
| :--- | :---: | :---: | :---: | :---: |
| **BM25 + Custom Analyzer** | **0.6750** | **0.7772** | **0.7077** | **0.6675** |
| **BM25 + Custom + Query Expansion** | 0.6417 | 0.7404 | 0.6732 | 0.6653 |
| **BM25 + StandardAnalyzer (Baseline)** | 0.6417 | 0.7494 | 0.6773 | 0.6124 |
| **TF-IDF Klasik + Custom Analyzer** | 0.6000 | 0.6631 | 0.6181 | 0.5628 |
