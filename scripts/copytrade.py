import json, time, sys, os, urllib.request
RPCS=["https://api.mainnet-beta.solana.com"]
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE=os.environ.get("CT_STATE",os.path.join(ROOT,"data","slingoor_state.json"))
MAX_PAGES=int(os.environ.get("CT_MAX_PAGES","16"))  # signature pages per slice; failed spam is skipped inside these
TX_CAP=int(os.environ.get("CT_TX_CAP","18"))        # getTransaction calls per wallet per run
LOOKBACK=int(os.environ.get("CT_LOOKBACK","21600")) # seconds of history to catch up; older gaps are left behind
BUDGET=float(os.environ.get("CT_BUDGET","160"))     # seconds; stop starting new work after this, save, print
T0=time.time()
def save(st):
    os.makedirs(os.path.dirname(os.path.abspath(STATE)) or ".",exist_ok=True)
    tmp=STATE+".tmp"; json.dump(st,open(tmp,"w"),indent=1); os.replace(tmp,STATE)
def gettx(sig):
    return rpc("getTransaction",[sig,{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}])
def page_sigs(addr,until=None,before=None,max_pages=MAX_PAGES):
    """Newest-first signatures. Failed transactions stay in the list but do not stop paging.
    Stops at `until`, a short page, the lookback floor, or max_pages. Returns (infos, reached, oldest_sig)."""
    out=[]; cursor=before; reached=False; floor=time.time()-LOOKBACK
    for _ in range(max_pages):
        if time.time()-T0>BUDGET: break
        opts={"limit":1000}
        if until: opts["until"]=until
        if cursor: opts["before"]=cursor
        page=rpc("getSignaturesForAddress",[addr,opts])
        if page is None: break
        if not page:
            reached=True; break
        out.extend(page)
        cursor=page[-1]["signature"]
        oldest=page[-1].get("blockTime") or 0
        if len(page)<1000 or (oldest and oldest<floor):
            reached=True; break
    return out, reached, cursor
