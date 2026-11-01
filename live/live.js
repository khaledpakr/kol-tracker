const CA = "6PUjXbaJnS95cbAFG44nmtbKL3NtPPfxVny8jgT5pump";
const $ = (s) => document.querySelector(s);
let feed = null, pnl = null, known = null;

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
function fm(n) {
  if (n == null || isNaN(n)) return "—";
  const a = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (a >= 1e9) return sign + (a / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return sign + (a / 1e6).toFixed(2) + "M";
  if (a >= 1e3) return sign + (a / 1e3).toFixed(1) + "K";
  return sign + a.toFixed(2);
}
function ago(s) {
  if (!s) return "—";
  const d = Date.now() / 1e3 - s;
  if (d < 60) return Math.max(0, Math.floor(d)) + "s";
  if (d < 3600) return Math.floor(d / 60) + "m";
  if (d < 86400) return Math.floor(d / 3600) + "h";
  return Math.floor(d / 86400) + "d";
}
function money(n) {
  if (n == null || isNaN(n)) return "—";
  const sign = n < 0 ? "-" : n > 0 ? "+" : "";
  return sign + "$" + fm(Math.abs(n));
}
function solAmt(n) {
  if (n == null || isNaN(n)) return null;
  const sign = n < 0 ? "-" : n > 0 ? "+" : "";
  return sign + Math.abs(n).toFixed(Math.abs(n) < 100 ? 2 : 0) + " SOL";
}
function fresh(ts) {
  const el = $("#fresh");
  if (!el) return;
  if (!ts) { el.textContent = "updated …"; return; }
  const d = Math.max(0, Date.now() / 1e3 - ts);
  el.textContent = d < 45 ? "updated just now" : d < 3600 ? "updated " + Math.max(1, Math.floor(d / 60)) + " min ago" : "updated " + Math.floor(d / 3600) + " h ago";
}
function keyOf(t) {
  return [t.sig || "", t.wallet, t.mint, t.side, t.time].join("|");
}
function renderFeed() {
  const rows = $("#rows");
  if (!rows) return;
  const trades = (feed && feed.trades || []).slice().sort((a, b) => (b.time || 0) - (a.time || 0)).slice(0, 40);
  if (!trades.length) { rows.innerHTML = `<p class="empty">No trades yet</p>`; return; }
  const first = known == null;
  if (first) known = new Set();
  const tokens = (feed && feed.tokens) || {};
  rows.innerHTML = trades.map((t) => {
    const k = keyOf(t);
    const isNew = !first && !known.has(k);
    known.add(k);
    const tok = tokens[t.mint] || {};
    const sym = t.symbol || tok.symbol || "???";
    const img = tok.img;
    const amt = t.sol != null ? Number(t.sol).toFixed(Math.abs(t.sol) < 10 ? 3 : 1) + " SOL" : t.usd != null ? "$" + fm(t.usd) : "—";
    const mc = t.mc != null ? "$" + fm(t.mc) : tok.mc != null ? "$" + fm(tok.mc) : "—";
    const face = img ? `<img alt="" src="${esc(img)}">` : `<span class="av">${esc(sym[0] || "?")}</span>`;
    return `<article class="row${isNew ? " in" : ""}"><span class="badge ${t.side === "SELL" ? "sell" : "buy"}">${t.side === "SELL" ? "SELL" : "BUY"}</span><div class="who">${esc(t.wallet)}</div><div class="coin">${face}<b>${esc(sym)}</b></div><div class="amt">${esc(amt)}</div><div class="mc">${esc(mc)}</div><div class="ago">${ago(t.time)}</div></article>`;
  }).join("");
}
function renderBoard() {
  const ol = $("#board");
  if (!ol) return;
  const callers = (pnl && pnl.callers) || [];
  const by = Object.fromEntries(callers.map((c) => [c.name, c]));
  let names = (pnl && pnl.boards && pnl.boards.today) || [];
  if (!names.length) names = callers.map((c) => c.name);
  names = names.slice(0, 10);
  if (!names.length) { ol.innerHTML = `<li><span class="flat">No trades</span></li>`; return; }
  ol.innerHTML = names.map((name, i) => {
    const b = ((by[name] || {}).periods || {}).today || {};
    const trades = (b.wins || 0) + (b.losses || 0);
    const cls = !trades ? "flat" : b.net_usd < 0 || (b.net_usd === 0 && b.net_sol < 0) ? "dn" : "up";
    const main = !trades ? "No trades" : money(b.net_usd || 0);
    const sub = !trades ? "" : `<div class="sub ${cls}">${esc(solAmt(b.net_sol || 0) || "")}</div>`;
    return `<li><span class="rank${i < 3 ? " top" : ""}">${i + 1}</span><div><div class="name">${esc(name)}</div>${trades ? `<div class="sub">${b.wins || 0}W · ${b.losses || 0}L</div>` : ""}</div><div class="${cls}">${esc(main)}${sub}</div></li>`;
  }).join("");
}
function paint() {
  fresh(feed && feed.generated_at);
  renderFeed();
  renderBoard();
}
async function load() {
  try {
    const [f, p] = await Promise.all([
      fetch("../feed.json?" + Date.now(), { cache: "no-store" }).then((r) => r.json()),
      fetch("../pnl.json?" + Date.now(), { cache: "no-store" }).then((r) => r.json()),
    ]);
    feed = f;
    pnl = p;
    paint();
  } catch (e) {
    console.warn(e);
  }
}
$("#ca").textContent = CA;
load();
setInterval(load, 45000);
setInterval(() => { if (feed) paint(); }, 15000);
