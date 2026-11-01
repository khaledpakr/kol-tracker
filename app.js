const T={en:{nav_home:"Home",nav_feed:"Live Feed",nav_lb:"Leaderboard",nav_pnl:"PnL",nav_coins:"Top Coins",nav_token:"$KOLT",
disc:"Data from public on-chain activity and DexScreener. Not financial advice. DYOR.",hero_pill:"● Live on-chain tracking · Solana",
hero_t:'Follow the <span>smart money</span> on pump.fun',hero_p:"KOL Tracker watches top pump.fun callers' wallets and shows every buy and sell as it happens, plus the hottest Solana coins right now.",
cta_feed:"Open live feed",cta_coins:"Trending coins",s_callers:"Callers tracked",s_trades:"Trades logged",s_open:"Open positions",s_sol:"SOL in open bags",
latest:"Latest caller trades",all:"View all →",callers:"Callers",side:"Side",coin:"Coin",amount:"Amount",mc:"Market cap",time:"Time",links:"Links",caller:"Caller",
lb:"Caller leaderboard",lb_sub:"Ranked by realized PnL (SOL) from observed trades",realized:"Realized PnL",winr:"Win rate",unreal:"Unrealized (est.)",
trades:"Trades",open:"Open",invested:"SOL in open",top:"Top coins",top_sub:"Live from DexScreener · Solana · refreshes every 45s",
boosted:"Top boosted",latestp:"New profiles",pumpq:"pump.fun search",price:"Price",vol:"Vol 24h",liq:"Liquidity",chg:"24h",
positions:"Open positions",history:"Trade history",entry:"Entry",cost:"Cost (SOL)",value:"Value (SOL)",all_c:"All",buys:"Buys",sells:"Sells",
pnl_note:"Realized PnL counts only SOL-quoted sells whose buy was also observed by the tracker (cost basis prorated by % sold). USDC trades and sells of bags bought before tracking began are excluded. Values are estimates.",
tok_t:"$KOLT — coming soon",tok_p:"The KOL Tracker community token has not launched. No presale and no contract address yet.",
tok_n:"Nothing here is a promise of value, returns or utility.",follow:"Follow on X",updated:"updated",ago:"ago",none:"No data yet",loading:"Loading…",back:"← Back",wallet:"Wallet"}};
let L="en",F=null,seen=new Set(),coins={tab:"boosted",data:[]},filt="ALL";
const t=k=>T[L][k]||k,$=s=>document.querySelector(s);
const fm=n=>n==null||isNaN(n)?"—":Math.abs(n)>=1e9?(n/1e9).toFixed(2)+"B":Math.abs(n)>=1e6?(n/1e6).toFixed(2)+"M":Math.abs(n)>=1e3?(n/1e3).toFixed(1)+"K":(+n).toFixed(2);
const usd=n=>n==null?"—":"$"+fm(n),sol=n=>n==null?"—":(+n).toFixed(Math.abs(n)<10?3:1)+" ◎";
const px=n=>n==null?"—":n<0.0001?"$"+(+n).toExponential(2):"$"+(+n).toPrecision(4);
const pc=n=>n==null?"—":`<span class="${n>=0?"up":"dn"}">${n>=0?"+":""}${(+n).toFixed(1)}%</span>`;
const ago=s=>{if(!s)return"—";const d=Date.now()/1e3-s;const r=d<60?Math.floor(d)+"s":d<3600?Math.floor(d/60)+"m":d<86400?Math.floor(d/3600)+"h":Math.floor(d/86400)+"d";return r+" ago"};
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const short=a=>a?a.slice(0,4)+"…"+a.slice(-4):"";
const links=(m,sig)=>`<span class="lk"><a target="_blank" rel="noopener" href="https://dexscreener.com/solana/${m}">Dex</a><a target="_blank" rel="noopener" href="https://pump.fun/coin/${m}">pump</a><a target="_blank" rel="noopener" href="https://solscan.io/${sig?"tx/"+sig:"token/"+m}">Solscan</a></span>`;
const coinCell=(m,sym,img)=>{const tk=F?.tokens?.[m]||{};img=img||tk.img;sym=sym||tk.symbol||short(m);return `<div class="coin">${img?`<img loading="lazy" src="${esc(img)}" onerror="this.remove()">`:`<span class="av">${esc(sym[0]||"?")}</span>`}<div><b>${esc(sym)}</b><div class="addr">${short(m)}</div></div></div>`};
const amt=x=>x.sol!=null?sol(x.sol):x.usd!=null?usd(x.usd):"—";
function tradeRows(list,showCaller=true){if(!list.length)return`<tr><td colspan=7 class=muted>${t("none")}</td></tr>`;return list.map(x=>{const k=(x.sig||"")+x.mint+x.side+x.time,n=F&&!seen.has(k);seen.add(k);const mc=x.mc??F.tokens?.[x.mint]?.mc;
return`<tr class="${n&&seen.size>1?"":""}"><td><span class="tag ${x.side}">${x.side=="BUY"?"BUY":"SELL"}</span>${x.pct_sold&&x.side=="SELL"?` <small class=muted>${Math.round(x.pct_sold)}%</small>`:""}</td>${showCaller?`<td><a href="#/caller/${x.wallet}"><b>${esc(x.wallet)}</b></a></td>`:""}<td>${coinCell(x.mint,x.symbol)}</td><td><b>${amt(x)}</b></td><td>${usd(mc)}</td><td class=muted>${ago(x.time)}</td><td>${links(x.mint,x.sig)}</td></tr>`}).join("")}
const tradeHead=(c=true)=>`<thead><tr><th>${t("side")}</th>${c?`<th>${t("caller")}</th>`:""}<th>${t("coin")}</th><th>${t("amount")}</th><th>${t("mc")}</th><th>${t("time")}</th><th>${t("links")}</th></tr></thead>`;
function ranked(){return [...F.callers].sort((a,b)=>b.realized_sol-a.realized_sol||b.trades-a.trades)}
function lbTable(){return`<div class="glass tw"><table class=tbl><thead><tr><th>#</th><th>${t("caller")}</th><th>${t("realized")}</th><th>${t("winr")}</th><th class=hide-m>${t("unreal")}</th><th>${t("trades")}</th><th>${t("open")}</th><th class=hide-m>${t("invested")}</th></tr></thead><tbody>${ranked().map((c,i)=>`<tr onclick="location.hash='#/caller/${c.name}'" style=cursor:pointer><td class="rank r${i+1}">${i+1}</td><td><div class=coin><span class=av>${c.name[0]}</span><div><b>${esc(c.name)}</b><div class=addr>${short(c.address)}</div></div></div></td><td class="${c.realized_sol>=0?"up":"dn"}"><b>${c.realized_sol>=0?"+":""}${sol(c.realized_sol)}</b><div class=addr>${c.matched_sells} matched</div></td><td>${c.win_rate==null?"—":c.win_rate+"%"}</td><td class="hide-m ${c.unrealized_sol>=0?"up":"dn"}">${sol(c.unrealized_sol)}</td><td>${c.trades}</td><td>${c.open_positions}</td><td class=hide-m>${sol(c.sol_in_open)}</td></tr>`).join("")}</tbody></table></div><div class=note>${t("pnl_note")}</div>`}
const V={
home(){const o=F.totals;return`${pnlHome()}<section><div class=stats>${[[o.callers,"s_callers"],[o.trades,"s_trades"],[o.open_positions,"s_open"],[fm(o.sol_in_open)+" ◎","s_sol"]].map(([v,k])=>`<div class="glass stat"><b>${v}</b><span>${t(k)}</span></div>`).join("")}</div></section>
<section><h2>⚡ ${t("latest")} <a href="#/feed" style="margin-inline-start:auto;font-size:14px">${t("all")}</a></h2><div class="glass tw"><table class=tbl>${tradeHead()}<tbody>${tradeRows(F.trades.slice(0,10))}</tbody></table></div></section>
<section><h2>🏆 ${t("lb")}</h2>${lbTable()}</section>
<section><h2>👥 ${t("callers")}</h2><div class=cards>${F.callers.map(callerCard).join("")}</div></section>
<section id=coinsec>${coinsBlock()}</section>${tokenBlock()}`},
feed(){const l=F.trades.filter(x=>filt=="ALL"||x.side==filt||x.wallet==filt);return`<section><h2>⚡ ${t("nav_feed")}</h2><div class=filters>${["ALL","BUY","SELL",...F.callers.map(c=>c.name)].map(f=>`<button class="${f==filt?"on":""}" onclick="filt='${f}';render()">${f=="ALL"?t("all_c"):f=="BUY"?t("buys"):f=="SELL"?t("sells"):f}</button>`).join("")}</div><div class="glass tw"><table class=tbl>${tradeHead()}<tbody>${tradeRows(l.slice(0,200))}</tbody></table></div></section>`},
leaderboard(){return`${pnlBoards()}<section><h2>🏆 ${t("lb")}</h2><p class=muted>${t("lb_sub")}</p>${lbTable()}</section>`},
pnl(){return pnlHome()+pnlBoards()},
coins(){return`<section id=coinsec>${coinsBlock()}</section>`},
token(){return tokenBlock()},
caller(n){const c=F.callers.find(c=>c.name==n);if(!c)return`<p>${t("none")}</p>`;const h=F.trades.filter(x=>x.wallet==n);
return`<section><a href="#/leaderboard">${t("back")}</a><div class="glass card" style="margin-top:12px"><div class=coin><span class=av>${c.name[0]}</span><div><h1>${esc(c.name)}</h1><a class=addr target=_blank href="https://solscan.io/account/${c.address}">${c.address}</a></div></div>
<div class=stats>${[[(c.realized_sol>=0?"+":"")+sol(c.realized_sol),t("realized")],[c.win_rate==null?"—":c.win_rate+"%",t("winr")],[sol(c.unrealized_sol),t("unreal")],[c.trades,t("trades")]].map(([v,k])=>`<div class="glass stat"><b>${v}</b><span>${k}</span></div>`).join("")}</div><div class=note>${t("pnl_note")}</div></div></section>
<section><h2>📂 ${t("positions")} (${c.open_positions})</h2><div class="glass tw"><table class=tbl><thead><tr><th>${t("coin")}</th><th>${t("cost")}</th><th>${t("value")}</th><th>PnL</th><th>${t("mc")}</th><th>${t("chg")}</th><th>${t("entry")}</th><th>${t("links")}</th></tr></thead><tbody>${c.positions.length?c.positions.map(p=>`<tr><td>${coinCell(p.mint,p.symbol,p.img)}</td><td>${sol(p.sol_cost)}</td><td>${sol(p.value_sol)}</td><td class="${(p.unrealized_sol||0)>=0?"up":"dn"}">${p.unrealized_sol==null?"—":sol(p.unrealized_sol)}</td><td>${usd(p.mc)}</td><td>${pc(p.chg24)}</td><td class=muted>${ago(p.entry_time)}</td><td>${links(p.mint)}</td></tr>`).join(""):`<tr><td colspan=8 class=muted>${t("none")}</td></tr>`}</tbody></table></div></section>
<section><h2>🕘 ${t("history")}</h2><div class="glass tw"><table class=tbl>${tradeHead(false)}<tbody>${tradeRows(h,false)}</tbody></table></div></section>`}};
function callerCard(c){return`<a class="glass card" href="#/caller/${c.name}" style="color:inherit"><div class=coin><span class=av>${c.name[0]}</span><div><h3>${esc(c.name)}</h3><div class=addr>${short(c.address)}</div></div></div><div class=kv><div><span>${t("realized")}</span><b class="${c.realized_sol>=0?"up":"dn"}">${sol(c.realized_sol)}</b></div><div><span>${t("open")}</span><b>${c.open_positions}</b></div><div><span>${t("trades")}</span><b>${c.trades}</b></div><div><span>${t("time")}</span><b>${ago(c.last_trade)}</b></div></div></a>`}
function tokenBlock(){return`<section><div class="glass token"><img class="token-logo" src="kolt-logo.jpg" alt="" width="40" height="40"><h2>${t("tok_t")}</h2><p class=muted style="max-width:620px;margin:0 auto 8px">${t("tok_p")}</p><p class=muted style="font-size:12px">${t("tok_n")}</p></div></section>`}
function coinsBlock(){const d=coins.data;return`<h2>🔥 ${t("top")}</h2><p class=muted>${t("top_sub")}</p><div class=filters>${[["boosted","boosted"],["latest","latestp"],["pump","pumpq"]].map(([k,l])=>`<button class="${coins.tab==k?"on":""}" onclick="coins.tab='${k}';loadCoins()">${t(l)}</button>`).join("")}</div>
<div class="glass tw"><table class=tbl><thead><tr><th>#</th><th>${t("coin")}</th><th>${t("price")}</th><th>${t("mc")}</th><th>${t("vol")}</th><th>${t("liq")}</th><th>1h</th><th>${t("chg")}</th><th>${t("links")}</th></tr></thead><tbody>${d.length?d.map((p,i)=>`<tr><td class=muted>${i+1}</td><td>${coinCell(p.baseToken.address,p.baseToken.symbol,p.info?.imageUrl)}</td><td>${px(+p.priceUsd)}</td><td><b>${usd(p.marketCap??p.fdv)}</b></td><td>${usd(p.volume?.h24)}</td><td>${usd(p.liquidity?.usd)}</td><td>${pc(p.priceChange?.h1)}</td><td>${pc(p.priceChange?.h24)}</td><td>${links(p.baseToken.address)}</td></tr>`).join(""):Array(6).fill(`<tr><td colspan=9><div class=skel></div></td></tr>`).join("")}</tbody></table></div>`}
async function j(u){const r=await fetch(u);if(!r.ok)throw r.status;return r.json()}
async function loadCoins(){try{let pairs=[];const D="https://api.dexscreener.com";
if(coins.tab=="pump"){pairs=(await j(D+"/latest/dex/search?q=pump")).pairs.filter(p=>p.chainId=="solana")}
else{const l=await j(D+(coins.tab=="boosted"?"/token-boosts/top/v1":"/token-profiles/latest/v1"));const a=[...new Set(l.filter(x=>x.chainId=="solana").map(x=>x.tokenAddress))].slice(0,30);if(a.length)pairs=await j(D+"/tokens/v1/solana/"+a.join(","))}
const best={};for(const p of pairs){const m=p.baseToken.address;if(!best[m]||(p.liquidity?.usd||0)>(best[m].liquidity?.usd||0))best[m]=p}
coins.data=Object.values(best).filter(p=>(p.liquidity?.usd||0)>1000).sort((a,b)=>(b.volume?.h24||0)-(a.volume?.h24||0)).slice(0,25)}catch(e){console.warn("coins",e)}
const s=$("#coinsec");if(s)s.innerHTML=coinsBlock()}
async function loadFeed(){try{F=await j("feed.json?"+Date.now());$("#upd").textContent=t("updated")+" "+ago(F.generated_at)}catch(e){console.warn(e)}}
let P=null,pnlDay="today";
async function loadPnl(){try{P=await j("pnl.json?"+Date.now())}catch(e){console.warn("pnl",e)}}
const sUsd=n=>n==null?"—":(n<0?"-":"+")+"$"+fm(Math.abs(n));
const sSol=n=>n==null?"—":(n<0?"-":"+")+(Math.abs(n)<100?(+Math.abs(n)).toFixed(2):fm(Math.abs(n)))+" SOL";
const pnlCls=b=>!b?" ":(b.net_usd<0||(b.net_usd==0&&b.net_sol<0)?"dn":"up");
const xSvg=`<svg class="xlogo" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.727-8.835L1.254 2.25H8.08l4.253 5.622L18.244 2.25zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>`;
function miniX(url){return url?`<a class="xicon" href="${esc(url)}" target=_blank rel=noopener aria-label="X">${xSvg}</a>`:""}
function pnlCard(c){
  const b=(c.periods&&c.periods[pnlDay])||{};
  const cls=pnlCls(b);
  return`<article class="glass pnl-card"><div class=pnl-top><div class=coin><span class=av>${esc((c.name||"?")[0])}</span><div><a href="#/caller/${esc(c.name)}"><b>${esc(c.name)}</b></a><div class=addr>${short(c.address)}</div></div></div>${miniX(c.x)}</div>
<div class="pnl-big ${cls}">${sUsd(b.net_usd||0)}</div><div class="${cls} pnl-sol">${sSol(b.net_sol||0)}</div>
<div class=kv><div><span>Won</span><b class=up>${sUsd(b.won_usd||0)}</b><b class=up>${sSol(b.won_sol||0)}</b></div><div><span>Lost</span><b class=dn>${b.lost_usd?"-"+usd(b.lost_usd):"$0.00"}</b><b class=dn>${b.lost_sol?"-"+((b.lost_sol<100?b.lost_sol.toFixed(2):fm(b.lost_sol))+" SOL"):"0.00 SOL"}</b></div><div><span>Trades</span><b>${b.wins||0}W · ${b.losses||0}L</b></div></div>
<div class=thumb><canvas data-series="${esc(JSON.stringify(c.series||[]))}"></canvas></div></article>`}
function pnlHome(){
  const days=[["today","Today"],["yesterday","Yesterday"],["day_before","Day before"]];
  const label=P&&P.labels&&P.labels[pnlDay]?` · ${P.labels[pnlDay]}`:"";
  const per=c=>((c.periods||{})[pnlDay]||{});
  const list=(P&&P.callers? [...P.callers]:[]).sort((a,b)=>(per(b).net_usd||0)-(per(a).net_usd||0));
  return`<section class=pnl-hero><div class=pnl-head><div><span class=pill>Asia/Riyadh · realized SOL &amp; USDC</span><h2>Caller profit and loss${label}</h2><p class=muted>Net, what was won, and what was lost. Real SOL and Circle USDC only.</p></div></div>
<div class=filters>${days.map(([k,l])=>`<button class="${pnlDay==k?"on":""}" onclick="pnlDay='${k}';render()">${l}</button>`).join("")}</div>
${list.length?`<div class=pnl-cards>${list.map(pnlCard).join("")}</div>`:`<p class=muted>PnL appears after the next 10-minute refresh.</p>`}
<p class=note>${esc(P&&P.methodology||"")}</p></section>`}
function pnlTable(title,key,sub){
  const names=(P&&P.boards&&P.boards[key])||[];
  const by=Object.fromEntries((P.callers||[]).map(c=>[c.name,c]));
  const rows=names.map((n,i)=>{const c=by[n]||{name:n,periods:{}};const b=c.periods[key]||{};const cls=pnlCls(b);
    return`<tr><td class="rank r${i+1}">${i+1}</td><td><div class=coin><span class=av>${esc((n||"?")[0])}</span><a href="#/caller/${esc(n)}"><b>${esc(n)}</b></a></div></td><td class="${cls}"><b>${sUsd(b.net_usd||0)}</b><div class=addr>${sSol(b.net_sol||0)}</div></td><td class="up hide-m">${sUsd(b.won_usd||0)}</td><td class="dn hide-m">${sUsd(b.lost_usd||0)}</td><td>${b.wins||0}W · ${b.losses||0}L</td><td>${miniX(c.x)}</td></tr>`}).join("");
  const vals=names.map(n=>(((by[n]||{}).periods||{})[key]||{}).net_usd||0);
  const chart=`<div class="glass board-chart"><canvas data-names="${esc(JSON.stringify(names))}" data-vals="${esc(JSON.stringify(vals))}"></canvas></div>`;
  return`<section><h2>${title}</h2><p class=muted>${sub}</p>${names.length?chart:""}<div class="glass tw"><table class=tbl><thead><tr><th>#</th><th>Caller</th><th>Net</th><th class=hide-m>Won</th><th class=hide-m>Lost</th><th>W / L</th><th></th></tr></thead><tbody>${rows||`<tr><td colspan=7 class=muted>No realized trades yet</td></tr>`}</tbody></table></div></section>`}
