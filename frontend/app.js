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
    if (tab.dataset.view === "deudas") loadDebts();
    if (tab.dataset.view === "traspasos") loadTransfers();
    if (tab.dataset.view === "salud") loadSalud();
  });
});

/* ---------------------------- carga inicial ------------------------- */
async function init() {
  $("#month-picker").value = state.month;
  $("#month-picker").addEventListener("change", (e) => { state.month = e.target.value; refresh(); });
  $("#account-filter").addEventListener("change", (e) => { state.account = e.target.value; refresh(); });
  $("#import-btn").addEventListener("click", doImport);
  $("#recat-btn").addEventListener("click", doRecategorize);
  $("#budget-add").addEventListener("click", addBudget);
  $("#debt-import-btn").addEventListener("click", doImportDebts);
  $("#acc-add").addEventListener("click", doAddAccount);
  $("#salud-income").value = localStorage.getItem("income") || "";
  $("#salud-calc").addEventListener("click", () => {
    localStorage.setItem("income", $("#salud-income").value || "");
    loadSalud();
  });
  $("#mail-sync-btn").addEventListener("click", doMailSync);
  $("#mail-filter-btn").addEventListener("click", showGmailFilter);
  $("#mailtext-btn").addEventListener("click", doMailText);

  [state.categories, state.accounts] = await Promise.all([
    api("/categories"), api("/accounts"),
  ]);
  renderAccountSelectors();
  renderAccountsList();
  renderCategorySelectors();
  refresh();
  registerSW();
}

