"""
Crawler untuk korpus Cerpen / Cerita Fiksi Indonesia (Kategori 7).
Mengambil cerpen nyata melalui WordPress REST API dari portal sastra Indonesia:
- BasaBasi.co (Cerita Pendek)
- BacaPetra.co (Cerpen & Cerpen Terjemahan)
- Litera.co.id (Cerpen)
"""

from __future__ import annotations

import csv
import html
import json
import re
import time
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

SOURCES = [
    {
        "name": "BasaBasi.co",
        "base_url": "https://basabasi.co",
        "categories": "3",
        "per_page": 50,
    },
    {
        "name": "BacaPetra.co",
        "base_url": "https://bacapetra.co",
        "categories": "3,73",
        "per_page": 50,
    },
    {
        "name": "Litera.co.id",
        "base_url": "https://litera.co.id",
        "categories": "11",
        "per_page": 50,
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

MIN_CHARS = 400
TARGET_DOCS = 680


def fetch_json_with_retry(
    session: requests.Session, url: str, params: dict[str, Any] | None = None, retries: int = 3
) -> tuple[Any, requests.Response] | tuple[None, None]:
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, params=params, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp.json(), resp
            if resp.status_code in (400, 404):
                return None, resp
            print(f"  [WARN] HTTP {resp.status_code} on {url} (attempt {attempt}/{retries})")
        except requests.RequestException as exc:
            print(f"  [WARN] Request error on {url} (attempt {attempt}/{retries}): {exc}")
        time.sleep(1.0 * attempt)
    return None, None


def fetch_authors(session: requests.Session, base_url: str) -> dict[int, str]:
    authors: dict[int, str] = {}
    page = 1
    while True:
        data, resp = fetch_json_with_retry(
            session, f"{base_url}/wp-json/wp/v2/users", params={"per_page": 100, "page": page}
        )
        if not data or not isinstance(data, list):
            break
        for user in data:
            uid = user.get("id")
            name = html.unescape(str(user.get("name") or "")).strip()
            if uid is not None and name:
                authors[int(uid)] = name
        total_pages = int(resp.headers.get("X-WP-TotalPages", "1")) if resp else 1
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.2)
    return authors


def html_to_raw_text(html_content: str) -> str:
    """Konversi HTML artikel menjadi teks mentah terstruktur tanpa mengubah gaya bahasa/kata dasar."""
    soup = BeautifulSoup(html_content or "", "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "figure", "figcaption"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = html.unescape(text)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def clean_title(raw_title: str) -> str:
    soup = BeautifulSoup(raw_title or "", "lxml")
    return re.sub(r"\s+", " ", html.unescape(soup.get_text())).strip()


def crawl_all_sources() -> list[dict[str, Any]]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    collected: list[dict[str, Any]] = []

    for src in SOURCES:
        name = src["name"]
        base_url = src["base_url"]
        print(f"\n[CRAWL] Memulai crawling dari {name} ({base_url})...")
        author_map = fetch_authors(session, base_url)
        print(f"  -> Memuat {len(author_map)} profil penulis.")

        page = 1
        total_pages = 1
        src_count = 0
        while page <= total_pages and len(collected) < TARGET_DOCS:
            params = {
                "categories": src["categories"],
                "per_page": src["per_page"],
                "page": page,
                "status": "publish",
                "_fields": "id,date,link,title,content,author",
            }
            posts, resp = fetch_json_with_retry(
                session, f"{base_url}/wp-json/wp/v2/posts", params=params
            )
            if not posts or not isinstance(posts, list):
                break

            if resp is not None:
                try:
                    total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
                except ValueError:
                    total_pages = 1

            for post in posts:
                title = clean_title(post.get("title", {}).get("rendered", ""))
                content_html = post.get("content", {}).get("rendered", "")
                content_raw = html_to_raw_text(content_html)
                url = str(post.get("link") or "").strip()

                if not title or not url or len(content_raw) < MIN_CHARS:
                    continue

                author_id = post.get("author")
                author_name = author_map.get(author_id, "Redaksi") if author_id else "Redaksi"
                date_str = str(post.get("date") or "")[:10]
                word_count = len(content_raw.split())

                doc_idx = len(collected) + 1
                collected.append(
                    {
                        "doc_id": f"CERPEN-{doc_idx:04d}",
                        "title": title,
                        "author": author_name,
                        "source": name,
                        "date": date_str,
                        "url": url,
                        "content_html_sample": content_html[:800],
                        "content_raw": content_raw,
                        "word_count": word_count,
                    }
                )
                src_count += 1
                if len(collected) >= TARGET_DOCS:
                    break

            print(f"  -> Halaman {page}/{total_pages}: total {src_count} cerpen dari {name}")
            page += 1
            time.sleep(0.3)

    return collected


def save_corpus(docs: list[dict[str, Any]], json_path: Path, csv_path: Path) -> None:
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)

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
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in docs:
            writer.writerow({k: d.get(k, "") for k in fieldnames})


def main() -> None:
    docs = crawl_all_sources()
    raw_json = DATA_DIR / "raw_corpus.json"
    raw_csv = DATA_DIR / "raw_corpus.csv"
    save_corpus(docs, raw_json, raw_csv)
    print(f"\n[DONE] Total korpus mentah tersimpan: {len(docs)} dokumen")
    print(f"       JSON: {raw_json}")
    print(f"       CSV : {raw_csv}")


if __name__ == "__main__":
    main()
