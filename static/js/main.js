// UI helpers + Chart.js wrappers
const PALETTE = ["#2b2f77", "#f2a93b", "#1f9d6b", "#d64545", "#6c72d9", "#8a5a2b", "#999"];

function gradeFor(total) {
  const bands = [[90, "O"], [80, "A+"], [70, "A"], [60, "B+"], [50, "B"], [40, "C"], [0, "F"]];
  return bands.find(([min]) => total >= min)[1];
}

function barChart(id, labels, datasets, opts = {}) {
  const el = document.getElementById(id);
  if (!el || !window.Chart) return;
  new Chart(el, {
    type: "bar",
    data: { labels, datasets: datasets.map((d, i) => ({ backgroundColor: PALETTE[i], borderRadius: 6, ...d })) },
    options: {
      responsive: true,
      scales: { x: { stacked: !!opts.stacked }, y: { stacked: !!opts.stacked, beginAtZero: true, max: 100 } },
    },
  });
}

function lineChart(id, labels, datasets, threshold) {
  const el = document.getElementById(id);
  if (!el || !window.Chart) return;
  const all = datasets.map((d, i) => ({ borderColor: PALETTE[i], backgroundColor: PALETTE[i], tension: 0.3, ...d }));
  if (threshold) all.push({ label: `Required ${threshold}%`, data: labels.map(() => threshold), borderColor: "#d64545", borderDash: [6, 4], pointRadius: 0 });
  new Chart(el, { type: "line", data: { labels, datasets: all }, options: { responsive: true, scales: { y: { beginAtZero: true, max: 100 } } } });
}

function pieChart(id, labels, data) {
  const el = document.getElementById(id);
  if (!el || !window.Chart) return;
  new Chart(el, { type: "doughnut", data: { labels, datasets: [{ data, backgroundColor: PALETTE }] }, options: { responsive: true } });
}

document.addEventListener("DOMContentLoaded", () => {
  // mobile nav
  document.querySelector("[data-toggle-nav]")?.addEventListener("click", () =>
    document.getElementById("nav").classList.toggle("open"));

  // auto-dismiss flash messages
  document.querySelectorAll("[data-dismissable]").forEach((el) => setTimeout(() => el.remove(), 5000));

  // confirm deletes
  document.querySelectorAll("form[data-confirm]").forEach((f) =>
    f.addEventListener("submit", (e) => { if (!confirm(f.dataset.confirm)) e.preventDefault(); }));

  // admin tabs
  const tabs = document.querySelectorAll("[data-tabs] .tab");
  const show = (name) => {
    tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("hidden", p.id !== name));
  };
  tabs.forEach((t) => t.addEventListener("click", () => show(t.dataset.tab)));
  if (tabs.length && location.hash) {
    const name = location.hash.slice(1);
    if (document.getElementById(name)?.classList.contains("tab-panel")) show(name);
  }

  // attendance: mark all + live summary
  const summary = document.getElementById("att-summary");
  const updateSummary = () => {
    if (!summary) return;
    const c = { present: 0, absent: 0, late: 0 };
    document.querySelectorAll(".status-group input:checked").forEach((i) => c[i.value]++);
    summary.textContent = `Present ${c.present} · Absent ${c.absent} · Late ${c.late}`;
  };
  document.querySelectorAll("[data-mark-all]").forEach((b) =>
    b.addEventListener("click", () => {
      document.querySelectorAll(`.status-group input[value="${b.dataset.markAll}"]`).forEach((i) => (i.checked = true));
      updateSummary();
    }));
  document.querySelectorAll(".status-group input").forEach((i) => i.addEventListener("change", updateSummary));
  updateSummary();

  // marks: live totals + grades
  document.querySelectorAll("[data-mark-row]").forEach((row) => {
    const inp = row.querySelector("[data-internal]"), ext = row.querySelector("[data-external]");
    const recalc = () => {
      const i = Math.min(40, Math.max(0, +inp.value || 0)), e = Math.min(60, Math.max(0, +ext.value || 0));
      const total = i + e, g = gradeFor(total);
      row.querySelector("[data-total]").textContent = total;
      const pill = row.querySelector("[data-grade]");
      pill.textContent = g;
      pill.className = "pill " + (g === "F" ? "bad" : "good");
    };
    inp.addEventListener("input", recalc); ext.addEventListener("input", recalc); recalc();
  });
});
