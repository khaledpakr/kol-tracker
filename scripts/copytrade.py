import json, time, sys, os, urllib.request
from concurrent.futures import ThreadPoolExecutor
RPCS=["https://api.mainnet-beta.solana.com","https://solana-rpc.publicnode.com"]
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE=os.environ.get("CT_STATE",os.path.join(ROOT,"data","slingoor_state.json"))
SIG_CAP=int(os.environ.get("CT_SIG_CAP","1000"))   # max signatures scanned per wallet per run
BUDGET=float(os.environ.get("CT_BUDGET","210"))     # seconds; stop starting new work after this, save, print
WORKERS=int(os.environ.get("CT_WORKERS","4"))       # modest parallel getTransaction
BATCH=20
T0=time.time()
def save(st):
    os.makedirs(os.path.dirname(os.path.abspath(STATE)) or ".",exist_ok=True)
    tmp=STATE+".tmp"; json.dump(st,open(tmp,"w"),indent=1); os.replace(tmp,STATE)
def fetch_sigs(addr,until):
    """Page newest->older with `before` until reaching `until` (exclusive) or SIG_CAP. Returns (sigs newest-first, capped) or (None,False)."""
    out=[]; before=None
    while len(out)<SIG_CAP:
        p={"limit":min(1000,SIG_CAP-len(out)),"until":until}
        if before: p["before"]=before
        page=rpc("getSignaturesForAddress",[addr,p])
        if page is None:
            if not out: return None,False
            break
        out+=page
        if len(page)<p["limit"]: return out,False
        before=page[-1]["signature"]
    return out,len(out)>=SIG_CAP
def gettx(sig):
    return rpc("getTransaction",[sig,{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}])
# PAUSED (user request 2026-10-17, bestcook-only): {"slingoor":"5YRgrP3mjGzrzirYYN5HAQH19cTYREYwGxW6XRJQUzij","Gfree":"4yo9CUuTBbds9NFhZd4MzPiZZkUvveXdTnAH8qMsE8ku","POORGOAT___":"8k1sAmVUjzaZkxqexeYkCPphjcQobYugQeGmCyvKtHNG","marcell":"6vbrTLsWy76TxDQAUKLqZrPohQuq6EVaJgfGzR82paFa","cwuhn4":"CwUHN4zTn5wiEYoZjsP4FrDvAT9heDWewCTQjhgwhJqS","cupsey":"6DQAGJT7VZPVBsuG4kn3AvpyHCEi7B2RFFvMZdbqQqqP"}
WALLETS={"slingoor":"5YRgrP3mjGzrzirYYN5HAQH19cTYREYwGxW6XRJQUzij","Gfree":"4yo9CUuTBbds9NFhZd4MzPiZZkUvveXdTnAH8qMsE8ku","POORGOAT___":"8k1sAmVUjzaZkxqexeYkCPphjcQobYugQeGmCyvKtHNG","marcell":"6vbrTLsWy76TxDQAUKLqZrPohQuq6EVaJgfGzR82paFa","cwuhn4":"CwUHN4zTn5wiEYoZjsP4FrDvAT9heDWewCTQjhgwhJqS"}
IGNORE={"So11111111111111111111111111111111111111112","EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}
def rpc(method,params):
    for attempt in range(6):
        url=RPCS[attempt%len(RPCS)]
        try:
            req=urllib.request.Request(url,data=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode(),headers={"Content-Type":"application/json"})
            r=json.load(urllib.request.urlopen(req,timeout=25))
            if "error" in r: raise Exception(r["error"])
            return r["result"]
        except Exception as e:
            time.sleep(1.5*(attempt+1))
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
def main():
    st=json.load(open(STATE)) if os.path.exists(STATE) else {}
    events=[]
    for name,addr in WALLETS.items():
        s=st.setdefault(name,{"address":addr,"last_sig":None,"positions":{}})
        if s["last_sig"] is None:
            sigs=rpc("getSignaturesForAddress",[addr,{"limit":1}])
            if sigs: s["last_sig"]=sigs[0]["signature"]; s["baseline_at"]=int(time.time())
            continue
        if time.time()-T0>BUDGET: events.append({"wallet":name,"error":"time_budget_skipped"}); continue
        sigs,capped=fetch_sigs(addr,s["last_sig"])
        if sigs is None: events.append({"wallet":name,"error":"rpc_failed"}); continue
        if not sigs: continue
        if capped: events.append({"wallet":name,"error":"sig_cap_reached","scanned":len(sigs)})
        todo=list(reversed(sigs))  # oldest first; last_sig advances as we go
        for i in range(0,len(todo),BATCH):
            if time.time()-T0>BUDGET: events.append({"wallet":name,"error":"time_budget_partial","remaining":len(todo)-i}); break
            chunk=todo[i:i+BATCH]
            want=[sg for sg in chunk if not sg.get("err")]
            with ThreadPoolExecutor(WORKERS) as ex: txs=dict(zip([g["signature"] for g in want],ex.map(lambda g:gettx(g["signature"]),want)))
            for sg in want:
              tx=txs[sg["signature"]]
              for ev in parse(tx,addr):
                ev.update(wallet=name,sig=sg["signature"],time=sg.get("blockTime"))
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
                events.append(ev)
            s["last_sig"]=chunk[-1]["signature"]
            save(st)
    save(st)
    print(json.dumps(events,indent=1))
main()
# PAUSED (user request 2026-10-14 23:34): "thedetective":"6qudAN2kV8mtCcYJxb5QQ6Vr15itdHHdeVbYm99NKMhy"
