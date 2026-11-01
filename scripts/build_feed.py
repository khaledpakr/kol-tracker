#!/usr/bin/env python3
"""KOL Tracker feed builder. Reads copytrade.py state + event logs -> feed.json.
Run after each copytrade.py cycle (or via run_loop.sh every few minutes)."""
import json, time, os, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
HIST = os.path.join(DATA, "trades_history.json"); CACHE = os.path.join(DATA, "token_cache.json")
STATE = os.path.join(DATA, "slingoor_state.json")
FEED = os.path.join(ROOT, "feed.json")
TRACKED = {"slingoor":"5YRgrP3mjGzrzirYYN5HAQH19cTYREYwGxW6XRJQUzij","Gfree":"4yo9CUuTBbds9NFhZd4MzPiZZkUvveXdTnAH8qMsE8ku",
 "POORGOAT___":"8k1sAmVUjzaZkxqexeYkCPphjcQobYugQeGmCyvKtHNG","marcell":"6vbrTLsWy76TxDQAUKLqZrPohQuq6EVaJgfGzR82paFa",
 "cwuhn4":"CwUHN4zTn5wiEYoZjsP4FrDvAT9heDWewCTQjhgwhJqS"}
def lj(p, d):
    try: return json.load(open(p))
    except Exception: return d
def num(*v):
    for x in v:
        if isinstance(x, (int, float)): return float(x)
    return None
def norm(e, t):
    w = e.get("wallet"); ty = str(e.get("type", "")).upper()
    if w not in TRACKED or "error" in e or not e.get("mint"): return []
    base = dict(wallet=w, mint=e["mint"], symbol=e.get("symbol"), time=e.get("time") or t, sig=e.get("sig"),
                mc=num(e.get("mc")), entry_mc=num(e.get("entry_mc")), pct_sold=num(e.get("pct_sold")))
    usdq = e.get("quote") == "USDC"
    out = []
    if "BUY" in ty:
        sol = None if usdq else num(e.get("sol"), e.get("sol_in"), e.get("buy_sol"), e.get("add_sol"))
        usd = num(e.get("usdc") if usdq else None, e.get("buy_usdc"), e.get("add_usdc"), e.get("usd") if "SELL" not in ty else None)
        out.append(dict(base, side="BUY", sol=sol, usd=usd, tokens=num(e.get("tokens")) if "SELL" not in ty else None, addon=bool(e.get("addon")) or "ADD" in ty))
    if "SELL" in ty:
        sol = None if usdq else num(e.get("sol_out"), e.get("sell_sol"), e.get("sol") if "BUY" not in ty else None)
        usd = num(e.get("usdc") if usdq else None, e.get("sell_usdc"), e.get("usd"))
        out.append(dict(base, side="SELL", sol=sol, usd=usd, tokens=num(e.get("tokens")) if "BUY" not in ty else None))
    return out
def key(t): return t.get("sig") and f'{t["sig"]}:{t["mint"]}:{t["side"]}' or f'{t["wallet"]}:{t["mint"]}:{t["side"]}:{round(t.get("sol") or t.get("usd") or 0,2)}:{t["time"]}'
def collect():
    os.makedirs(DATA, exist_ok=True)
    hist = {key(t): t for t in lj(HIST, [])}
    srcs = []
    log_path = os.path.join(DATA, "log.txt")
    events_path = os.path.join(DATA, "last_events.json")
    for line in open(log_path, errors="ignore") if os.path.exists(log_path) else []:
        line = line.strip()
        if line.startswith("{"):
            try: d = json.loads(line); srcs += [(e, d.get("time")) for e in d.get("events") or [] if isinstance(e, dict)]
            except Exception: pass
    m = os.path.getmtime(events_path) if os.path.exists(events_path) else time.time()
    srcs += [(e, int(m)) for e in lj(events_path, []) if isinstance(e, dict)]
    for e, t in srcs:
        for n in norm(e, t): hist.setdefault(key(n), n)
    out = sorted(hist.values(), key=lambda x: x.get("time") or 0)
    json.dump(out, open(HIST, "w")); return out
