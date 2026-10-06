/* Renders server-built Plotly figures; drives the report builder's live preview. */
(() => {
  const config = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d"] };
  const draw = (el, fig) => window.Plotly && Plotly.newPlot(el, fig.data, fig.layout, config);

  // Saved report page
  document.querySelectorAll("[data-figure]").forEach((el) => {
    draw(el, JSON.parse(document.getElementById(el.dataset.figure).textContent));
  });

  // Builder preview
  const form = document.getElementById("reportForm");
  if (!form) return;
  const area = document.getElementById("previewArea");
  const btn = document.getElementById("previewBtn");
  const esc = window.MB.esc;
  const field = (n) => form.elements[n].value;

  const table = (cols, rows) => `
    <div class="table-responsive border rounded-3 mt-3" style="max-height:320px">
      <table class="table table-x table-sm mb-0"><thead class="sticky-top"><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${rows.slice(0, 200).map((r) => `<tr>${r.map((v) => `<td>${v === null ? "—" : esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table>
    </div>`;

  async function preview() {
    if (!field("sql").trim()) return window.MB.toast("Write a query first.", "error");
    btn.disabled = true;
    area.innerHTML = `<div class="py-5 text-center"><div class="spinner-ring mx-auto"></div></div>`;
    try {
      const r = await fetch("/reports/preview/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": window.MB.csrf() },
        body: JSON.stringify({
          sql: field("sql"), chart_type: field("chart_type"), x_column: field("x_column"),
          y_columns: field("y_columns"), series_column: field("series_column"),
          doctor_id: document.getElementById("previewAs").value || null,
        }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || "Preview failed.");
      document.getElementById("colList").innerHTML = data.columns.map((c) => `<option value="${esc(c)}">`).join("");
      const out = data.output;
      const meta = `<div class="small text-muted mb-2">${data.rows.length} row(s)${data.truncated ? " (truncated)" : ""} · ${data.elapsed_ms} ms · columns: ${data.columns.map(esc).join(", ")}</div>`;
      if (out.kind === "number") {
        area.innerHTML = `${meta}<div class="text-center py-4"><div class="small-caps mb-2">${esc(out.label)}</div><div style="font-size:3rem;font-weight:800;color:var(--ink)">${esc(out.value ?? "—")}</div></div>${table(data.columns, data.rows)}`;
      } else if (out.kind === "plot") {
        area.innerHTML = `${meta}<div id="previewChart" style="min-height:380px"></div>${table(data.columns, data.rows)}`;
        draw(document.getElementById("previewChart"), out.figure);
      } else {
        area.innerHTML = meta + (data.rows.length ? table(data.columns, data.rows) : `<p class="small text-muted">The query returned no rows.</p>`);
      }
    } catch (err) {
      area.innerHTML = `<div class="alert alert-danger small mb-0"><i class="bi bi-exclamation-octagon me-1"></i>${esc(err.message)}</div>`;
    } finally {
      btn.disabled = false;
    }
  }

  btn.addEventListener("click", preview);
  form.elements.sql.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); preview(); } });
  ["chart_type"].forEach((n) => form.elements[n].addEventListener("change", () => field("sql").trim() && preview()));
  if (field("sql").trim()) preview();
})();
