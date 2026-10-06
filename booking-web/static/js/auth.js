/* Password visibility toggle, strength meter and confirm-match feedback. */
(() => {
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-pw-toggle]");
    if (!btn) return;
    const input = document.getElementById(btn.dataset.pwToggle);
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.querySelector("i").className = show ? "bi bi-eye-slash" : "bi bi-eye";
    btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
  });

  document.querySelectorAll("[data-pw-meter]").forEach((input) => {
    const bar = input.closest("div").parentElement.querySelector(".pw-meter span");
    input.addEventListener("input", () => {
      const v = input.value;
      const score = [v.length >= 8, /[A-Z]/.test(v) && /[a-z]/.test(v), /\d/.test(v), /[^A-Za-z0-9]/.test(v), v.length >= 12]
        .filter(Boolean).length;
      bar.style.width = `${(score / 5) * 100}%`;
      bar.style.background = ["#dc2626", "#dc2626", "#d97706", "#d97706", "#0d9488", "#15803d"][score];
    });
  });

  document.querySelectorAll("[data-pw-confirm]").forEach((confirm) => {
    const pw = document.getElementById(confirm.dataset.pwConfirm);
    const check = () => confirm.classList.toggle("is-invalid", !!confirm.value && confirm.value !== pw.value);
    confirm.addEventListener("input", check);
    pw.addEventListener("input", () => confirm.value && check());
  });
})();
