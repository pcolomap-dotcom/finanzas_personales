"use strict";

const API = "/api";
const state = { accounts: [], categories: [], month: monthNow(), account: "" };

function monthNow() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
const $ = (sel) => document.querySelector(sel);
async function api(path, opts) {
  const res = await fetch(API + path, opts);
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  return res.status === 204 ? null : res.json();
}
function fmt(amount, currency) {
  const locale = currency === "EUR" ? "es-ES" : "es-CL";
  const digits = currency === "EUR" ? 2 : 0;
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency", currency, minimumFractionDigits: digits, maximumFractionDigits: digits,
    }).format(amount);
  } catch {
    return `${amount} ${currency}`;
  }
}

/* ---------------------------- navegación ---------------------------- */
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    tab.classList.add("active");
    $("#view-" + tab.dataset.view).classList.add("active");
    if (tab.dataset.view === "presupuestos") loadBudgets();
    if (tab.dataset.view === "movimientos") loadTransactions();
  });
});

/* ---------------------------- carga inicial ------------------------- */
async function init() {
  $("#month-picker").value = state.month;
  $("#month-picker").addEventListener("change", (e) => { state.month = e.target.value; refresh(); });
  $("#account-filter").addEventListener("change", (e) => { state.account = e.target.value; refresh(); });
  $("#import-btn").addEventListener("click", doImport);
  $("#budget-add").addEventListener("click", addBudget);

  [state.categories, state.accounts] = await Promise.all([
    api("/categories"), api("/accounts"),
  ]);
  renderAccountSelectors();
  renderCategorySelectors();
  refresh();
  registerSW();
}

function renderAccountSelectors() {
  const opts = `<option value="">Todas las cuentas</option>` +
    state.accounts.map((a) => `<option value="${a.id}">${a.name} · ${a.currency}</option>`).join("");
  $("#account-filter").innerHTML = opts;
  $("#import-account").innerHTML = state.accounts
    .map((a) => `<option value="${a.id}">${a.name} · ${a.bank} · ${a.currency}</option>`).join("")
    || `<option value="">(crea una cuenta primero)</option>`;
}
function renderCategorySelectors() {
  const opts = state.categories.map((c) => `<option value="${c.id}">${c.icon} ${c.name}</option>`).join("");
  $("#budget-category").innerHTML = opts;
}
function categoryOptions(selectedId) {
  return state.categories
    .map((c) => `<option value="${c.id}" ${c.id === selectedId ? "selected" : ""}>${c.icon} ${c.name}</option>`)
    .join("");
}

function refresh() {
  loadSummary();
  const active = document.querySelector(".tab.active").dataset.view;
  if (active === "movimientos") loadTransactions();
}

/* ---------------------------- resumen ------------------------------- */
async function loadSummary() {
  const data = await api(`/summary?month=${state.month}`);
  const kpis = $("#kpis");
  const breakdown = $("#cat-breakdown");
  const currencies = Object.entries(data.currencies || {});
  if (currencies.length === 0) {
    kpis.innerHTML = `<div class="empty">Sin datos este mes. Importa una cartola en la pestaña <b>Importar</b>.</div>`;
    breakdown.innerHTML = "";
    loadBudgetMini();
    return;
  }
  kpis.innerHTML = currencies.map(([cur, c]) => `
    <div class="kpi"><div class="label">Ingresos · ${cur}</div>
      <div class="value pos">${fmt(c.income, cur)}</div></div>
    <div class="kpi"><div class="label">Gastos · ${cur}</div>
      <div class="value neg">${fmt(c.expense, cur)}</div></div>
    <div class="kpi"><div class="label">Balance · ${cur}</div>
      <div class="value ${c.net >= 0 ? "pos" : "neg"}">${fmt(c.net, cur)}</div></div>
  `).join("");

  breakdown.innerHTML = currencies.map(([cur, c]) => {
    const max = Math.max(...c.by_category.map((x) => x.amount), 1);
    if (!c.by_category.length) return "";
    return `<div class="muted" style="margin:6px 0">${cur}</div>` + c.by_category.map((x) => `
      <div class="bar-row">
        <span class="ico">${x.icon}</span>
        <span class="name">${x.category}</span>
        <span class="track"><span class="fill" style="width:${(x.amount / max) * 100}%;background:${x.color}"></span></span>
        <span class="amt">${fmt(x.amount, cur)}</span>
      </div>`).join("");
  }).join("") || `<div class="empty">Sin gastos categorizados.</div>`;

  loadBudgetMini();
}

