/* Slot picker (date chips -> live slots) and the 6-step booking wizard. */
(() => {
  const root = document.querySelector("[data-slot-picker]");
  if (!root) return;
  const $ = (s) => root.querySelector(s);
  const dateIn = $("input[name=appointment_date]");
  const timeIn = $("input[name=start_time]");
  const area = root.querySelector("[data-slot-area]");
  const dateLabel = root.querySelector("[data-slot-date]");

  const fmtDate = (iso) => new Date(`${iso}T00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const fmtTime = (hm) => { const [h, m] = hm.split(":").map(Number); return new Date(2000, 0, 1, h, m).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); };

  function review() {
    document.querySelectorAll("[data-review]").forEach((el) => {
      const k = el.dataset.review;
      if (k === "date") el.textContent = dateIn.value ? fmtDate(dateIn.value) : "Not selected";
      if (k === "time") el.textContent = timeIn.value ? fmtTime(timeIn.value) : "Not selected";
      if (k === "reason") el.textContent = (root.querySelector("[name=reason]") || {}).value || "—";
    });
  }

  async function loadSlots(date) {
    dateIn.value = date;
    root.querySelectorAll(".date-chip").forEach((c) => c.classList.toggle("selected", c.dataset.date === date));
    if (dateLabel) dateLabel.textContent = `· ${fmtDate(date)}`;
    review();
    area.innerHTML = `<div class="py-4 text-center"><div class="spinner-ring mx-auto" style="width:32px;height:32px"></div></div>`;
    try {
      const r = await fetch(`/ajax/doctors/${root.dataset.doctor}/slots/?date=${date}`, { headers: { Accept: "application/json" } });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Could not load slots.");
      if (!data.slots.length) {
        area.innerHTML = `<div class="empty py-4"><div class="empty-icon"><i class="bi bi-calendar-x"></i></div><h3>No open slots</h3><p class="small mb-0">Try another date.</p></div>`;
        return;
      }
      const groups = { Morning: [], Afternoon: [], Evening: [] };
      data.slots.forEach((s) => { const h = +s.start.slice(0, 2); groups[h < 12 ? "Morning" : h < 17 ? "Afternoon" : "Evening"].push(s); });
      const icon = { Morning: "bi-sunrise", Afternoon: "bi-sun", Evening: "bi-moon-stars" };
      area.innerHTML = Object.entries(groups).filter(([, v]) => v.length).map(([name, slots]) => `
        <div class="slot-group-title"><i class="bi ${icon[name]}"></i>${name}</div>
        <div class="slot-grid">${slots.map((s) => `<button type="button" class="slot-btn ${s.start === timeIn.value ? "selected" : ""}" data-time="${s.start}" aria-pressed="${s.start === timeIn.value}">${fmtTime(s.start)}</button>`).join("")}</div>`).join("");
      if (timeIn.value && !data.slots.some((s) => s.start === timeIn.value)) timeIn.value = "";
      review();
    } catch (err) {
      area.innerHTML = `<div class="alert alert-danger small mb-0">${window.MB.esc(err.message)}</div>`;
    }
  }

  area.addEventListener("click", (e) => {
    const btn = e.target.closest(".slot-btn");
    if (!btn) return;
    area.querySelectorAll(".slot-btn").forEach((b) => { b.classList.toggle("selected", b === btn); b.setAttribute("aria-pressed", b === btn); });
    timeIn.value = btn.dataset.time;
    review();
  });
  root.querySelectorAll(".date-chip").forEach((chip) => chip.addEventListener("click", () => {
    if (chip.classList.contains("disabled")) return;
    timeIn.value = "";
    loadSlots(chip.dataset.date);
    if (wizard) wizard.go(3);
  }));
  root.querySelector("[data-date-input]")?.addEventListener("change", (e) => {
    if (!e.target.value) return;
    timeIn.value = "";
    loadSlots(e.target.value);
    if (wizard) wizard.go(3);
  });

  // Doctor profile: carry the chosen slot into the booking page
  document.querySelector("[data-book-with-slot]")?.addEventListener("click", (e) => {
    if (dateIn.value) e.currentTarget.href += `?date=${dateIn.value}${timeIn.value ? `&time=${timeIn.value}` : ""}`;
  });

  // Plain forms (reschedule): require a slot before submitting
  const form = root.closest("form");
  form?.addEventListener("submit", (e) => {
    if (!dateIn.value || !timeIn.value) {
      e.preventDefault(); e.stopImmediatePropagation();
      window.MB.toast("Please choose a date and a time slot.", "error");
    }
  }, true);

  // ---- 6-step wizard (booking page only) ----
  const panels = [...root.querySelectorAll("[data-step]")];
  const wizard = panels.length ? (() => {
    let current = 1;
    const prev = root.querySelector("[data-step-prev]"), next = root.querySelector("[data-step-next]"), submit = root.querySelector("[data-step-submit]");
    const reason = root.querySelector("[name=reason]");
    const valid = (n) => {
      if (n === 2 && !dateIn.value) return window.MB.toast("Please select a date.", "error"), false;
      if (n === 3 && !timeIn.value) return window.MB.toast("Please select a time slot.", "error"), false;
      if (n === 4 && reason.value.trim().length < 3) { reason.classList.add("is-invalid"); reason.focus(); return false; }
      return true;
    };
    const go = (n) => {
      current = Math.min(Math.max(n, 1), panels.length);
      panels.forEach((p) => p.classList.toggle("active", +p.dataset.step === current));
      root.querySelectorAll("[data-step-ind]").forEach((s) => {
        s.classList.toggle("active", +s.dataset.stepInd === current);
        s.classList.toggle("done", +s.dataset.stepInd < current);
      });
      prev.style.visibility = current === 1 ? "hidden" : "visible";
      next.classList.toggle("d-none", current === panels.length);
      submit.classList.toggle("d-none", current !== panels.length);
      review();
    };
    next.addEventListener("click", () => {
      for (let n = 2; n <= current; n++) if (!valid(n)) return go(n);
      go(current + 1);
    });
    prev.addEventListener("click", () => go(current - 1));
    reason.addEventListener("input", () => reason.classList.remove("is-invalid"));
    form.addEventListener("submit", (e) => {
      for (let n = 2; n <= 4; n++) if (!valid(n)) { e.preventDefault(); e.stopImmediatePropagation(); return go(n); }
      if (!root.querySelector("#agree").checked) { e.preventDefault(); e.stopImmediatePropagation(); window.MB.toast("Please accept the visit policy to confirm.", "error"); }
    }, true);
    go(+root.dataset.startStep || 1);
    return { go };
  })() : null;

  if (dateIn.value) loadSlots(dateIn.value);
  review();
})();
