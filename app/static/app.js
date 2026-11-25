const state = {
  model: "bm25_custom",
  query: "",
  relevantIds: new Set(),
  nonRelevantIds: new Set(),
  insights: null,
  history: JSON.parse(localStorage.getItem("lokacerita_history") || "[]"),
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function esc(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

/* Tab Switching */
$$(".nav-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".nav-tab").forEach((b) => b.classList.remove("active"));
    $$(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
  });
});

$("#brand-home").addEventListener("click", () => {
  $$(".nav-tab")[0].click();
  $("#search-hero").classList.remove("compact");
  $("#results-meta").classList.add("hidden");
  $("#rocchio-summary").classList.add("hidden");
  $("#results-list").innerHTML = "";
  resetFeedback();
});

/* History */
function renderHistory() {
  const bar = $("#history-bar");
  const wrap = $("#history-chips");
  if (!state.history.length) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");
  wrap.innerHTML = state.history
    .map((q) => `<button type="button" class="chip-btn hist-chip" data-q="${esc(q)}">${esc(q)}</button>`)
    .join("");
  $$(".hist-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      $("#search-input").value = btn.dataset.q;
      performSearch(btn.dataset.q);
    });
  });
}

function pushHistory(query) {
  const clean = query.trim();
  if (!clean) return;
  state.history = [clean, ...state.history.filter((x) => x !== clean)].slice(0, 6);
  localStorage.setItem("lokacerita_history", JSON.stringify(state.history));
  renderHistory();
}

/* Model Segmented Control */
$$(".seg-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".seg-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.model = btn.dataset.model;
    if (state.query) performSearch(state.query);
  });
});

$("#toggle-expand").addEventListener("change", () => {
  if (state.query) performSearch(state.query);
});

$("#source-filter").addEventListener("change", () => {
  if (state.query) performSearch(state.query);
});

$$("#quick-queries .chip-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    $("#search-input").value = btn.dataset.q;
    performSearch(btn.dataset.q);
  });
});

$("#search-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $("#search-input").value.trim();
  if (q) performSearch(q);
});

/* Search */
async function performSearch(query) {
  state.query = query;
  pushHistory(query);
  resetFeedback();
  $("#rocchio-summary").classList.add("hidden");
  $("#search-hero").classList.add("compact");

  const expand = $("#toggle-expand").checked;
  const source = $("#source-filter").value;
  const url = `/api/search?q=${encodeURIComponent(query)}&model=${encodeURIComponent(
    state.model
  )}&top_k=10&expand=${expand}&source=${encodeURIComponent(source)}`;

  $("#results-list").innerHTML = `<div class="card muted">Mencari di indeks PyLucene...</div>`;

  const res = await fetch(url);
  const data = await res.json();
  renderResults(data);
}