async function loadBudgetMini() {
  const status = await api(`/budgets/status?month=${state.month}`);
  const el = $("#budget-mini");
  if (!status.length) { el.innerHTML = `<div class="empty">Aún no defines presupuestos.</div>`; return; }
  el.innerHTML = status.map(renderBudgetBar).join("");
}
function renderBudgetBar(b) {
  const pct = Math.min(b.pct, 100);
  const over = b.spent > b.limit;
  return `<div class="budget ${over ? "over" : ""}">
    <div class="top"><span>${b.icon} ${b.category}</span>
      <span>${fmt(b.spent, b.currency)} / ${fmt(b.limit, b.currency)} (${b.pct}%)</span></div>
    <div class="track"><span class="fill" style="width:${pct}%;background:${b.color}"></span></div>
  </div>`;
}

/* -------------------------- movimientos ----------------------------- */
async function loadTransactions() {
  const q = new URLSearchParams({ month: state.month });
  if (state.account) q.set("account_id", state.account);
  const txs = await api(`/transactions?${q}`);
  const el = $("#tx-list");
  if (!txs.length) { el.innerHTML = `<div class="empty">Sin movimientos.</div>`; return; }
  el.innerHTML = txs.map((t) => `
    <div class="tx">
      <div class="ico" style="color:${t.category_color}">${t.category_icon}</div>
      <div class="desc">
        <div class="t">${escapeHtml(t.description)}</div>
        <div class="m">${t.date}</div>
        <select data-id="${t.id}" onchange="recategorize(this)">${categoryOptions(t.category_id)}</select>
      </div>
      <div class="amount ${t.amount >= 0 ? "pos" : ""}">${fmt(t.amount, t.currency)}</div>
    </div>`).join("");
}
async function recategorize(select) {
  await api(`/transactions/${select.dataset.id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category_id: Number(select.value) }),
  });
  loadSummary();
}
window.recategorize = recategorize;

/* ---------------------------- importar ------------------------------ */
async function doImport() {
  const accountId = $("#import-account").value;
  const file = $("#import-file").files[0];
  const out = $("#import-result");
  if (!accountId || !file) { out.textContent = "Elige cuenta y archivo."; return; }
  out.textContent = "Importando…";
  const fd = new FormData();
  fd.append("account_id", accountId);
  fd.append("file", file);
  try {
    const r = await api("/import/csv", { method: "POST", body: fd });
    if (r.error) { out.innerHTML = `⚠️ ${r.error}` + (r.headers ? `<br><span class="muted">Columnas: ${r.headers.join(", ")}</span>` : ""); return; }
    out.innerHTML = `✅ Importadas <b>${r.imported}</b>, omitidas ${r.skipped} (duplicadas/vacías).`;
    refresh();
  } catch (e) {
    out.textContent = "Error: " + e.message;
  }
}

/* -------------------------- presupuestos ---------------------------- */
async function loadBudgets() {
  const status = await api(`/budgets/status?month=${state.month}`);
  const el = $("#budget-list");
  el.innerHTML = status.length ? status.map(renderBudgetBar).join("")
    : `<div class="empty">Sin presupuestos.</div>`;
}
async function addBudget() {
  const body = {
    category_id: Number($("#budget-category").value),
    amount: Number($("#budget-amount").value),
    currency: $("#budget-currency").value,
  };
  if (!body.amount) return;
  await api("/budgets", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  $("#budget-amount").value = "";
  loadBudgets();
  loadBudgetMini();
}

/* ----------------------------- utils -------------------------------- */
function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function registerSW() {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}

init().catch((e) => { document.body.innerHTML = `<pre style="padding:20px">Error al iniciar: ${e.message}</pre>`; });
