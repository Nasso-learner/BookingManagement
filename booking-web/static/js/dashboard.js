/* Count-up animation for dashboard stat values. */
(() => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  document.querySelectorAll("[data-count]").forEach((el) => {
    const target = +el.dataset.count || 0;
    if (!target) return;
    const start = performance.now(), dur = 700;
    const tick = (t) => {
      const p = Math.min((t - start) / dur, 1);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
})();
