/* Fill edit/add modals for schedules and departments from the triggering button's data attributes. */
(() => {
  const on = (id, fn) => document.getElementById(id)?.addEventListener("show.bs.modal", (e) => e.relatedTarget && fn(e.currentTarget, e.relatedTarget.dataset));

  on("editSchedule", (m, d) => {
    m.querySelector("[name=id]").value = d.id;
    m.querySelector("[name=day_of_week]").value = d.day;
    m.querySelector("[name=start_time]").value = d.start;
    m.querySelector("[name=end_time]").value = d.end;
    m.querySelector("[name=slot_duration]").value = d.slot;
  });

  on("addSchedule", (m, d) => {
    m.querySelectorAll("[name=days]").forEach((c) => { c.checked = d.addDay !== undefined && c.value === d.addDay; });
  });

  on("deptModal", (m, d) => {
    const dept = JSON.parse(d.dept || "{}");
    m.querySelector("[name=id]").value = dept.id || "";
    m.querySelector("[name=name]").value = dept.name || "";
    m.querySelector("[name=code]").value = dept.code || "";
    m.querySelector("[name=description]").value = dept.description || "";
    m.querySelector("[name=is_active]").checked = dept.is_active !== false;
    m.querySelector(".modal-title, h2").textContent = dept.id ? "Edit department" : "Add department";
  });
})();