def pick_unseen(infos, seen, cap):
    """Non-error signatures not yet fetched. Newest half keeps the feed current; oldest half drains spam backlogs."""
    todo=[i for i in infos if not i.get("err") and i["signature"] not in seen]
    if len(todo)<=cap: return todo
    n_new=max(1, cap//2); n_old=cap-n_new
    chosen=[]; have=set()
    for info in todo[:n_new]+todo[-n_old:]:
        sig=info["signature"]
        if sig not in have:
            chosen.append(info); have.add(sig)
    return chosen
def load_wallets():
    cfg=json.load(open(os.path.join(ROOT,"config","callers.json")))
    return {c["name"]:c["address"] for c in cfg["callers"]}
WALLETS=load_wallets()
IGNORE={"So11111111111111111111111111111111111111112","EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}
def rpc(method,params):
    payload=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    for attempt in range(6):
        if time.time()-T0>BUDGET+20: return None
        url=RPCS[attempt%len(RPCS)]
        try:
            req=urllib.request.Request(url,data=payload,headers={"Content-Type":"application/json"})
            r=json.load(urllib.request.urlopen(req,timeout=25))
            if "error" in r: raise Exception(r["error"])
            return r["result"]
        except Exception as e:
            wait=0.8*(attempt+1)
            if "429" in str(e) or "Too many" in str(e): wait=1.6*(attempt+1)
            time.sleep(wait)
    return None
def parse(tx,owner):
    if not tx or tx["meta"] is None or tx["meta"].get("err"): return []
    ak=tx["transaction"]["message"]["accountKeys"]
    if not any((k.get("pubkey")==owner and k.get("signer")) for k in ak if isinstance(k,dict)): return []
    m=tx["meta"]; keys=[k["pubkey"] if isinstance(k,dict) else k for k in tx["transaction"]["message"]["accountKeys"]]
    sol=0
    if owner in keys:
        i=keys.index(owner); sol=(m["postBalances"][i]-m["preBalances"][i])/1e9
    bal={}
    for side,arr in (("pre",m.get("preTokenBalances") or []),("post",m.get("postTokenBalances") or [])):
        for b in arr:
            if b.get("owner")!=owner: continue
            d=bal.setdefault(b["mint"],{"pre":0,"post":0})
            d[side]+=float(b["uiTokenAmount"].get("uiAmount") or 0)
    # wSOL change counts as SOL
    w=bal.get("So11111111111111111111111111111111111111112")
    if w: sol+=w["post"]-w["pre"]
    u=bal.get("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"); usdc=(u["post"]-u["pre"]) if u else 0
    out=[]
    for mint,d in bal.items():
        if mint in IGNORE: continue
        delta=d["post"]-d["pre"]
        if abs(delta)<1e-9: continue
        if delta>0 and usdc<-0.5: out.append({"type":"BUY","quote":"USDC","mint":mint,"tokens":delta,"sol":-usdc,"usdc":-usdc,"pre":d["pre"],"post":d["post"]})
        elif delta<0 and usdc>0.5: out.append({"type":"SELL","quote":"USDC","mint":mint,"tokens":-delta,"sol":usdc,"usdc":usdc,"pre":d["pre"],"post":d["post"]})
        elif delta>0 and sol<-0.001: out.append({"type":"BUY","mint":mint,"tokens":delta,"sol":-sol,"pre":d["pre"],"post":d["post"]})
        elif delta<0 and sol>0.0005: out.append({"type":"SELL","mint":mint,"tokens":-delta,"sol":sol,"pre":d["pre"],"post":d["post"]})
    return out
def mark(seen_list, seen, sig):
    if sig not in seen:
        seen.add(sig); seen_list.append(sig)
def record(s, addr, name, info, tx, events):
    if not tx: return 0
    n=0
    for ev in parse(tx, addr):
        ev.update(wallet=name, sig=info["signature"], time=info.get("blockTime"))
        p=s["positions"].get(ev["mint"])
        if ev["type"]=="BUY":
            if p: p["tokens"]+=ev["tokens"]; p["sol"]+=ev["sol"]
            else: s["positions"][ev["mint"]]={"tokens":ev["tokens"],"sol":ev["sol"],"entry_time":ev["time"],"held_before":ev["pre"]}
        else:
            ev["pct_sold"]=100*ev["tokens"]/ev["pre"] if ev["pre"]>0 else None
            if p and p["tokens"]>0 and p["sol"]>0:
                entry_px=p["sol"]/p["tokens"]; ev["multiple"]=(ev["sol"]/ev["tokens"])/entry_px
            if ev["post"]<=1e-6: s["positions"].pop(ev["mint"],None)
            elif p: frac=ev["tokens"]/max(ev["pre"],1e-12); p["tokens"]*=(1-frac); p["sol"]*=(1-frac)
        events.append(ev); n+=1
    return n
def fetch_some(addr, infos, seen_list, seen, cap):
    """Download up to `cap` unseen successful signatures. Failed spam is not fetched. RPC misses are retried next run."""
    for info in pick_unseen(infos, seen, cap):
        if time.time()-T0>BUDGET: break
        tx=gettx(info["signature"])
        if tx is None: continue
        mark(seen_list, seen, info["signature"])
        yield info, tx
def unfinished(infos, seen):
    return any(not i.get("err") and i["signature"] not in seen for i in infos)
def settle_edge(s, addr, name, info, seen_list, seen, events):
    """`before`/`until` are exclusive, so the cursor signature itself must already be resolved."""
    if not info: return None
    if info.get("err") or info["signature"] in seen: return info["signature"]
    tx=gettx(info["signature"])
    if tx is None: return None
    mark(seen_list, seen, info["signature"])
    record(s, addr, name, info, tx, events)
    return info["signature"]
def consume(s, addr, name, infos, seen_list, seen, cap, events):
    fetched=swaps=0
    for info, tx in fetch_some(addr, infos, seen_list, seen, cap):
        fetched+=1; swaps+=record(s, addr, name, info, tx, events)
    return fetched, swaps
def main():
    st=json.load(open(STATE)) if os.path.exists(STATE) else {}
    events=[]
    for name,addr in WALLETS.items():
        s=st.setdefault(name,{"address":addr,"last_sig":None,"positions":{}})
        if time.time()-T0>BUDGET:
            events.append({"wallet":name,"error":"time_budget_skipped"}); print(name,"skipped budget",file=sys.stderr,flush=True); continue
        seen_list=list(s.get("seen") or []); seen=set(seen_list)
        # Live window: chain tip down to the backlog cursor, or to the last fully synced signature.
        live_until=s.get("scan_before") or s.get("last_sig")
        live, live_done, _=page_sigs(addr, until=live_until, max_pages=8)
        fetched, swaps=consume(s, addr, name, live, seen_list, seen, TX_CAP, events)
        if live_done and not unfinished(live, seen):
            if s.get("scan_before"):
                older, older_done, _=page_sigs(addr, until=s.get("last_sig"), before=s["scan_before"])
                f2, s2=consume(s, addr, name, older, seen_list, seen, max(4, TX_CAP//3), events)
                fetched+=f2; swaps+=s2
                if older_done and not unfinished(older, seen) and live:
                    s["last_sig"]=live[0]["signature"]; s.pop("scan_before", None)
                    if not s.get("baseline_at"): s["baseline_at"]=int(time.time())
                elif older:
                    edge=settle_edge(s, addr, name, older[-1], seen_list, seen, events)
                    if edge: s["scan_before"]=edge
            elif live:
                s["last_sig"]=live[0]["signature"]
                if not s.get("baseline_at"): s["baseline_at"]=int(time.time())
        elif live and not s.get("scan_before") and not live_done:
            edge=settle_edge(s, addr, name, live[-1], seen_list, seen, events)
            if edge: s["scan_before"]=edge
        s["seen"]=seen_list[-4000:]
        save(st)
        print(name,"listed",len(live),"err",sum(1 for i in live if i.get("err")),"fetched",fetched,"swaps",swaps,"settled",s.get("scan_before") is None,file=sys.stderr,flush=True)
    save(st)
    print(json.dumps(events,indent=1))
main()
# PAUSED (user request 2026-10-14 23:34): "thedetective":"6qudAN2kV8mtCcYJxb5QQ6Vr15itdHHdeVbYm99NKMhy"