function renderResults(data, isRocchio = false) {
  const metaEl = $("#results-meta");
  metaEl.classList.remove("hidden");

  const tokensHtml = (data.processed_tokens || [])
    .map((t) => `<span class="token-pill">${esc(t)}</span>`)
    .join("");

  let synHtml = "";
  const added = data.added_synonyms || {};
  const synList = Object.entries(added).flatMap(([k, vals]) =>
    vals.map((v) => `${k} &rarr; ${v}`)
  );
  if (synList.length) {
    synHtml = synList.map((s) => `<span class="token-pill syn">+ ${s}</span>`).join("");
  }

  metaEl.innerHTML = `
    <div>
      <strong>${data.total_hits ?? 0}</strong> dokumen cocok
      <span class="muted">(${data.latency_ms ?? 0} ms &middot; ${esc(data.model_label || data.model)})</span>
    </div>
    <div class="token-badges">
      <span class="muted small">Token Query:</span>
      ${tokensHtml || '<span class="muted small">-</span>'}
      ${synHtml}
    </div>
  `;

  const items = isRocchio ? data.refined_results : data.results;
  if (!items || !items.length) {
    $("#results-list").innerHTML = `<div class="card">Tidak ada cerpen yang cocok untuk query ini. Coba aktifkan <strong>Query Expansion</strong> atau gunakan kata kunci lain.</div>`;
    return;
  }

  $("#results-list").innerHTML = items
    .map((item) => {
      const isRel = state.relevantIds.has(item.doc_id);
      const isNonRel = state.nonRelevantIds.has(item.doc_id);
      let deltaBadge = "";
      if (item.rank_change !== undefined && item.rank_change !== null && item.rank_change !== 0) {
        const cls = item.rank_change > 0 ? "up" : "down";
        const sign = item.rank_change > 0 ? `+${item.rank_change}` : `${item.rank_change}`;
        deltaBadge = `<span class="rank-delta ${cls}">Rank ${sign}</span>`;
      }
      return `
        <article class="result-card">
          <div class="result-top">
            <div class="result-rank-meta">
              <span class="rank-num">#${item.rank}</span>
              <span class="meta-pill">${esc(item.doc_id)}</span>
              <span class="meta-pill">${esc(item.source)}</span>
              <span class="muted small">${esc(item.author)} &middot; ${esc(item.date)} &middot; ${item.word_count} kata</span>
              ${deltaBadge}
            </div>
            <span class="score-pill">Skor: ${item.score}</span>
          </div>
          <h3 class="result-title" data-doc-id="${esc(item.doc_id)}">${esc(item.title)}</h3>
          <p class="result-snippet">${item.snippet_html || esc(item.snippet)}</p>
          <div class="result-footer">
            <div class="result-actions">
              <button type="button" class="btn-ghost read-btn" data-doc-id="${esc(item.doc_id)}">Baca Cerpen</button>
              <a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer" class="btn-ghost">Sumber Asli &nearr;</a>
            </div>
            <div class="result-actions">
              <button type="button" class="fb-btn ${isRel ? "active-rel" : ""}" data-fb="rel" data-doc-id="${esc(item.doc_id)}">Relevan</button>
              <button type="button" class="fb-btn ${isNonRel ? "active-nonrel" : ""}" data-fb="nonrel" data-doc-id="${esc(item.doc_id)}">Tidak Relevan</button>
            </div>
          </div>
        </article>
      `;
    })
    .join("");

  $$(".result-title, .read-btn").forEach((el) => {
    el.addEventListener("click", () => openReaderModal(el.dataset.docId));
  });

  $$(".fb-btn").forEach((btn) => {
    btn.addEventListener("click", () => toggleFeedback(btn.dataset.docId, btn.dataset.fb));
  });
}

/* Rocchio Feedback */
function toggleFeedback(docId, kind) {
  if (kind === "rel") {
    state.nonRelevantIds.delete(docId);
    if (state.relevantIds.has(docId)) state.relevantIds.delete(docId);
    else state.relevantIds.add(docId);
  } else {
    state.relevantIds.delete(docId);
    if (state.nonRelevantIds.has(docId)) state.nonRelevantIds.delete(docId);
    else state.nonRelevantIds.add(docId);
  }
  updateRocchioBar();
  // Refresh button classes without resetting results
  $$(`.fb-btn[data-doc-id="${docId}"]`).forEach((b) => {
    b.classList.remove("active-rel", "active-nonrel");
    if (b.dataset.fb === "rel" && state.relevantIds.has(docId)) b.classList.add("active-rel");
    if (b.dataset.fb === "nonrel" && state.nonRelevantIds.has(docId)) b.classList.add("active-nonrel");
  });
}

function updateRocchioBar() {
  const total = state.relevantIds.size + state.nonRelevantIds.size;
  $("#rel-count").textContent = `${state.relevantIds.size} Relevan`;
  $("#nonrel-count").textContent = `${state.nonRelevantIds.size} Tidak Relevan`;
  if (total > 0) $("#rocchio-bar").classList.remove("hidden");
  else $("#rocchio-bar").classList.add("hidden");
}

function resetFeedback() {
  state.relevantIds.clear();
  state.nonRelevantIds.clear();
  updateRocchioBar();
}

$("#btn-rocchio-reset").addEventListener("click", () => {
  resetFeedback();
  $$(".fb-btn").forEach((b) => b.classList.remove("active-rel", "active-nonrel"));
});