function pnlBoards(){
  if(!P)return`<section><h2>Leaderboards</h2><p class=muted>PnL appears after the next 10-minute refresh.</p></section>`;
  return pnlTable("Top 10 today","today","Realized net PnL for the current Asia/Riyadh day")+pnlTable("Top 10 this month","month","Realized net PnL over the last 30 Asia/Riyadh days")+pnlTable("Top 10 on the platform","all_time","The tracked callers, ranked since this job started downloading their swaps");
}
let charts=[];
function killCharts(){charts.splice(0).forEach(c=>{try{c.destroy()}catch(e){}})}
function drawCharts(){
  if(!window.Chart)return;
  const axis={color:"#c8c2b4"},grid={color:"rgba(212,175,55,.16)"};
  document.querySelectorAll("canvas[data-series]").forEach(cv=>{
    let series=[];try{series=JSON.parse(cv.dataset.series)}catch(e){}
    if(!series.length)return;
    charts.push(new Chart(cv,{type:"line",data:{labels:(P&&P.series_labels)||series.map((_,i)=>i),datasets:[{data:series,borderColor:"#d4af37",backgroundColor:"rgba(212,175,55,.15)",fill:true,tension:.35,pointRadius:0,borderWidth:2}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{display:false},y:{display:false}},animation:{duration:350}}}));
  });
  document.querySelectorAll("canvas[data-vals]").forEach(cv=>{
    let names=[],vals=[];try{names=JSON.parse(cv.dataset.names);vals=JSON.parse(cv.dataset.vals)}catch(e){}
    charts.push(new Chart(cv,{type:"bar",data:{labels:names,datasets:[{data:vals,backgroundColor:vals.map(v=>v<0?"#ff4d6a":"#1fcb7a"),borderRadius:4}]},options:{indexAxis:"y",responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:axis,grid},y:{ticks:{color:"#fff"},grid:{display:false}}},animation:{duration:400}}}));
  });
}
function render(){killCharts();document.documentElement.lang="en";document.documentElement.dir="ltr";
document.querySelectorAll("[data-i]").forEach(e=>e.textContent=t(e.dataset.i));const [,r="",a]=location.hash.split("/");
document.querySelectorAll("nav a").forEach(e=>e.classList.toggle("on",e.getAttribute("href")=="#/"+r));
if(!F){$("#app").innerHTML=`<p class=muted style="padding:60px;text-align:center">${t("loading")}</p>`;return}
const y=scrollY;$("#app").innerHTML=(V[r]||V.home)(decodeURIComponent(a||""));scrollTo(0,y);requestAnimationFrame(drawCharts)}

addEventListener("hashchange",()=>{render();scrollTo(0,0);});
async function countVisit(){
  try{
    const r=await fetch("https://abacus.jasoncameron.dev/hit/kol-tracker/visits");
    if(!r.ok) return;
    const d=await r.json();
    const el=$("#visits");
    if(el && d.value!=null){el.hidden=false;el.textContent=" · "+d.value+" visits"}
  }catch(e){console.warn("visits",e)}
}
(async()=>{render();countVisit();await loadFeed();await loadPnl();render();loadCoins();setInterval(async()=>{await loadFeed();await loadPnl();render()},30000);setInterval(loadCoins,45000)})();
