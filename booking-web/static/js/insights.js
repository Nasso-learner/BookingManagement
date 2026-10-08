/* Insights dashboard: ECharts visuals, cross-filtering, slicers, table/CSV/PNG/focus per visual.
   Data comes from /insights/data/ (same-origin, cookie session) -> booking-api -> ClickHouse. */
(() => {
  const root = document.getElementById("insights");
  if (!root || !window.echarts) return;
  const isAdmin = root.dataset.role === "ADMIN";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = window.MB.esc;

  // ---- Design tokens (validated palette; statuses keep the same colour on every visual) ----
  const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
  const STATUS = {  // stack order, validated adjacent-pair separation
    COMPLETED: ["Completed", "#1baf7a"], CONFIRMED: ["Confirmed", "#2a78d6"], PENDING: ["Pending", "#eda100"],
    NO_SHOW: ["No-show", "#e87ba4"], RESCHEDULED: ["Rescheduled", "#4a3aa7"], CANCELLED: ["Cancelled", "#e34948"],
  };
  const LABELS = { WEB: "Web", ADMIN: "Admin", FEMALE: "Female", MALE: "Male", OTHER: "Other", UNKNOWN: "Not specified" };
  const INK = "#0f172a", INK2 = "#334155", MUTED = "#64748b", GRID = "#e6ebf2";
  const SEQ = ["#eef4fc", "#a9c9ef", "#2a78d6", "#123e75"];  // sequential: one hue, light -> dark
  const FONT = '"Plus Jakarta Sans", system-ui, sans-serif';
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  const num = new Intl.NumberFormat("en-IN");
  const money = (v) => "₹" + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(v || 0);
  const moneyShort = (v) => "₹" + new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(v || 0);
  const isoLocal = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

  // ---- State (mirrored in the URL so a refresh keeps the view) ----
  const qs = new URLSearchParams(location.search);
  const state = {
    preset: qs.get("preset") ?? (qs.get("date_from") ? "" : "90"),
    date_from: qs.get("date_from") || "", date_to: qs.get("date_to") || "",
    department: qs.get("department") || "", doctor: isAdmin ? qs.get("doctor") || "" : "", status: qs.get("status") || "",
  };
  const applyPreset = (p) => {
    const to = new Date(), from = new Date();
    if (p === "ytd") from.setMonth(0, 1); else from.setDate(to.getDate() - (Number(p) - 1));
    Object.assign(state, { preset: p, date_from: isoLocal(from), date_to: isoLocal(to) });
  };
  if (state.preset) applyPreset(state.preset);

  // ---- Charts ----
  const cards = $$(".ix-viz");
  const charts = {}, tables = {};
  cards.forEach((c) => { charts[c.dataset.viz] = echarts.init($(".ix-chart", c), null, { renderer: "canvas" }); });
  const ro = new ResizeObserver((entries) => entries.forEach((e) => echarts.getInstanceByDom(e.target)?.resize()));
  $$(".ix-chart").forEach((el) => ro.observe(el));

  const tooltip = (extra = {}) => ({
    backgroundColor: "#fff", borderColor: GRID, borderWidth: 1, padding: [8, 12], confine: true,
    textStyle: { color: INK, fontFamily: FONT, fontSize: 12 },
    extraCssText: "box-shadow:0 10px 28px -10px rgba(15,23,42,.25);border-radius:10px;", ...extra,
  });
  const base = (o) => ({
    textStyle: { fontFamily: FONT, color: INK2 }, animationDuration: 350, animationDurationUpdate: 300,
    grid: { left: 8, right: 18, top: 34, bottom: 8, containLabel: true }, ...o,
  });
  const catAxis = (data, o = {}) => ({ type: "category", data, axisLine: { lineStyle: { color: GRID } }, axisTick: { show: false },
    axisLabel: { color: MUTED, fontSize: 11, hideOverlap: true }, ...o });
  const valAxis = (o = {}) => ({ type: "value", splitLine: { lineStyle: { color: GRID } }, axisLabel: { color: MUTED, fontSize: 11 }, ...o });
  const legend = (o = {}) => ({ top: 0, left: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, itemGap: 14,
    textStyle: { color: INK2, fontSize: 12 }, ...o });
  const dim = (selected, key) => (selected && String(selected) !== String(key) ? 0.3 : 1);

  function setViz(id, option, table, empty) {
    const card = $(`.ix-viz[data-viz="${id}"]`);
    if (!card) return;
    tables[id] = table;
    $(".ix-empty", card).hidden = !empty;
    charts[id].setOption(base(option), { notMerge: true });
    if (!$(".ix-table", card).hidden) renderTable(card);
  }

  const fmtBucket = (b, grain) => {
    const d = new Date(`${b}T00:00`);
    if (grain === "month") return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
    const s = d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
    return grain === "week" ? `Wk ${s}` : s;
  };

  // ---- Visuals ----
  function renderTrend(d) {
    const labels = d.trend.buckets.map((b) => fmtBucket(b, d.granularity));
    const keys = Object.keys(STATUS).filter((k) => d.trend.series[k]);
    const series = keys.map((k) => ({
      name: STATUS[k][0], type: "bar", stack: "s", data: d.trend.series[k], barMaxWidth: 28,
      itemStyle: { color: STATUS[k][1], borderColor: "#fff", borderWidth: 1, opacity: dim(state.status, k) },
      emphasis: { focus: "series" },
    }));
    const zoom = labels.length > 31;
    setViz("trend", {
      legend: legend(), tooltip: tooltip({ trigger: "axis", axisPointer: { type: "shadow" } }),
      grid: { left: 8, right: 18, top: 34, bottom: zoom ? 44 : 8, containLabel: true },
      xAxis: catAxis(labels), yAxis: valAxis({ minInterval: 1 }), series,
      dataZoom: zoom ? [{ type: "inside" }, { type: "slider", height: 16, bottom: 6, borderColor: GRID, fillerColor: "rgba(42,120,214,.12)",
        handleSize: 18, showDetail: false, brushSelect: false }] : [],
    }, {
      columns: ["Period", ...keys.map((k) => STATUS[k][0]), "Total"],
      rows: d.trend.buckets.map((b, i) => [b, ...keys.map((k) => d.trend.series[k][i]),
        keys.reduce((s, k) => s + d.trend.series[k][i], 0)]),
    }, !keys.length);
    charts.trend.off("click").on("click", (p) => toggle("status", keyOfStatus(p.seriesName)));
  }

  const keyOfStatus = (label) => Object.keys(STATUS).find((k) => STATUS[k][0] === label);

  function donut(id, rows, colorOf, labelOf, keyOf, filterKey, valueName) {
    const total = rows.reduce((s, r) => s + r.n, 0);
    setViz(id, {
      tooltip: tooltip({ trigger: "item", formatter: (p) => `<b>${esc(p.name)}</b><br>${num.format(p.value)} ${valueName} · ${p.percent}%` }),
      legend: legend({ top: "auto", bottom: 0, left: "center" }),
      title: { text: num.format(total), subtext: valueName, left: "center", top: "38%",
        textStyle: { fontSize: 22, fontWeight: 800, color: INK, fontFamily: FONT }, subtextStyle: { color: MUTED, fontSize: 11 } },
      series: [{
        type: "pie", radius: ["52%", "74%"], center: ["50%", "45%"], avoidLabelOverlap: true,
        itemStyle: { borderColor: "#fff", borderWidth: 2, borderRadius: 4 },
        label: { show: rows.length <= 6, formatter: "{d}%", color: INK2, fontSize: 11 }, labelLine: { length: 6, length2: 6 },
        data: rows.map((r, i) => ({ name: labelOf(r), value: r.n, key: keyOf(r),
          itemStyle: { color: colorOf(r, i), opacity: filterKey ? dim(state[filterKey], keyOf(r)) : 1 } })),
      }],
    }, { columns: ["Category", valueName, "Share %"], rows: rows.map((r) => [labelOf(r), r.n, total ? +(100 * r.n / total).toFixed(1) : 0]) }, !total);
    charts[id].off("click");
    if (filterKey) charts[id].on("click", (p) => toggle(filterKey, p.data.key));
  }

  function hbar(id, items, { label, value, key, filterKey, valueFmt = num.format, tip, color = PALETTE[0], max, table }) {
    const rows = [...items].reverse();  // ECharts draws category axis bottom-up; keep largest on top
    setViz(id, {
      tooltip: tooltip({ trigger: "item", formatter: (p) => tip(items[items.length - 1 - p.dataIndex]) }),
      grid: { left: 8, right: 44, top: 8, bottom: 8, containLabel: true },
      xAxis: valAxis({ max, axisLabel: { color: MUTED, fontSize: 11, formatter: (v) => valueFmt(v) } }),
      yAxis: catAxis(rows.map(label), { axisLabel: { color: INK2, fontSize: 11, width: 130, overflow: "truncate" } }),
      series: [{ type: "bar", barMaxWidth: 18, data: rows.map((r) => ({ value: value(r), key: key(r),
        itemStyle: { color, borderRadius: [0, 4, 4, 0], opacity: filterKey ? dim(state[filterKey], key(r)) : 1 } })),
        label: { show: true, position: "right", color: INK2, fontSize: 11, formatter: (p) => valueFmt(p.value) } }],
    }, table, !items.length);
    charts[id].off("click");
    if (filterKey) charts[id].on("click", (p) => toggle(filterKey, p.data.key));
  }

  function renderAll(d) {
    renderKpis(d);
    renderTrend(d);

    const statusRows = Object.keys(STATUS).map((k) => d.status_mix.find((r) => r.status === k)).filter(Boolean);
    donut("status", statusRows, (r) => STATUS[r.status][1], (r) => STATUS[r.status][0], (r) => r.status, "status", "appointments");

    const labels = d.trend.buckets.map((b) => fmtBucket(b, d.granularity));
    const totalRev = d.trend.revenue.reduce((a, b) => a + b, 0);
    setViz("revenue", {
      tooltip: tooltip({ trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: money }),
      xAxis: catAxis(labels), yAxis: valAxis({ axisLabel: { color: MUTED, fontSize: 11, formatter: moneyShort } }),
      grid: { left: 8, right: 18, top: 12, bottom: 8, containLabel: true },
      series: [{ name: "Revenue", type: "bar", barMaxWidth: 24, data: d.trend.revenue,
        itemStyle: { color: PALETTE[0], borderRadius: [4, 4, 0, 0] },
        markLine: totalRev ? { symbol: "none", lineStyle: { color: MUTED, type: "dashed" }, label: { color: MUTED, position: "insideEndTop", formatter: (p) => `avg ${moneyShort(p.value)}` },
          data: [{ type: "average" }] } : undefined }],
    }, { columns: ["Period", "Revenue"], rows: d.trend.buckets.map((b, i) => [b, d.trend.revenue[i]]) }, !totalRev);

    hbar("departments", d.departments, {
      label: (r) => r.department_name, value: (r) => r.total, key: (r) => r.department_name, filterKey: "department",
      tip: (r) => `<b>${esc(r.department_name)}</b><br>${num.format(r.total)} appointments<br>${num.format(r.completed)} completed · ${money(r.revenue)}`,
      table: { columns: ["Department", "Appointments", "Completed", "Revenue"],
        rows: d.departments.map((r) => [r.department_name, r.total, r.completed, r.revenue]) },
    });

    if (isAdmin && d.doctors) {
      hbar("doctors", d.doctors.slice(0, 10), {
        label: (r) => r.doctor, value: (r) => r.total, key: (r) => r.doctor_id, filterKey: "doctor",
        tip: (r) => `<b>${esc(r.doctor)}</b> · ${esc(r.department)}<br>${num.format(r.total)} appointments · ${num.format(r.completed)} completed<br>` +
          `No-show ${r.no_show_pct ?? 0}% · ${money(r.revenue)}`,
        table: { columns: ["Doctor", "Department", "Appointments", "Completed", "Cancelled", "No-show", "No-show %", "Revenue"],
          rows: d.doctors.map((r) => [r.doctor, r.department, r.total, r.completed, r.cancelled, r.no_show, r.no_show_pct ?? 0, r.revenue]) },
      });
    }

    const maxPct = Math.max(100, ...d.utilisation.map((r) => r.pct || 0));
    hbar("utilisation", d.utilisation, {
      label: (r) => r.doctor_name, value: (r) => r.pct || 0, key: (r) => r.doctor_id, filterKey: isAdmin ? "doctor" : null,
      valueFmt: (v) => `${v}%`, max: Math.ceil(maxPct / 10) * 10,
      tip: (r) => `<b>${esc(r.doctor_name)}</b><br>${num.format(r.booked)} of ${num.format(r.capacity)} slots booked (${r.pct || 0}%)`,
      table: { columns: ["Doctor", "Booked", "Published slots", "Utilisation %"],
        rows: d.utilisation.map((r) => [r.doctor_name, r.booked, r.capacity, r.pct || 0]) },
    });

    // Heatmap: weekday x hour (sequential single-hue ramp)
    const hours = d.heatmap.map((c) => c[0]);
    const h0 = Math.min(8, ...hours), h1 = Math.max(19, ...hours);
    const hourLabels = Array.from({ length: h1 - h0 + 1 }, (_, i) => `${String(h0 + i).padStart(2, "0")}:00`);
    const maxN = Math.max(1, ...d.heatmap.map((c) => c[2]));
    setViz("heatmap", {
      tooltip: tooltip({ formatter: (p) => `<b>${DAYS[p.value[1]]} ${hourLabels[p.value[0]]}</b><br>${num.format(p.value[2])} appointments` }),
      grid: { left: 8, right: 12, top: 8, bottom: 44, containLabel: true },
      xAxis: catAxis(hourLabels, { splitArea: { show: false } }), yAxis: catAxis(DAYS, { inverse: true }),
      visualMap: { min: 0, max: maxN, calculable: false, orient: "horizontal", left: "center", bottom: 0, itemWidth: 10, itemHeight: 120,
        inRange: { color: SEQ }, textStyle: { color: MUTED, fontSize: 11 } },
      series: [{ type: "heatmap", data: d.heatmap.map(([h, w, n]) => [h - h0, w, n]),
        label: { show: d.heatmap.length <= 120, color: INK, fontSize: 10, formatter: (p) => (p.value[2] ? p.value[2] : "") },
        itemStyle: { borderColor: "#fff", borderWidth: 2, borderRadius: 4 }, emphasis: { itemStyle: { borderColor: INK, borderWidth: 1 } } }],
    }, { columns: ["Weekday", "Hour", "Appointments"], rows: d.heatmap.map(([h, w, n]) => [DAYS[w], `${String(h).padStart(2, "0")}:00`, n]) },
    !d.heatmap.length);

    setViz("lead", {
      tooltip: tooltip({ trigger: "axis", axisPointer: { type: "shadow" } }),
      grid: { left: 8, right: 12, top: 12, bottom: 8, containLabel: true },
      xAxis: catAxis(d.lead_time.map((r) => r.bucket), { axisLabel: { color: MUTED, fontSize: 10, interval: 0 } }), yAxis: valAxis({ minInterval: 1 }),
      series: [{ name: "Appointments", type: "bar", barMaxWidth: 36, data: d.lead_time.map((r) => r.n),
        itemStyle: { color: PALETTE[0], borderRadius: [4, 4, 0, 0] }, label: { show: true, position: "top", color: INK2, fontSize: 11 } }],
    }, { columns: ["Lead time", "Appointments"], rows: d.lead_time.map((r) => [r.bucket, r.n]) }, !d.lead_time.some((r) => r.n));

    donut("source", d.source_mix, (r, i) => PALETTE[i], (r) => LABELS[r.booking_source] || r.booking_source, (r) => r.booking_source, null, "appointments");
    const genderOrder = ["FEMALE", "MALE", "OTHER", "UNKNOWN"];
    const genders = genderOrder.map((g) => d.gender_mix.find((r) => r.gender === g)).filter(Boolean);
    donut("gender", genders, (r) => PALETTE[genderOrder.indexOf(r.gender)], (r) => LABELS[r.gender] || r.gender, (r) => r.gender, null, "patients");
  }

  // ---- KPI tiles ----
  function renderKpis(d) {
    const k = d.kpis;
    const rate = (a, b) => (b ? (100 * a) / b : null);
    const tiles = {
      total: { v: k.total, p: k.p_total, fmt: num.format, good: "up" },
      completion: { v: rate(k.completed, k.completed + k.no_show + k.cancelled), p: rate(k.p_completed, k.p_completed + k.p_no_show + k.p_cancelled),
        fmt: (x) => `${x.toFixed(1)}%`, good: "up", pts: true },
      no_show: { v: rate(k.no_show, k.completed + k.no_show), p: rate(k.p_no_show, k.p_completed + k.p_no_show), fmt: (x) => `${x.toFixed(1)}%`, good: "down", pts: true },
      revenue: { v: k.revenue, p: k.p_revenue, fmt: money, good: "up" },
      patients: { v: k.patients, p: k.p_patients, fmt: num.format, good: "up" },
      lead: { v: k.avg_lead_days, p: k.p_avg_lead_days, fmt: (x) => `${x.toFixed(1)} days`, good: null, days: true },
    };
    Object.entries(tiles).forEach(([id, t]) => {
      const el = $(`.ix-kpi[data-kpi="${id}"]`);
      $(".ix-kpi-value", el).textContent = t.v == null ? "–" : t.fmt(t.v);
      const delta = $(".ix-kpi-delta", el);
      delta.className = "ix-kpi-delta";
      if (t.v == null || t.p == null || (!t.pts && !t.days && !t.p)) {
        delta.innerHTML = `<span class="vs">No data for previous ${d.period_days} days</span>`;
        return;
      }
      const diff = t.v - t.p;
      const text = t.pts ? `${Math.abs(diff).toFixed(1)} pts` : t.days ? `${Math.abs(diff).toFixed(1)} days` : `${Math.abs((100 * diff) / t.p).toFixed(1)}%`;
      const dir = diff > 0 ? "up" : diff < 0 ? "down" : "flat";
      if (t.good && dir !== "flat") delta.classList.add(dir === t.good ? "good" : "bad");
      const icon = dir === "up" ? "bi-arrow-up-right" : dir === "down" ? "bi-arrow-down-right" : "bi-dash";
      delta.innerHTML = `<i class="bi ${icon}" aria-hidden="true"></i>${dir === "flat" ? "No change" : (dir === "up" ? "Up " : "Down ") + text}` +
        ` <span class="vs">vs previous ${d.period_days} days</span>`;
    });
  }

  // ---- Slicers, chips, URL ----
  function fillSelect(sel, options, current, all) {
    if (!sel) return;
    sel.innerHTML = `<option value="">${all}</option>` + options.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("");
    sel.value = current;
  }
  function syncControls(d) {
    $$("#ixPresets a").forEach((a) => a.classList.toggle("active", a.dataset.preset === state.preset));
    $("#ixFrom").value = state.date_from; $("#ixTo").value = state.date_to;
    if (d) {
      fillSelect($("#ixDepartment"), d.options.departments.map((x) => [x, x]), state.department, "All departments");
      fillSelect($("#ixDoctor"), (d.options.doctors || []).map((x) => [x.doctor_id, x.doctor_name]), state.doctor, "All doctors");
      fillSelect($("#ixStatus"), d.options.statuses.map((s) => [s, STATUS[s][0]]), state.status, "All statuses");
      const docName = (d.options.doctors || []).find((x) => String(x.doctor_id) === String(state.doctor))?.doctor_name;
      const chips = [
        state.department && ["department", `Department: ${state.department}`],
        state.doctor && ["doctor", `Doctor: ${docName || state.doctor}`],
        state.status && ["status", `Status: ${STATUS[state.status]?.[0] || state.status}`],
      ].filter(Boolean);
      $("#ixChips").innerHTML = chips.map(([k, l]) =>
        `<span class="ix-chip">${esc(l)}<button type="button" data-clear="${k}" aria-label="Remove filter ${esc(l)}"><i class="bi bi-x"></i></button></span>`).join("");
    }
  }
  function syncUrl() {
    const p = new URLSearchParams();
    if (state.preset) p.set("preset", state.preset); else { p.set("date_from", state.date_from); p.set("date_to", state.date_to); }
    ["department", "doctor", "status"].forEach((k) => state[k] && p.set(k, state[k]));
    history.replaceState(null, "", `${location.pathname}?${p}`);
  }
  function toggle(key, value) {
    if (!key || value == null) return;
    state[key] = String(state[key]) === String(value) ? "" : String(value);
    load();
  }

  // ---- Data loading ----
  let ctrl = null, first = true;
  async function load() {
    ctrl?.abort();
    ctrl = new AbortController();
    syncUrl(); syncControls();
    root.classList.add("is-refreshing");
    if (first) cards.forEach((c) => c.classList.add("is-loading"));
    const p = new URLSearchParams();
    ["date_from", "date_to", "department", "doctor", "status"].forEach((k) => state[k] && p.set(k, state[k]));
    try {
      const r = await fetch(`/insights/data/?${p}`, { signal: ctrl.signal, headers: { Accept: "application/json" } });
      if (r.redirected || !(r.headers.get("content-type") || "").includes("json")) {
        location.href = `/login/?next=${encodeURIComponent(location.pathname + location.search)}`; return;
      }
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Could not load insights.");
      $("#ixError").classList.add("d-none");
      syncControls(d);
      renderAll(d);
      const t = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      $("#ixMeta").innerHTML = `<i class="bi bi-lightning-charge-fill"></i>ClickHouse · ${d.query_ms} ms${d.cached ? " (cached)" : ""} · updated ${t}`;
    } catch (e) {
      if (e.name === "AbortError") return;
      const box = $("#ixError");
      box.textContent = e.message;
      box.classList.remove("d-none");
    } finally {
      root.classList.remove("is-refreshing");
      cards.forEach((c) => c.classList.remove("is-loading"));
      first = false;
    }
  }

  // ---- Per-visual actions ----
  function renderTable(card) {
    const t = tables[card.dataset.viz];
    const box = $(".ix-table", card);
    if (!t || !t.rows.length) { box.innerHTML = `<p class="small text-muted p-3 mb-0">No rows.</p>`; return; }
    box.innerHTML = `<table class="table table-sm"><thead><tr>${t.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>` +
      t.rows.map((r) => `<tr>${r.map((v) => (typeof v === "number" ? `<td class="num">${num.format(v)}</td>` : `<td>${esc(v ?? "")}</td>`)).join("")}</tr>`).join("") +
      `</tbody></table>`;
  }
  function download(name, href) { const a = Object.assign(document.createElement("a"), { href, download: name }); a.click(); }
  const closeFocus = () => { $(".ix-viz.is-full")?.classList.remove("is-full"); $(".ix-backdrop")?.remove(); Object.values(charts).forEach((c) => c.resize()); };

  root.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-act]");
    if (btn) {
      const card = btn.closest(".ix-viz"), id = card.dataset.viz;
      const range = `${state.date_from}_${state.date_to}`;
      if (btn.dataset.act === "table") {
        const box = $(".ix-table", card), chart = $(".ix-chart", card);
        box.hidden = !box.hidden; chart.hidden = !box.hidden; btn.classList.toggle("active", !box.hidden);
        if (!box.hidden) renderTable(card); else charts[id].resize();
      } else if (btn.dataset.act === "csv") {
        const t = tables[id];
        if (!t) return;
        const cell = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
        const csv = [t.columns, ...t.rows].map((r) => r.map(cell).join(",")).join("\r\n");
        download(`${id}_${range}.csv`, URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" })));
      } else if (btn.dataset.act === "png") {
        download(`${id}_${range}.png`, charts[id].getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" }));
      } else if (btn.dataset.act === "expand") {
        if (card.classList.contains("is-full")) return closeFocus();
        card.classList.add("is-full");
        document.body.insertAdjacentHTML("beforeend", `<div class="ix-backdrop"></div>`);
        $(".ix-backdrop").addEventListener("click", closeFocus);
        setTimeout(() => charts[id].resize(), 50);
      }
      return;
    }
    const clear = e.target.closest("[data-clear]");
    if (clear) { state[clear.dataset.clear] = ""; load(); }
  });
  document.addEventListener("keydown", (e) => e.key === "Escape" && closeFocus());

  $("#ixPresets").addEventListener("click", (e) => {
    const a = e.target.closest("[data-preset]");
    if (!a) return;
    e.preventDefault(); applyPreset(a.dataset.preset); load();
  });
  ["ixFrom", "ixTo"].forEach((id) => $(`#${id}`).addEventListener("change", () => {
    const from = $("#ixFrom").value, to = $("#ixTo").value;
    if (!from || !to) return;
    Object.assign(state, { preset: "", date_from: from, date_to: to }); load();
  }));
  [["ixDepartment", "department"], ["ixDoctor", "doctor"], ["ixStatus", "status"]].forEach(([id, key]) =>
    $(`#${id}`)?.addEventListener("change", (e) => { state[key] = e.target.value; load(); }));
  $("#ixReset").addEventListener("click", () => { Object.assign(state, { department: "", doctor: "", status: "" }); applyPreset("90"); load(); });
  $("#ixRefresh").addEventListener("click", load);

  load();
})();