$("#btn-rocchio-run").addEventListener("click", async () => {
  if (!state.query) return;
  const payload = {
    query: state.query,
    model: state.model === "bm25_baseline" ? "bm25_custom" : state.model,
    relevant_ids: Array.from(state.relevantIds),
    non_relevant_ids: Array.from(state.nonRelevantIds),
    alpha: parseFloat($("#rocchio-alpha").value || "1.0"),
    beta: parseFloat($("#rocchio-beta").value || "0.75"),
    gamma: parseFloat($("#rocchio-gamma").value || "0.15"),
    top_k: 10,
  };
  const res = await fetch("/api/rocchio", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  const sumEl = $("#rocchio-summary");
  sumEl.classList.remove("hidden");
  const weightsHtml = (data.weighted_query_terms || [])
    .map(
      (t) =>
        `<span class="token-pill ${t.from_original_query ? "" : "syn"}">${esc(t.term)}: <strong>${t.weight}</strong></span>`
    )
    .join("");
  sumEl.innerHTML = `
    <div style="margin-bottom:6px;"><strong>Query Term Berbobot Baru (Rocchio &alpha;=${data.parameters.alpha}, &beta;=${data.parameters.beta}, &gamma;=${data.parameters.gamma}):</strong></div>
    <div class="token-badges">${weightsHtml}</div>
  `;
  renderResults(
    {
      ...data,
      model_label: `${data.model} (Rocchio Refined)`,
      processed_tokens: data.original_query_terms,
    },
    true
  );
  window.scrollTo({ top: 0, behavior: "smooth" });
});

/* Modal Reader */
async function openReaderModal(docId) {
  const res = await fetch(`/api/document/${encodeURIComponent(docId)}`);
  if (!res.ok) return;
  const doc = await res.json();
  $("#modal-source").textContent = `${doc.doc_id} · ${doc.source}`;
  $("#modal-title").textContent = doc.title;
  $("#modal-meta").textContent = `Penulis: ${doc.author} · Tanggal: ${doc.date}`;
  $("#modal-body").textContent = doc.content_raw;
  $("#modal-link").href = doc.url;
  $("#reader-modal").classList.remove("hidden");
}

$("#modal-close").addEventListener("click", () => $("#reader-modal").classList.add("hidden"));
$("#modal-backdrop").addEventListener("click", () => $("#reader-modal").classList.add("hidden"));

/* Preprocessing Live Tester */
$("#btn-run-prep").addEventListener("click", async () => {
  const text = $("#prep-input").value.trim();
  if (!text) return;
  const res = await fetch("/api/preprocess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const d = await res.json();
  const out = $("#prep-output");
  out.classList.remove("hidden");
  out.innerHTML = `
    <div><div class="prep-stage-label">1. Domain Cleaning & Case Folding</div><div><code>${esc(d.cleaned_text)}</code></div></div>
    <div><div class="prep-stage-label">2. Tokenisasi (${d.tokens.length} token)</div><div>${d.tokens.map((t) => `<span class="token-pill">${esc(t)}</span>`).join(" ")}</div></div>
    <div><div class="prep-stage-label">3. Stopword + Custom Domain Stopwords (${d.after_stopwords.length} token)</div><div>${d.after_stopwords.map((t) => `<span class="token-pill">${esc(t)}</span>`).join(" ")}</div></div>
    <div><div class="prep-stage-label">4. Stemming Sastrawi Final (${d.stemmed_tokens.length} term)</div><div><code>${esc(d.final_text)}</code></div></div>
  `;
});

/* Posting List Inspector */
async function loadPostingList(term) {
  const idxType = $("#posting-index-type").value;
  const res = await fetch(`/api/posting-list?term=${encodeURIComponent(term)}&index_type=${idxType}&limit=25`);
  const d = await res.json();
  const rows = (d.postings || [])
    .map(
      (p) => `
      <tr>
        <td><code>${esc(p.doc_id)}</code></td>
        <td>${esc(p.title)}</td>
        <td>${esc(p.source)}</td>
        <td><strong>${p.tf}</strong></td>
        <td><code>[${(p.positions || []).join(", ")}${p.tf > 8 ? ", ..." : ""}]</code></td>
      </tr>
    `
    )
    .join("");

  $("#posting-result").innerHTML = `
    <div style="margin-bottom:12px; display:flex; gap:12px; flex-wrap:wrap;">
      <span class="meta-pill">Term Input: <strong>${esc(d.input_term)}</strong></span>
      <span class="meta-pill">Term Terindeks: <strong>${esc(d.resolved_term)}</strong></span>
      <span class="meta-pill">Field: <code>${esc(d.field)}</code></span>
      <span class="meta-pill">Document Frequency (df): <strong>${d.df}</strong></span>
      <span class="meta-pill">Total Term Frequency: <strong>${d.total_tf}</strong></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Doc ID</th><th>Judul Cerpen</th><th>Sumber</th><th>TF</th><th>Posisi Awal</th></tr>
        </thead>
        <tbody>${rows || '<tr><td colspan="5" class="muted">Term tidak ditemukan di indeks.</td></tr>'}</tbody>
      </table>
    </div>
  `;
}

$("#posting-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const term = $("#posting-term").value.trim();
  if (term) loadPostingList(term);
});

$$(".posting-chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    $("#posting-term").value = btn.dataset.term;
    loadPostingList(btn.dataset.term);
  });
});

