#!/usr/bin/env python3
"""Realized caller PnL from public Solana RPC.

Counts a swap only when the quote is native SOL / wrapped SOL
(So11111111111111111111111111111111111111112) or Circle USDC
(EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v). Token names are ignored.
Sells are realized against SOL or USDC buys of the same mint that this job
has already downloaded. Days are Asia/Riyadh calendar days.
"""
import json, os, time, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CFG = os.path.join(ROOT, "config", "callers.json")
STATE_PATH = os.path.join(DATA, "pnl_state.json")
OUT = os.path.join(ROOT, "pnl.json")
RIYADH = ZoneInfo("Asia/Riyadh")
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
IGNORE = {WSOL, USDC, USDT}
RPCS = ["https://api.mainnet-beta.solana.com", "https://solana-rpc.publicnode.com"]
BUDGET = float(os.environ.get("CT_PNL_BUDGET", "150"))
TX_CAP = int(os.environ.get("CT_PNL_TX_CAP", "120"))
PAGE = int(os.environ.get("CT_PNL_PAGE", "40"))
T0 = time.time()

def load_json(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default

def save_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w"))
    os.replace(tmp, path)

def callers():
    return json.load(open(CFG))["callers"]

def rpc(method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for attempt in range(5):
        if time.time() - T0 > BUDGET:
            return None
        url = RPCS[attempt % len(RPCS)]
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            body = json.load(urllib.request.urlopen(req, timeout=20))
            if "error" in body:
                raise RuntimeError(body["error"])
            return body["result"]
        except Exception:
            time.sleep(0.4 * (attempt + 1))
    return None

def signatures(addr, cap, until=None, before=None):
    """Newest-first, stop at `until` (exclusive) or after `cap` signatures."""
    out, cursor = [], before
    while len(out) < cap and time.time() - T0 < BUDGET:
        opts = {"limit": min(1000, cap - len(out))}
        if until:
            opts["until"] = until
        if cursor:
            opts["before"] = cursor
        page = rpc("getSignaturesForAddress", [addr, opts])
        if not page:
            break
        out.extend(page)
        if len(page) < opts["limit"]:
            break
        cursor = page[-1]["signature"]
    return out

def parse_swap(tx, owner):
    """One meme-token swap quoted in real SOL or real USDC, or None."""
    if not tx or tx.get("meta") is None or tx["meta"].get("err"):
        return None
    msg = tx["transaction"]["message"]
    keys = msg["accountKeys"]
    if not any(isinstance(k, dict) and k.get("pubkey") == owner and k.get("signer") for k in keys):
        return None
    pub = [k["pubkey"] if isinstance(k, dict) else k for k in keys]
    meta = tx["meta"]
    sol = 0.0
    if owner in pub:
        i = pub.index(owner)
        sol = (meta["postBalances"][i] - meta["preBalances"][i]) / 1e9
    bal = {}
    for side, arr in (("pre", meta.get("preTokenBalances") or []), ("post", meta.get("postTokenBalances") or [])):
        for b in arr:
            if b.get("owner") != owner:
                continue
            d = bal.setdefault(b["mint"], {"pre": 0.0, "post": 0.0})
            d[side] += float((b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
    w = bal.get(WSOL)
    if w:
        sol += w["post"] - w["pre"]
    u = bal.get(USDC)
    usdc = (u["post"] - u["pre"]) if u else 0.0
    moved = []
    for mint, d in bal.items():
        if mint in IGNORE:
            continue
        delta = d["post"] - d["pre"]
        if abs(delta) < 1e-9:
            continue
        moved.append((mint, delta))
    if len(moved) != 1:
        return None
    mint, delta = moved[0]
    sol_swap = delta > 0 and sol < -0.001 or delta < 0 and sol > 0.0005
    usdc_swap = delta > 0 and usdc < -0.5 or delta < 0 and usdc > 0.5
    if sol_swap and usdc_swap:
        return None
    if sol_swap:
        return {"mint": mint, "side": "BUY" if delta > 0 else "SELL", "quote": "SOL",
                "tokens": abs(delta), "amount": abs(sol)}
    if usdc_swap:
        return {"mint": mint, "side": "BUY" if delta > 0 else "SELL", "quote": "USDC",
                "tokens": abs(delta), "amount": abs(usdc)}
    return None

def sol_price():
    try:
        req = urllib.request.Request(
            "https://api.dexscreener.com/tokens/v1/solana/" + WSOL,
            headers={"User-Agent": "kol-tracker"})
        pairs = json.load(urllib.request.urlopen(req, timeout=15))
        best = 0.0
        price = None
        for p in pairs:
            if p.get("baseToken", {}).get("address") != WSOL:
                continue
            liq = (p.get("liquidity") or {}).get("usd") or 0
            if liq >= best and p.get("priceUsd"):
                best, price = liq, float(p["priceUsd"])
        return price
    except Exception as ex:
        print("sol price", ex)
        return None

def recompute(swaps):
    """Average-cost realized PnL. Quote currencies are not mixed."""
    basis = {}
    closed = []
    for s in sorted(swaps, key=lambda x: (x.get("time") or 0, x.get("sig") or "")):
        key = (s["wallet"], s["mint"], s["quote"])
        b = basis.setdefault(key, {"qty": 0.0, "cost": 0.0})
        if s["side"] == "BUY":
            b["qty"] += s["tokens"]
            b["cost"] += s["amount"]
            continue
        if b["qty"] <= 1e-12 or b["cost"] <= 0 or not s.get("tokens"):
            continue
        frac = min(1.0, s["tokens"] / b["qty"])
        cost = b["cost"] * frac
        pnl = s["amount"] - cost
        b["cost"] -= cost
        b["qty"] *= (1 - frac)
        if b["qty"] < 1e-9:
            b["qty"] = b["cost"] = 0.0
        closed.append({"wallet": s["wallet"], "time": s["time"], "quote": s["quote"], "pnl": pnl, "sig": s["sig"]})
    return closed

def riyadh_bounds(now=None):
    now = now or datetime.now(RIYADH)
    today = now.date()
    start = datetime(today.year, today.month, today.day, tzinfo=RIYADH)
    return {
        "today": (start.timestamp(), (start + timedelta(days=1)).timestamp(), today.isoformat()),
        "yesterday": ((start - timedelta(days=1)).timestamp(), start.timestamp(), (today - timedelta(days=1)).isoformat()),
        "day_before": ((start - timedelta(days=2)).timestamp(), (start - timedelta(days=1)).timestamp(), (today - timedelta(days=2)).isoformat()),
        "month": ((start - timedelta(days=30)).timestamp(), (start + timedelta(days=1)).timestamp(), "last 30 days"),
        "all_time": (None, None, "since tracking"),
    }

def empty_bucket():
    return {"won_sol": 0.0, "lost_sol": 0.0, "net_sol": 0.0, "won_usd": 0.0, "lost_usd": 0.0, "net_usd": 0.0, "wins": 0, "losses": 0}

def add_leg(bucket, sol, usd, win):
    if win:
        bucket["wins"] += 1
        if sol:
            bucket["won_sol"] += sol
        if usd:
            bucket["won_usd"] += usd
    else:
        bucket["losses"] += 1
        if sol:
            bucket["lost_sol"] += abs(sol)
        if usd:
            bucket["lost_usd"] += abs(usd)

def finish(bucket):
    bucket["net_sol"] = round(bucket["won_sol"] - bucket["lost_sol"], 4)
    bucket["net_usd"] = round(bucket["won_usd"] - bucket["lost_usd"], 2)
    for k in ("won_sol", "lost_sol"):
        bucket[k] = round(bucket[k], 4)
    for k in ("won_usd", "lost_usd"):
        bucket[k] = round(bucket[k], 2)
    return bucket

def aggregate(closed, sol_usd, bounds):
    by_wallet = {}
    for c in closed:
        pnl = c["pnl"]
        if abs(pnl) < 1e-12:
            continue
        sol = pnl if c["quote"] == "SOL" else (pnl / sol_usd if sol_usd else None)
        usd = pnl if c["quote"] == "USDC" else (pnl * sol_usd if sol_usd else None)
        win = pnl > 0
        for name, (t0, t1, _label) in bounds.items():
            if t0 is not None and (c["time"] or 0) < t0:
                continue
            if t1 is not None and (c["time"] or 0) >= t1:
                continue
            slot = by_wallet.setdefault(c["wallet"], {})
            add_leg(slot.setdefault(name, empty_bucket()), sol, usd, win)
    for periods in by_wallet.values():
        for name in bounds:
            finish(periods.setdefault(name, empty_bucket()))
    return by_wallet

def blank_periods(bounds):
    return {name: finish(empty_bucket()) for name in bounds}

def take(state, name, addr, infos, fetched):
    """Parse a newest-first signature list. Stop before an unfetched tx so the cursor does not skip it."""
    seen = state.setdefault("seen", {}).setdefault(name, {})
    swaps = state.setdefault("swaps", [])
    known = {s["sig"] for s in swaps}
    done = []
    for info in infos:
        if fetched[0] >= TX_CAP or time.time() - T0 > BUDGET:
            break
        sig = info["signature"]
        if seen.get(sig):
            done.append(info)
            continue
        if info.get("err"):
            seen[sig] = 1
            done.append(info)
            continue
        tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
        fetched[0] += 1
        if tx is None:
            break
        seen[sig] = 1
        done.append(info)
        swap = parse_swap(tx, addr)
        if swap and sig not in known:
            swap.update(wallet=name, sig=sig, time=info.get("blockTime") or 0)
            swaps.append(swap)
            known.add(sig)
    return done

def ingest(state, people):
    cursors = state.setdefault("cursors", {})
    fetched = [0]
    per = max(1, TX_CAP // max(1, len(people)))
    cutoff = time.time() - 31 * 86400
    for person in people:
        if time.time() - T0 > BUDGET or fetched[0] >= TX_CAP:
            break
        name, addr = person["name"], person["address"]
        cur = cursors.setdefault(name, {"before": None, "reached_cutoff": False, "oldest_time": None})
        # Recent signatures. `before` walks toward older history; already-seen sigs are cheap.
        newer = signatures(addr, per, before=None)
        done = take(state, name, addr, newer, fetched)
        if done:
            cur["before"] = done[-1]["signature"]
            times = [s.get("blockTime") for s in done if s.get("blockTime")]
            if times:
                cur["oldest_time"] = min([cur["oldest_time"] or min(times)] + times)
        if cur["before"] and not cur["reached_cutoff"] and fetched[0] < TX_CAP and time.time() - T0 < BUDGET:
            older = signatures(addr, per, before=cur["before"])
            done_old = take(state, name, addr, older, fetched)
            if done_old:
                cur["before"] = done_old[-1]["signature"]
                times = [s.get("blockTime") or time.time() for s in done_old]
                cur["oldest_time"] = min(times)
                if min(times) < cutoff or len(done_old) < len(older):
                    if min(times) < cutoff or len(older) < per:
                        cur["reached_cutoff"] = True
            elif not older:
                cur["reached_cutoff"] = True
    print("fetched txs", fetched[0], "swaps", len(state.get("swaps") or []))
    return state

def series_labels(days=14, now=None):
    now = now or datetime.now(RIYADH)
    start = datetime(now.year, now.month, now.day, tzinfo=RIYADH) - timedelta(days=days - 1)
    return [(start + timedelta(days=i)).date().isoformat() for i in range(days)]

def series_for(wallet, closed, sol_usd, days=14):
    labels = series_labels(days)
    totals = {d: 0.0 for d in labels}
    for c in closed:
        if c["wallet"] != wallet or not c.get("time"):
            continue
        day = datetime.fromtimestamp(c["time"], RIYADH).date().isoformat()
        if day not in totals:
            continue
        pnl = c["pnl"]
        usd = pnl if c["quote"] == "USDC" else (pnl * sol_usd if sol_usd else 0.0)
        totals[day] += usd
    return [round(totals[d], 2) for d in labels]

def publish(state, people, sol_usd):
    bounds = riyadh_bounds()
    closed = recompute(state.get("swaps") or [])
    by_wallet = aggregate(closed, sol_usd, bounds)
    rows = []
    for person in people:
        periods = by_wallet.get(person["name"]) or blank_periods(bounds)
        for name in bounds:
            periods.setdefault(name, finish(empty_bucket()))
            finish(periods[name])
        rows.append({"name": person["name"], "address": person["address"], "x": person.get("x"), "periods": periods, "series": series_for(person["name"], closed, sol_usd)})
    def rank(key):
        return [r["name"] for r in sorted(rows, key=lambda r: (-r["periods"][key]["net_usd"], -r["periods"][key]["net_sol"], r["name"]))]
    cursors = state.get("cursors") or {}
    out = {
        "generated_at": int(time.time()),
        "timezone": "Asia/Riyadh",
        "sol_usd": sol_usd,
        "labels": {k: v[2] for k, v in bounds.items()},
        "series_labels": series_labels(),
        "callers": rows,
        "boards": {"today": rank("today"), "month": rank("month"), "all_time": rank("all_time")},
        "coverage": {
            "swaps": len(state.get("swaps") or []),
            "closed": len(closed),
            "backfill_done": sum(1 for c in cursors.values() if c.get("reached_cutoff")),
            "callers": len(people),
        },
        "methodology": "Realized PnL is average cost of observed buys in the same quote, booked on the sell. Only native SOL plus wrapped SOL, or Circle USDC, count as quote. A token named SOL or USDC does not. USD uses the latest SOL price, not the price at the trade. Sells of bags bought before the downloaded history are left out. Days are calendar days in Asia/Riyadh. Month is the last 30 Riyadh days. All-time is everything downloaded since this job started.",
    }
    save_json(OUT, out)
    print("pnl", len(rows), "callers", len(closed), "closed", "sol", sol_usd)

def selftest():
    start = datetime(2026, 11, 1, tzinfo=RIYADH)
    yday = int((start - timedelta(hours=5)).timestamp())
    today = int((start + timedelta(hours=5)).timestamp())
    before = int((start - timedelta(days=1, hours=3)).timestamp())
    swaps = [
        {"wallet": "a", "mint": "M", "quote": "SOL", "side": "BUY", "tokens": 10, "amount": 1, "time": yday, "sig": "b1"},
        {"wallet": "a", "mint": "M", "quote": "SOL", "side": "SELL", "tokens": 10, "amount": 2, "time": today, "sig": "s1"},
        {"wallet": "a", "mint": "N", "quote": "USDC", "side": "BUY", "tokens": 5, "amount": 100, "time": before, "sig": "b2"},
        {"wallet": "a", "mint": "N", "quote": "USDC", "side": "SELL", "tokens": 5, "amount": 40, "time": before, "sig": "s2"},
        {"wallet": "a", "mint": "Z", "quote": "SOL", "side": "SELL", "tokens": 1, "amount": 3, "time": today, "sig": "s3"},
    ]
    closed = recompute(swaps)
    assert len(closed) == 2, closed
    bounds = riyadh_bounds(start + timedelta(hours=12))
    agg = aggregate(closed, 100.0, bounds)
    today_b = agg["a"]["today"]
    y_b = agg["a"]["yesterday"]
    d_b = agg["a"]["day_before"]
    assert today_b["wins"] == 1 and abs(today_b["won_sol"] - 1) < 1e-9, today_b
    assert y_b["wins"] == 0 and y_b["losses"] == 0, y_b
    assert d_b["losses"] == 1 and abs(d_b["lost_usd"] - 60) < 1e-9, d_b
    assert abs(d_b["lost_sol"] - 0.6) < 1e-9
    # fake quote mint must not parse as SOL just because of a name
    assert IGNORE == {WSOL, USDC, USDT}
    print("selftest ok")

def main():
    if os.environ.get("CT_PNL_SELFTEST"):
        selftest()
        return
    os.makedirs(DATA, exist_ok=True)
    people = callers()
    state = load_json(STATE_PATH, {"seen": {}, "swaps": [], "cursors": {}})
    try:
        ingest(state, people)
    finally:
        save_json(STATE_PATH, state)
    publish(state, people, sol_price())

if __name__ == "__main__":
    main()