function renderAccountSelectors() {
  const opts = `<option value="">Todas las cuentas</option>` +
    state.accounts.map((a) => `<option value="${a.id}">${a.name} · ${a.currency}</option>`).join("");
  $("#account-filter").innerHTML = opts;
  const accOpts = state.accounts
    .map((a) => `<option value="${a.id}">${a.name} · ${a.bank} · ${a.currency}</option>`).join("")
    || `<option value="">(crea una cuenta primero)</option>`;
  $("#import-account").innerHTML = accOpts;
  $("#mail-account").innerHTML = accOpts;
  $("#mailtext-account").innerHTML = accOpts;
}
function renderAccountsList() {
  const el = $("#accounts-list");
  if (!el) return;
  el.innerHTML = state.accounts.length
    ? state.accounts.map((a) => `<span class="chip">${escapeHtml(a.name)} · ${a.currency}</span>`).join(" ")
    : `<span class="muted">Aún no tienes cuentas.</span>`;
}
async function doAddAccount() {
  const name = $("#acc-name").value.trim();
  if (!name) { $("#acc-name").focus(); return; }
  const body = {
    name, bank: $("#acc-bank").value.trim(),
    country: $("#acc-country").value, currency: $("#acc-currency").value,
  };
  await api("/accounts", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  state.accounts = await api("/accounts");
  renderAccountSelectors();
  renderAccountsList();
  $("#acc-name").value = ""; $("#acc-bank").value = "";
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

async function doRecategorize() {
  const out = $("#recat-result");
  out.textContent = "Procesando…";
  try {
    const r = await api("/maintenance/recategorize", { method: "POST" });
    out.innerHTML = `✅ Revisados ${r.revisados}, categorizados <b>${r.actualizados}</b>.`;
    refresh();
    if (document.querySelector(".tab.active").dataset.view === "movimientos") loadTransactions();
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

/* ----------------------------- deudas ------------------------------- */
async function loadDebts() {
  const data = await api("/debts");
  const t = data.totals;
  $("#debt-kpis").innerHTML = `
    <div class="kpi"><div class="label">Deuda total</div>
      <div class="value neg">${fmt(t.total, "CLP")}</div></div>
    <div class="kpi"><div class="label">Cuota mensual</div>
      <div class="value">${fmt(t.monthly, "CLP")}</div></div>
    <div class="kpi"><div class="label">Por pagar este mes</div>
      <div class="value ${t.pending_month > 0 ? "neg" : "pos"}">${fmt(t.pending_month, "CLP")}</div></div>
    <div class="kpi"><div class="label">Créditos de consumo</div>
      <div class="value neg">${fmt(t.consumo, "CLP")}</div></div>
    <div class="kpi"><div class="label">Tarjetas de crédito</div>
      <div class="value neg">${fmt(t.tarjetas || 0, "CLP")}</div></div>
    <div class="kpi"><div class="label">Líneas de crédito</div>
      <div class="value neg">${fmt(t.lineas || 0, "CLP")}</div></div>
    <div class="kpi"><div class="label">En mora</div>
      <div class="value ${t.arrears > 0 ? "neg" : "pos"}">${fmt(t.arrears, "CLP")}</div></div>`;

  const list = $("#debt-list");
  if (!data.items.length) {
    list.innerHTML = `<div class="empty">Aún no importas tu informe de deudas.</div>`;
    return;
  }
  list.innerHTML = data.items.map((d) => {
    const isCard = (d.credit_type || "").toLowerCase().includes("tarjeta");
    const ico = d.is_consumo ? "💳" : isCard ? "💳" : "🏦";
    const nextInfo = d.next_due
      ? `próximo venc: <b>${d.next_due}</b>${d.paid_this_month ? " ✅ pagada este mes" : ""}`
      : "sin día de pago configurado";
    return `<div class="debt">
      <div class="debt-head">
        <div class="ico">${ico}</div>
        <div class="desc">
          <div class="t">${escapeHtml(d.institution)} ${d.is_consumo ? '<span style="color:var(--primary)">• consumo</span>' : ""}</div>
          <div class="m">${escapeHtml(d.credit_type)} · ${nextInfo}</div>
        </div>
        <div class="amount">${fmt(d.current_amount, "CLP")}</div>
      </div>
      <div class="debt-edit">
        <label>Cuota <input type="number" id="cuota-${d.id}" value="${d.monthly_payment || ""}" /></label>
        <label>Día <input type="number" min="1" max="31" id="day-${d.id}" value="${d.payment_day || ""}" /></label>
        <button class="btn mini" onclick="saveDebt(${d.id})">Guardar</button>
        <button class="btn mini primary" onclick="markPaid(${d.id})">Marcar cuota pagada</button>
      </div>
    </div>`;
  }).join("");
}
async function saveDebt(id) {
  const body = {
    monthly_payment: Number($("#cuota-" + id).value) || 0,
    payment_day: Number($("#day-" + id).value) || null,
  };
  await api("/debts/" + id, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  loadDebts();
}
async function markPaid(id) {
  await api("/debts/" + id + "/mark_paid", { method: "POST" });
  loadDebts();
}
window.saveDebt = saveDebt;
window.markPaid = markPaid;
async function doImportDebts() {
  const file = $("#debt-file").files[0];
  const out = $("#debt-import-result");
  if (!file) { out.textContent = "Elige el archivo CSV del informe."; return; }
  out.textContent = "Importando…";
  const fd = new FormData();
  fd.append("file", file);
  try {
    const r = await api("/debts/import", { method: "POST", body: fd });
    if (r.error) { out.innerHTML = `⚠️ ${r.error}`; return; }
    out.innerHTML = `✅ ${r.imported} deudas nuevas, ${r.updated} actualizadas.`;
    loadDebts();
  } catch (e) {
    out.textContent = "Error: " + e.message;
  }
}

/* ------------------------------ salud ------------------------------- */
async function loadSalud() {
  const inc = Number($("#salud-income").value) || 0;
  const q = new URLSearchParams({ month: state.month });
  if (inc > 0) q.set("income", inc);
  const d = await api("/salud?" + q);
  const el = $("#salud-result");
  if (d.score == null) {
    el.innerHTML = `<div class="empty">${escapeHtml(d.message || "Sin datos este mes.")}</div>`;
    return;
  }
  const deg = Math.round(d.score * 3.6);
  el.innerHTML = `
    <div class="gauge-wrap">
      <div class="gauge" style="background:conic-gradient(${d.color} ${deg}deg, var(--surface-2) 0)">
        <div class="gauge-inner">
          <div class="gauge-score">${d.score}</div>
          <div class="gauge-label" style="color:${d.color}">${d.label}</div>
        </div>
      </div>
      <div class="gauge-side">
        <div>Ingreso: <b>${fmt(d.income, "CLP")}</b></div>
        <div>Gasto: <b>${fmt(d.expense, "CLP")}</b></div>
        <div>Cuotas de deuda: <b>${fmt(d.cuota, "CLP")}</b></div>
        <div>Balance del mes: <b class="${d.balance < 0 ? "neg-text" : ""}">${fmt(d.balance, "CLP")}</b></div>
        <div>Deuda total: <b>${fmt(d.deuda, "CLP")}</b></div>
      </div>
    </div>
    <div class="metrics">
      ${d.metrics.map((m) => `
        <div class="metric ${m.status}">
          <div class="metric-top"><span>${m.key}</span><span>${m.value}</span></div>
          <div class="track"><span class="fill" style="width:${Math.min(m.pct, 100)}%"></span></div>
          <div class="muted">${m.hint}</div>
        </div>`).join("")}
    </div>`;
}

/* ---------------------------- traspasos ----------------------------- */
function accName(id) {
  const a = state.accounts.find((x) => x.id === id);
  return a ? a.name : "Cuenta " + id;
}
async function loadTransfers() {
  const data = await api("/transfers/suggestions");
  const pl = $("#pairs-list");
  pl.innerHTML = data.pairs.length ? data.pairs.map((p) => `
    <div class="sugg">
      <div class="sugg-info">
        <div>↑ <b>${fmt(p.a.amount, p.a.currency)}</b> · ${escapeHtml(accName(p.a.account_id))}
          — ${escapeHtml(p.a.description)} <span class="muted">${p.a.date}</span></div>
        <div>↓ <b>${fmt(p.b.amount, p.b.currency)}</b> · ${escapeHtml(accName(p.b.account_id))}
          — ${escapeHtml(p.b.description)} <span class="muted">${p.b.date}</span></div>
      </div>
      <div class="sugg-actions">
        <button class="btn mini primary" onclick="confirmPair(${p.a.id},${p.b.id})">Es traspaso</button>
        <button class="btn mini" onclick="dismissTx([${p.a.id},${p.b.id}])">Ignorar</button>
      </div>
    </div>`).join("") : `<div class="empty">Sin traspasos por revisar.</div>`;

  const dl = $("#debtpay-list");
  dl.innerHTML = data.debt_payments.length ? data.debt_payments.map((dp) => `
    <div class="sugg">
      <div class="sugg-info">
        <div><b>${fmt(dp.tx.amount, dp.tx.currency)}</b> · ${escapeHtml(accName(dp.tx.account_id))}
          — ${escapeHtml(dp.tx.description)} <span class="muted">${dp.tx.date}</span></div>
        <div class="muted" style="margin-top:4px">Aplicar a:
          <select id="debtsel-${dp.tx.id}">
            ${dp.candidates.map((c) => `<option value="${c.id}">${escapeHtml(c.institution)} · ${escapeHtml(c.credit_type)} · saldo ${fmt(c.current_amount, "CLP")}</option>`).join("")}
          </select>
        </div>
      </div>
      <div class="sugg-actions">
        <button class="btn mini primary" onclick="applyDebt(${dp.tx.id})">Aplicar pago</button>
        <button class="btn mini" onclick="dismissTx([${dp.tx.id}])">Ignorar</button>
      </div>
    </div>`).join("") : `<div class="empty">Sin pagos de deuda por revisar.</div>`;
}
async function confirmPair(a, b) {
  await api("/transfers/confirm_pair", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_a: a, id_b: b }),
  });
  loadTransfers(); loadSummary();
}
async function applyDebt(txId) {
  const debtId = Number($("#debtsel-" + txId).value);
  await api("/transfers/confirm_debt", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tx_id: txId, debt_id: debtId }),
  });
  loadTransfers(); loadSummary();
}
async function dismissTx(ids) {
  await api("/transfers/dismiss", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  loadTransfers();
}
window.confirmPair = confirmPair;
window.applyDebt = applyDebt;
window.dismissTx = dismissTx;

/* ----------------------------- correo ------------------------------- */
async function doMailSync() {
  const out = $("#mail-result");
  const body = {
    account_id: Number($("#mail-account").value),
    host: $("#mail-host").value.trim(),
    user: $("#mail-user").value.trim(),
    password: $("#mail-pass").value,
    folder: $("#mail-folder").value.trim() || "INBOX",
    since_days: Number($("#mail-days").value) || 30,
    use_bank_senders: ($("#mail-folder").value.trim().toUpperCase() === "INBOX"),
  };
  if (!body.account_id || !body.user || !body.password) {
    out.textContent = "Completa cuenta, correo y contraseña de aplicación.";
    return;
  }
  out.textContent = "Conectando y leyendo tu correo…";
  try {
    const r = await api("/ingest/email/imap", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const banks = r.por_banco && Object.keys(r.por_banco).length
      ? "<br>Por banco: " + Object.entries(r.por_banco).map(([b, n]) => `${b} (${n})`).join(", ")
      : "";
    out.innerHTML = `✅ Leídos ${r.emails_leidos}, reconocidos ${r.emails_reconocidos}, ` +
      `importados <b>${r.imported}</b> (omitidos ${r.skipped}).${banks}`;
    refresh();
  } catch (e) {
    out.textContent = "Error: " + e.message;
  }
}
async function showGmailFilter() {
  const box = $("#mail-filter-box");
  box.textContent = "Cargando…";
  try {
    const r = await api("/bank-senders/gmail-filter");
    box.innerHTML = `
      <textarea id="filter-text" rows="4" readonly>${escapeHtml(r.query)}</textarea>
      <button class="btn mini" id="filter-copy">Copiar</button>
      <ol class="muted" style="margin-top:10px;padding-left:18px">
        ${r.pasos.map((p) => `<li>${escapeHtml(p)}</li>`).join("")}
      </ol>`;
    $("#filter-copy").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(r.query);
        $("#filter-copy").textContent = "¡Copiado!";
      } catch {
        $("#filter-text").select();
      }
    });
  } catch (e) {
    box.textContent = "Error: " + e.message;
  }
}
async function doMailText() {
  const out = $("#mailtext-result");
  const body = {
    account_id: Number($("#mailtext-account").value),
    body: $("#mailtext-body").value,
  };
  if (!body.account_id || !body.body.trim()) {
    out.textContent = "Elige cuenta y pega el texto del correo.";
    return;
  }
  out.textContent = "Interpretando…";
  try {
    const r = await api("/ingest/email/text", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (r.parsed) {
      const p = r.parsed;
      out.innerHTML = `✅ ${r.imported ? "Agregado" : "Detectado (duplicado)"}: ` +
        `<b>${escapeHtml(p.description)}</b> · ${fmt(p.amount, p.currency)} · ${p.date}`;
      refresh();
    } else {
      out.innerHTML = `⚠️ ${r.detail || "No se detectó un movimiento en el texto."}`;
    }
  } catch (e) {
    out.textContent = "Error: " + e.message;
  }
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