def enrich(mints):
    cache = lj(CACHE, {}); now = time.time()
    need = [m for m in mints if now - cache.get(m, {}).get("_t", 0) > 240]
    for i in range(0, len(need), 30):
        try:
            r = urllib.request.Request("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(need[i:i+30]), headers={"User-Agent": "kol-tracker"})
            pairs = json.load(urllib.request.urlopen(r, timeout=15))
        except Exception as ex: print("dex err", ex); continue
        best = {}
        for p in pairs:
            m = p["baseToken"]["address"]
            if m not in best or (p.get("liquidity") or {}).get("usd", 0) > (best[m].get("liquidity") or {}).get("usd", 0): best[m] = p
        for m in need[i:i+30]:
            p = best.get(m)
            cache[m] = {"_t": now} if not p else {"_t": now, "symbol": p["baseToken"].get("symbol"), "name": p["baseToken"].get("name"),
              "price_usd": num(p.get("priceUsd") and float(p["priceUsd"])), "price_native": num(p.get("priceNative") and float(p["priceNative"])),
              "mc": num(p.get("marketCap"), p.get("fdv")), "liq": (p.get("liquidity") or {}).get("usd"), "vol24": (p.get("volume") or {}).get("h24"),
              "chg24": (p.get("priceChange") or {}).get("h24"), "img": (p.get("info") or {}).get("imageUrl"), "dex": p.get("dexId")}
    json.dump(cache, open(CACHE, "w")); return cache
def pnl(trades, name):
    """Honest realized PnL: only SOL-quoted sells whose cost basis was observed as a SOL buy in our log."""
    basis = {}; realized = 0.0; matched = unmatched = wins = 0
    for t in trades:
        if t["wallet"] != name: continue
        b = basis.setdefault(t["mint"], {"sol": 0.0, "tok": 0.0})
        if t["side"] == "BUY" and t.get("sol"): b["sol"] += t["sol"]; b["tok"] += t.get("tokens") or 0
        elif t["side"] == "SELL":
            if t.get("sol") is None or b["sol"] <= 0: unmatched += 1; continue
            frac = (t["pct_sold"] / 100) if t.get("pct_sold") else (min(1, t["tokens"] / b["tok"]) if t.get("tokens") and b["tok"] else None)
            if frac is None: unmatched += 1; continue
            cost = b["sol"] * frac; r = t["sol"] - cost; realized += r; matched += 1; wins += r > 0
            b["sol"] -= cost; b["tok"] *= (1 - frac)
    return dict(realized_sol=round(realized, 3), matched_sells=matched, unmatched_sells=unmatched, win_rate=round(100 * wins / matched) if matched else None)
def main():
    os.makedirs(DATA, exist_ok=True)
    st = lj(STATE, {}); trades = collect()
    mints = {t["mint"] for t in trades[-150:]}
    for n in TRACKED: mints |= set((st.get(n) or {}).get("positions", {}).keys())
    cache = enrich(sorted(mints | {"So11111111111111111111111111111111111111112"}))
    solusd = cache.get("So11111111111111111111111111111111111111112", {}).get("price_usd")
    for t in trades:
        c = cache.get(t["mint"], {}); t["symbol"] = t.get("symbol") or c.get("symbol")
    callers = []
    for n, addr in TRACKED.items():
        s = st.get(n) or {}; pos = []
        for m, p in (s.get("positions") or {}).items():
            c = cache.get(m, {}); # value in SOL via USD price, capped at pool liquidity (a bag can't exit for more than the pool holds)
            val = min((p.get("tokens") or 0) * c["price_usd"], c.get("liq") or 0) / solusd if c.get("price_usd") and c.get("liq") and solusd else None
            pos.append(dict(mint=m, symbol=c.get("symbol"), name=c.get("name"), img=c.get("img"), sol_cost=round(p.get("sol", 0), 4),
              tokens=p.get("tokens"), entry_time=p.get("entry_time"), mc=c.get("mc"), liq=c.get("liq"), chg24=c.get("chg24"),
              value_sol=round(val, 4) if val is not None else None, unrealized_sol=round(val - p.get("sol", 0), 4) if val is not None else None))
        pos.sort(key=lambda x: -x["sol_cost"]); mine = [t for t in trades if t["wallet"] == n]
        callers.append(dict(name=n, address=addr, x=f"https://x.com/search?q={n}", baseline_at=s.get("baseline_at"), positions=pos,
          open_positions=len(pos), sol_in_open=round(sum(p["sol_cost"] for p in pos), 3),
          unrealized_sol=round(sum(p["unrealized_sol"] or 0 for p in pos), 3), trades=len(mine),
          buys=sum(t["side"] == "BUY" for t in mine), sells=sum(t["side"] == "SELL" for t in mine),
          last_trade=max([t["time"] or 0 for t in mine], default=None), **pnl(trades, n)))
    feed = dict(generated_at=int(time.time()), callers=callers, trades=list(reversed(trades))[:400],
      tokens={m: {k: v for k, v in c.items() if k != "_t"} for m, c in cache.items() if m in mints and len(c) > 1},
      totals=dict(callers=len(callers), trades=len(trades), open_positions=sum(c["open_positions"] for c in callers),
                  sol_in_open=round(sum(c["sol_in_open"] for c in callers), 2)))
    tmp = FEED + ".tmp"; json.dump(feed, open(tmp, "w")); os.replace(tmp, FEED)
    print("ok", len(callers), "callers", len(trades), "trades")
if __name__ == "__main__": main()
