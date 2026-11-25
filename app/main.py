"""
FastAPI Backend untuk LokaCerita — Mesin Pencari Cerpen & Cerita Fiksi Indonesia
(Kelompok 9 — UAS Praktikum Penelusuran Informasi).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.indexer import ensure_jvm
from src.retriever import SearchEngine
from src.rocchio import RocchioFeedback

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EVAL_DIR = BASE_DIR / "evaluation"
REPORTS_DIR = BASE_DIR / "reports"
STATIC_DIR = Path(__file__).resolve().parent / "static"

state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_jvm()
    engine = SearchEngine()
    state["engine"] = engine
    state["rocchio"] = RocchioFeedback(engine)
    yield


app = FastAPI(
    title="LokaCerita — Search Engine Cerpen Indonesia",
    description="UAS Praktikum Penelusuran Informasi Kelompok 9 (PyLucene 9.12)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RocchioRequest(BaseModel):
    query: str = Field(..., min_length=1)
    model: str = Field(default="bm25_custom")
    relevant_ids: list[str] = Field(default_factory=list)
    non_relevant_ids: list[str] = Field(default_factory=list)
    alpha: float = Field(default=1.0, ge=0.0, le=3.0)
    beta: float = Field(default=0.75, ge=0.0, le=3.0)
    gamma: float = Field(default=0.15, ge=0.0, le=3.0)
    top_k: int = Field(default=10, ge=1, le=30)


class PreprocessRequest(BaseModel):
    text: str = Field(..., min_length=1)


def _read_json_safe(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/")
async def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    engine: SearchEngine = state["engine"]
    return engine.get_health_stats()


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=1, description="Kata kunci pencarian cerpen"),
    model: str = Query("bm25_custom", description="bm25_custom | tfidf_custom | bm25_baseline"),
    top_k: int = Query(10, ge=1, le=50),
    expand: bool = Query(False, description="Aktifkan Query Expansion sinonim"),
    source: str | None = Query(None, description="Filter portal sumber"),
):
    engine: SearchEngine = state["engine"]
    try:
        return engine.search(
            query_text=q,
            model=model,
            top_k=top_k,
            use_expansion=expand,
            source_filter=source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/document/{doc_id}")
async def get_document(doc_id: str):
    engine: SearchEngine = state["engine"]
    doc = engine.get_document_by_id(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Dokumen {doc_id} tidak ditemukan")
    return doc


@app.post("/api/rocchio")
async def run_rocchio(payload: RocchioRequest):
    if not payload.relevant_ids and not payload.non_relevant_ids:
        raise HTTPException(
            status_code=400,
            detail="Pilih minimal 1 dokumen relevan atau tidak relevan untuk Rocchio feedback.",
        )
    rocchio: RocchioFeedback = state["rocchio"]
    return rocchio.refine(
        query_text=payload.query,
        relevant_doc_ids=payload.relevant_ids,
        non_relevant_doc_ids=payload.non_relevant_ids,
        model=payload.model,
        alpha=payload.alpha,
        beta=payload.beta,
        gamma=payload.gamma,
        top_k=payload.top_k,
    )


@app.get("/api/posting-list")
async def posting_list(
    term: str = Query(..., min_length=1),
    index_type: str = Query("custom", pattern="^(custom|baseline)$"),
    limit: int = Query(25, ge=1, le=100),
):
    engine: SearchEngine = state["engine"]
    return engine.get_posting_list(term=term, index_type=index_type, limit=limit)


@app.post("/api/preprocess")
async def inspect_preprocess(payload: PreprocessRequest):
    engine: SearchEngine = state["engine"]
    return engine.preprocessor.preprocess_detailed(payload.text)


@app.get("/api/insights")
async def insights():
    return {
        "duplicate_report": _read_json_safe(REPORTS_DIR / "duplicate_report.json"),
        "preprocessing_examples": _read_json_safe(REPORTS_DIR / "preprocessing_examples.json"),
        "index_stats": _read_json_safe(REPORTS_DIR / "index_stats.json"),
        "synonyms": _read_json_safe(DATA_DIR / "synonyms.json"),
        "query_expansion_proof": _read_json_safe(REPORTS_DIR / "query_expansion_proof.json"),
        "rocchio_demo": _read_json_safe(REPORTS_DIR / "rocchio_demo.json"),
        "evaluation": _read_json_safe(EVAL_DIR / "results_summary.json"),
        "queries": _read_json_safe(EVAL_DIR / "queries.json"),
    }


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if (REPORTS_DIR / "charts").exists():
    app.mount("/charts", StaticFiles(directory=str(REPORTS_DIR / "charts")), name="charts")
elif REPORTS_DIR.exists():
    (REPORTS_DIR / "charts").mkdir(parents=True, exist_ok=True)
    app.mount("/charts", StaticFiles(directory=str(REPORTS_DIR / "charts")), name="charts")