/* Load Health & Insights */
async function initDashboard() {
  renderHistory();
  try {
    const hRes = await fetch("/api/health");
    const h = await hRes.json();
    $("#corpus-badge").textContent = `${h.custom_doc_count} Cerpen Terindeks`;
  } catch {
    $("#corpus-badge").textContent = "Offline";
  }

  try {
    const iRes = await fetch("/api/insights");
    const ins = await iRes.json();
    state.insights = ins;
    renderInsights(ins);
  } catch (e) {
    console.error("Insights load failed:", e);
  }
  loadPostingList("hujan");
}

function renderInsights(ins) {
  const prep = ins.preprocessing_examples;
  if (prep) {
    $("#prep-stats-grid").innerHTML = `
      <div class="card">
        <h3>Statistik Reduksi Preprocessing</h3>
        <p class="muted">Korpus: <strong>${prep.total_documents}</strong> cerpen unik</p>
        <p>Total Token: <strong>${prep.total_raw_tokens.toLocaleString()}</strong> &rarr; <strong>${prep.total_clean_tokens.toLocaleString()}</strong> (Reduksi <strong>${prep.token_reduction_pct}%</strong>)</p>
        <p>Ukuran Kosakata: <strong>${prep.raw_vocabulary_size.toLocaleString()}</strong> &rarr; <strong>${prep.clean_vocabulary_size.toLocaleString()}</strong> (Reduksi <strong>${prep.vocab_reduction_pct}%</strong>)</p>
      </div>
      <div class="card">
        <h3>Custom Domain Stopwords (${prep.custom_domain_stopwords_count} kata)</h3>
        <div class="token-badges">
          ${(prep.custom_domain_stopwords_sample || []).map((w) => `<span class="token-pill">${esc(w)}</span>`).join("")}
        </div>
      </div>
    `;

    $("#prep-examples").innerHTML = (prep.examples || [])
      .slice(0, 3)
      .map(
        (ex) => `
        <div class="example-box">
          <div class="small muted"><strong>${esc(ex.doc_id)}</strong> &middot; ${esc(ex.title)} (${esc(ex.source)})</div>
          <p class="small"><strong>Sebelum:</strong> ${esc(ex.before_raw)}</p>
          <p class="small"><strong>Sesudah (Stemmed):</strong> <code>${esc(ex.after_stemmed_final)}</code></p>
        </div>
      `
      )
      .join("");
  }

  const syn = ins.synonyms;
  if (syn && syn.pairs) {
    const renderSyn = (filterText = "") => {
      const f = filterText.toLowerCase();
      const filtered = syn.pairs.filter(
        (p) => p.term.includes(f) || p.synonyms.some((s) => s.includes(f))
      );
      $("#synonyms-grid").innerHTML = filtered
        .map(
          (p) => `
          <div class="syn-card">
            <div class="syn-root">${esc(p.term)}</div>
            <div class="small muted">${p.synonyms.map((s) => esc(s)).join(", ")}</div>
          </div>
        `
        )
        .join("");
    };
    renderSyn();
    $("#synonym-filter").addEventListener("input", (e) => renderSyn(e.target.value));
  }

  const qe = ins.query_expansion_proof;
  if (qe && qe.proof_queries) {
    $("#qe-proofs").innerHTML = qe.proof_queries
      .map(
        (q) => `
        <div class="example-box">
          <div><strong>Query:</strong> "${esc(q.raw_query)}"</div>
          <div class="small"><strong>Sebelum:</strong> <code>${q.tokens_before.join(" ")}</code> (${q.total_hits_before} hits)</div>
          <div class="small"><strong>Sesudah:</strong> <code>${q.tokens_after.join(" ")}</code> (${q.total_hits_after} hits)</div>
        </div>
      `
      )
      .join("");
  }

  const ev = ins.evaluation;
  if (ev && ev.summary) {
    const best = ev.summary[0];
    $("#eval-kpis").innerHTML = ev.summary
      .map(
        (row) => `
        <div class="kpi-card">
          <div class="kpi-label">${esc(row.label)}</div>
          <div class="kpi-value">${row.map.toFixed(4)}</div>
          <div class="kpi-sub">MAP &middot; P@10: ${row.precision_at_10.toFixed(4)} &middot; F1: ${row.f1.toFixed(4)}</div>
        </div>
      `
      )
      .join("");

    $("#eval-table-wrap").innerHTML = `
      <table>
        <thead>
          <tr><th>Konfigurasi Model</th><th>Query</th><th>Precision@10</th><th>Recall</th><th>F1-Score</th><th>MAP</th></tr>
        </thead>
        <tbody>
          ${ev.summary
            .map(
              (r) => `
              <tr>
                <td><strong>${esc(r.label)}</strong></td>
                <td>${r.num_queries}</td>
                <td>${r.precision_at_10.toFixed(4)}</td>
                <td>${r.recall.toFixed(4)}</td>
                <td>${r.f1.toFixed(4)}</td>
                <td><strong>${r.map.toFixed(4)}</strong></td>
              </tr>
            `
            )
            .join("")}
        </tbody>
      </table>
    `;
  }

  const dup = ins.duplicate_report;
  if (dup) {
    $("#dup-audit-box").innerHTML = `
      <p>Total Dokumen Di-crawl: <strong>${dup.total_crawled}</strong></p>
      <p>Duplikat URL Eksak: <strong>${dup.exact_url_duplicates}</strong> &middot; Hash SHA-256: <strong>${dup.exact_hash_duplicates}</strong> &middot; Near-Duplicate (&ge;95%): <strong>${dup.near_duplicates_gt_95}</strong></p>
      <p>Total Dokumen Unik Bersih: <strong>${dup.total_unique_documents}</strong> &middot; Kemiripan Maksimal Antar Dokumen: <strong>${(dup.max_similarity_among_unique * 100).toFixed(2)}%</strong> (&lt; 95%)</p>
    `;
  }

  const roc = ins.rocchio_demo;
  if (roc && roc.demos) {
    $("#rocchio-demo-box").innerHTML = roc.demos
      .map(
        (d) => `
        <div class="example-box" style="margin-bottom:10px;">
          <div><strong>Query Uji:</strong> "${esc(d.query)}" (&alpha;=${d.parameters.alpha}, &beta;=${d.parameters.beta}, &gamma;=${d.parameters.gamma})</div>
          <div class="small muted">Relevan: ${d.relevant_doc_ids.join(", ")} | Tidak Relevan: ${d.non_relevant_doc_ids.join(", ")}</div>
          <div class="token-badges" style="margin-top:8px;">
            ${d.weighted_query_terms.slice(0, 8).map((t) => `<span class="token-pill ${t.from_original_query ? "" : "syn"}">${esc(t.term)}: ${t.weight}</span>`).join("")}
          </div>
        </div>
      `
      )
      .join("");
  }
}

initDashboard();
