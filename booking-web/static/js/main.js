/* Global UI behaviour: sidebar, toasts, loading overlay, confirm forms, cancel modal, notifications. */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];

  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || "";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  window.MB = { csrf, esc };

  // Toasts
  const dismiss = (t) => { t.style.transition = "opacity .25s, transform .25s"; t.style.opacity = 0; t.style.transform = "translateY(-6px)"; setTimeout(() => t.remove(), 250); };
  window.MB.toast = (msg, type = "info") => {
    const icon = { success: "bi-check2-circle", error: "bi-exclamation-octagon" }[type] || "bi-info-circle";
    const t = document.createElement("div");
    t.className = `toast-x ${type}`;
    t.innerHTML = `<span class="toast-icon"><i class="bi ${icon}"></i></span><div class="small fw-semibold text-dark">${esc(msg)}</div><button type="button" class="btn-close" aria-label="Dismiss" data-toast-close></button>`;
    $("#toastStack").appendChild(t);
    setTimeout(() => dismiss(t), 5000);
  };
  $$(".toast-x").forEach((t) => setTimeout(() => dismiss(t), 5000));
  document.addEventListener("click", (e) => { const b = e.target.closest("[data-toast-close]"); if (b) dismiss(b.closest(".toast-x")); });

  // Sidebar (mobile)
  const sidebar = $("#sidebar");
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-sidebar-toggle]")) sidebar?.classList.add("open");
    if (e.target.closest("[data-sidebar-close]")) sidebar?.classList.remove("open");
  });
  const topbar = $("#topbar");
  if (topbar) addEventListener("scroll", () => topbar.classList.toggle("scrolled", scrollY > 4), { passive: true });

  // Confirm + loading overlay on form submit
  const overlay = $("#loadingOverlay");
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (form.dataset.confirm && !confirm(form.dataset.confirm)) { e.preventDefault(); return; }
    if (e.defaultPrevented) return;
    if (form.hasAttribute("data-loading") || form.id === "bookingForm") overlay?.classList.add("show");
  });
  addEventListener("pageshow", () => overlay?.classList.remove("show")); // back/forward cache

  // Cancel modal: the triggering button provides the URL and appointment number
  const cancelModal = $("#cancelModal");
  cancelModal?.addEventListener("show.bs.modal", (e) => {
    const btn = e.relatedTarget;
    if (!btn) return;
    $("#cancelForm").action = btn.dataset.cancelUrl;
    $("[data-cancel-number]", cancelModal).textContent = btn.dataset.cancelNumber || "this appointment";
    $("#cancelReason").value = "";
  });

  // Notifications dropdown
  const list = $("#notifList"), count = $("#notifCount");
  if (!list) return;
  const base = (window.location.pathname.match(/^\/(patient|doctor|admin)\//) || [])[0] || "/";
  const icons = { APPOINTMENT_BOOKED: "bi-calendar-plus", APPOINTMENT_CONFIRMED: "bi-patch-check", APPOINTMENT_CANCELLED: "bi-calendar-x",
    APPOINTMENT_RESCHEDULED: "bi-arrow-repeat", APPOINTMENT_COMPLETED: "bi-check2-all", APPOINTMENT_REMINDER: "bi-alarm" };
  const ago = (iso) => {
    const s = (Date.now() - new Date(iso)) / 1000;
    if (s < 60) return "just now";
    for (const [n, u] of [[86400, "d"], [3600, "h"], [60, "m"]]) if (s >= n) return `${Math.floor(s / n)}${u} ago`;
  };
  const post = (url) => fetch(url, { method: "POST", headers: { "X-CSRFToken": csrf() } });

  async function load() {
    try {
      const r = await fetch("/ajax/notifications/", { headers: { Accept: "application/json" } });
      if (!r.ok) throw 0;
      const data = await r.json();
      count.textContent = data.unread_count > 9 ? "9+" : data.unread_count;
      count.classList.toggle("d-none", !data.unread_count);
      list.innerHTML = data.results.length ? data.results.map((n) => `
        <div class="notif-item ${n.is_read ? "" : "unread"}" data-id="${n.id}" data-appt="${n.appointment ?? ""}" role="button" tabindex="0">
          <span class="notif-icon"><i class="bi ${icons[n.notification_type] || "bi-bell"}"></i></span>
          <div><div class="notif-title">${esc(n.title)}</div><div class="notif-msg">${esc(n.message)}</div><div class="notif-time">${ago(n.created_at)}</div></div>
        </div>`).join("")
        : `<div class="empty py-4"><div class="empty-icon"><i class="bi bi-bell-slash"></i></div><p class="small mb-0">You're all caught up.</p></div>`;
    } catch { list.innerHTML = `<p class="small text-muted p-3 mb-0">Couldn't load notifications.</p>`; }
  }
  list.addEventListener("click", async (e) => {
    const item = e.target.closest(".notif-item");
    if (!item) return;
    await post(`/ajax/notifications/${item.dataset.id}/read/`);
    if (item.dataset.appt && base !== "/") location.href = `${base}appointments/${item.dataset.appt}/`;
    else load();
  });
  $("#notifReadAll")?.addEventListener("click", async () => { await post("/ajax/notifications/read-all/"); load(); });
  $("#notifBtn")?.addEventListener("show.bs.dropdown", load);
  load();
  setInterval(() => document.visibilityState === "visible" && load(), 60000);
})();
