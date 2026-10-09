// Heimdall — the replay (1.42): a past window of the last 7 days on the Tactical map, like a weather-radar loop.
// Loaded only when somebody opens it. The official alerts paint the raions as they were at that moment; the targets
// stand where the channels' posts put them, read with today's rules, each until the next post moved it or its time
// ran out — nothing is extrapolated, no course is drawn that no post stated. The band at the top of the page stays live.
(function(){
const RP=window.RP={on:false,t:0,from:0,to:0,data:null,playing:false,sp:1,win:null,asig:null,els:new Map(),raf:0};
const SPEEDS=[2,10,30];                       // minutes of replay per second
const STEP=10*60e3;                           // the ⏮ / ⏭ buttons
const TRAIL_MIN=20;                           // how far back a target's reported positions are drawn
// how long a target stays after its last report (minutes), and when it starts to fade — the live map's own clocks:
// a drone is stale after 5 min and gone after 15; a missile after 12; a sign that says only "where" after 5
const TTL=ty=>ty==='unknown'?[2,5]:/missile/.test(ty)?[4,12]:[5,15];
const NS='http://www.w3.org/2000/svg';
const kp=ms=>{const o={}; for(const p of new Intl.DateTimeFormat('en-GB',{timeZone:TZ,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(ms))) if(p.type!=='literal') o[p.type]=+p.value; return o;};
const off=ms=>{const p=kp(ms); return Date.UTC(p.year,p.month-1,p.day,p.hour,p.minute,p.second)-Math.floor(ms/1000)*1000;};
// 12:00 Kyiv time on the day `back` days before today: a night is the 24 hours from one noon to the next
function noon(back){ const p=kp(Date.now()); const g=Date.UTC(p.year,p.month-1,p.day-back,12); return g-off(g); }
const loc=()=>LANG==='uk'?'uk-UA':LANG==='fr'?'fr-FR':'en-GB';
const fmtDay=ms=>new Date(ms).toLocaleDateString(loc(),{weekday:'short',day:'numeric',month:'short',timeZone:TZ});
const fmtHM=ms=>new Date(ms).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:TZ});
function windows(){
  const now=Date.now(), w=[]; const to=Math.ceil(now/300e3)*300e3;
  w.push({k:'24',from:to-864e5,to,label:t('rp_24')});
  for(let b=0;b<7;b++){ const a=noon(b); if(a>=now) continue; w.push({k:'n'+b,from:a,to:Math.min(noon(b-1),to),label:fmtDay(a),title:t('rp_night',fmtDay(a))}); }
  return w.slice(0,8);
}
const $r=id=>document.getElementById(id);
function bar(){
  if($r('rpbar')) return $r('rpbar');
  const el=document.createElement('div'); el.id='rpbar'; el.setAttribute('role','region'); el.setAttribute('aria-label',t('rp_open'));
  el.innerHTML=`<div class="rph"><span class="rptag">${esc(t('rp_tag'))}</span><b id="rptime">--:--</b><span id="rpdate"></span>
    <button type="button" id="rpx" class="rpx" aria-label="${esc(t('rp_close'))}" title="${esc(t('rp_close'))}">✕</button></div>
    <div class="rpdays" id="rpdays"></div>
    <div class="rptrack"><canvas id="rpcv" aria-hidden="true"></canvas><input type="range" id="rprange" min="0" max="1" step="60000" value="0" aria-label="${esc(t('rp_open'))}"></div>
    <div class="rpctl"><button type="button" id="rpback" aria-label="${esc(t('rp_back'))}" title="${esc(t('rp_back'))}">−10′</button><button type="button" id="rpplay" class="rpp" aria-label="${esc(t('rp_play'))}">▶</button><button type="button" id="rpfwd" aria-label="${esc(t('rp_fwd'))}" title="${esc(t('rp_fwd'))}">+10′</button><button type="button" id="rpspd" title="${esc(t('rp_speed_t'))}"></button><span id="rpcount"></span></div>
    <div class="rpnote" id="rpnote"><span class="rpnl">${esc(t('rp_note'))} ${esc(t('rp_live'))}</span><span class="rpns">${esc(t('rp_note_s'))}</span></div>`;
  $r('mapwrap').appendChild(el);
  $r('rpx').onclick=close;
  $r('rpplay').onclick=()=>play(!RP.playing);
  $r('rpback').onclick=()=>seek(RP.t-STEP);
  $r('rpfwd').onclick=()=>seek(RP.t+STEP);
  $r('rpspd').onclick=()=>{RP.sp=(RP.sp+1)%SPEEDS.length; spd();};
  $r('rprange').addEventListener('input',e=>seek(+e.target.value));
  return el;
}
function spd(){ $r('rpspd').textContent=t('rp_speed',SPEEDS[RP.sp]); }
function days(){
  const ws=windows(); RP.ws=ws;
  $r('rpdays').innerHTML=ws.map(w=>`<button type="button" data-w="${w.k}"${w.title?` title="${esc(w.title)}"`:''} class="${RP.win&&RP.win.k===w.k?'on':''}">${esc(w.label)}</button>`).join('');
  $r('rpdays').querySelectorAll('button').forEach(b=>b.onclick=()=>load(ws.find(w=>w.k===b.dataset.w)));
}
async function load(w){
  RP.win=w; play(false); days(); RP.data=null; RP.asig=null; clearTracks();
  $r('rpcount').textContent=t('rp_load');
  let d=null; try{ d=await jget(`/api/replay?from=${Math.floor(w.from/1000)}&to=${Math.floor(w.to/1000)}`,30000); }catch(e){}
  if(RP.win!==w||!RP.on) return;
  if(!d||!d.alerts){ $r('rpcount').textContent=t('rp_err'); return; }
  for(const a of d.alerts) a.al={oblast_uid:a.o,location_type:a.lt,raion_key:a.rk,alert_level:a.lv,alert_type:a.at,location_title:a.ti};
  d.alerts.forEach((a,i)=>a.i=i);
  RP.data=d; RP.from=d.from*1000; RP.to=d.to*1000;
  const r=$r('rprange'); r.min=RP.from; r.max=RP.to;
  // start a little before the attack, not at noon: the first ten minutes with at least a quarter of the busiest ten
  // minutes' reports (a lone report at lunchtime is not where anybody wants to begin); with no target, the first alert
  // over Kyiv city or oblast
  const B=new Map(); for(const tr of d.tracks) for(const p of tr.p){ const k=Math.floor(p[0]/600); if(p[0]*1000>=RP.from) B.set(k,(B.get(k)||0)+1); }
  const peak=Math.max(0,...B.values()), busy=[...B.keys()].sort((a,b)=>a-b).find(k=>B.get(k)>=Math.max(2,peak/4));
  const ky=d.alerts.filter(a=>(a.o==='31'||a.o==='14')&&a.s*1000>RP.from).map(a=>a.s*1000);
  const first=busy!=null?busy*600e3:Math.min(...ky,RP.to);
  seek(first<RP.to?Math.max(RP.from,first-10*60e3):RP.from);
  hist();
  if(!d.tracks.length) $r('rpcount').textContent=t('rp_empty');
}
// the strip above the slider: how many reports, and when Kyiv (city or oblast) was under an official alert
function hist(){
  const cv=$r('rpcv'), d=RP.data; if(!cv||!d) return; const W=cv.clientWidth||300, H=20, dpr=Math.min(2,devicePixelRatio||1);
  cv.width=W*dpr; cv.height=H*dpr; const c=cv.getContext('2d'); c.scale(dpr,dpr); c.clearRect(0,0,W,H);
  const span=RP.to-RP.from||1, X=ms=>(ms-RP.from)/span*W, N=Math.max(24,Math.min(144,Math.round(W/4))), bins=new Array(N).fill(0);
  for(const tr of d.tracks) for(const p of tr.p){ const i=Math.floor((p[0]*1000-RP.from)/span*N); if(i>=0&&i<N) bins[i]++; }
  const mx=Math.max(1,...bins), day=document.body.classList.contains('m-day');
  for(const a of d.alerts){ if(a.o!=='31'&&a.o!=='14') continue; const x0=X(Math.max(RP.from,a.s*1000)), x1=X(Math.min(RP.to,a.e?a.e*1000:RP.to));
    c.fillStyle=a.lv==='yellow'?'rgba(242,194,0,.55)':'rgba(224,52,44,.7)'; c.fillRect(x0,H-3,Math.max(1,x1-x0),3); }
  c.fillStyle=day?'rgba(40,48,60,.55)':'rgba(255,138,61,.75)';
  bins.forEach((b,i)=>{ if(!b) return; const h=Math.max(2,Math.round(b/mx*(H-5))); c.fillRect(i*W/N+.5,H-4-h,Math.max(1,W/N-1),h); });
}
function seek(ms){ if(!RP.data) return; RP.t=Math.max(RP.from,Math.min(RP.to,ms)); frame(); }
function play(on){
  RP.playing=!!on&&!!RP.data; const b=$r('rpplay'); if(b){ b.textContent=RP.playing?'⏸':'▶'; b.setAttribute('aria-label',t(RP.playing?'rp_pause':'rp_play')); }
  cancelAnimationFrame(RP.raf); if(!RP.playing) return;
  if(RP.t>=RP.to) RP.t=RP.from;
  let last=performance.now();
  const step=now=>{ if(!RP.playing||!RP.on) return; RP.t=Math.min(RP.to,RP.t+(now-last)*SPEEDS[RP.sp]*60); last=now; frame(); if(RP.t>=RP.to){ play(false); return; } RP.raf=requestAnimationFrame(step); };
  RP.raf=requestAnimationFrame(step);
}
function clearTracks(){ for(const e of RP.els.values()) e.g.remove(); RP.els.clear(); }
function frame(){
  const d=RP.data; if(!d||!RP.on) return; const T=RP.t/1000;
  // the alerts of that moment, painted only when they change
  const act=d.alerts.filter(a=>a.s<=T&&(a.e==null||a.e>T)); const sig=act.map(a=>a.i).join(',');
  if(sig!==RP.asig){ RP.asig=sig; applyAlertMap(alertMap(act.map(a=>a.al))); }
  // the targets: where the latest post before T put each one, with the positions reported over the last half-hour
  const g=$r('rpg'); const live=new Set(); let n=0;
  d.tracks.forEach((tr,i)=>{
    let j=-1; for(let q=0;q<tr.p.length;q++){ if(tr.p[q][0]<=T) j=q; else break; }
    if(j<0) return; const head=tr.p[j], age=(T-head[0])/60, [fresh,ttl]=TTL(tr.ty);
    if(age>ttl) return;
    live.add(i); n+=(tr.n||1);
    let e=RP.els.get(i);
    if(!e){ const gg=document.createElementNS(NS,'g'); gg.setAttribute('class',`rpt mk rp ${tr.ty}${tr.jet?' jet':''}${tr.ap?' appr':''}`);
      gg.innerHTML=`<polyline class="rptr"/><g class="rpds"></g><g class="rph2"><g class="body"><g class="rot"></g></g><text class="rpl"></text></g>`;
      g.appendChild(gg); e={g:gg,j:-2}; RP.els.set(i,e); }
    const op=age<=fresh?1:Math.max(.3,1-(age-fresh)/(ttl-fresh));
    e.g.style.opacity=op.toFixed(2);
    const [x,y]=proj(head[1],head[2]);
    const hg=e.g.querySelector('.rph2'); hg.setAttribute('transform',`translate(${x.toFixed(2)} ${y.toFixed(2)})`);
    if(e.j!==j||e.k!==KPX){ e.j=j; e.k=KPX;
      const last=j===tr.p.length-1, h=last&&tr.h!=null&&tr.ty!=='unknown'?tr.h:0;      // a course only where a post stated one
      const gk=glyphKey({type:tr.ty,jet:!!tr.jet,heading:h}); const rot=e.g.querySelector('.rot');
      if(e.gk!==gk){ e.gk=gk; rot.innerHTML=G[gk]; }
      rot.setAttribute('transform',`rotate(${h}) scale(${kx((tr.ty==='drones'?1.05:/missile/.test(tr.ty)?0.95:1.0)*KPX)})`);
      const lb=e.g.querySelector('.rpl'); lb.setAttribute('x',kx(9*KPX)); lb.setAttribute('y',kx(-7*KPX));
      lb.textContent=(head[3]&&head[3]!=='область'?(tr.ap?'→ ':'')+pn(head[3]):'')+((tr.n||1)>1?` ×${tr.n}`:'');
      // the trail: each reported position of the last half-hour, joined in the order they were reported
      const from=T-TRAIL_MIN*60; let pts=tr.p.slice(0,j+1).filter(p=>p[0]>=from);
      // a leg longer than a drone could fly between the two posts is two targets joined, not a route: the trail stops there
      for(let q=pts.length-1;q>0;q--){ const a=pts[q-1],b=pts[q],[ax,ay]=proj(a[1],a[2]),[bx,by]=proj(b[1],b[2]);
        if(Math.hypot(bx-ax,by-ay)>Math.max(12,(b[0]-a[0])/60*(/missile/.test(tr.ty)?15:4)+8)){ pts=pts.slice(q); break; } }
      const xy=pts.map(p=>proj(p[1],p[2]).map(v=>v.toFixed(2)).join(','));
      e.g.querySelector('.rptr').setAttribute('points',xy.length>1?xy.join(' '):'');
      e.g.querySelector('.rpds').innerHTML=pts.slice(0,-1).map(p=>{const [px,py]=proj(p[1],p[2]); return `<circle class="rpdot" cx="${px.toFixed(2)}" cy="${py.toFixed(2)}" r="${kx(1.6*KPX)}"/>`;}).join('');
    }
  });
  for(const [i,e] of RP.els) if(!live.has(i)){ e.g.remove(); RP.els.delete(i); }
  $r('rptime').textContent=fmtHM(RP.t); $r('rpdate').textContent=fmtDay(RP.t);
  const r=$r('rprange'); if(+r.value!==RP.t) r.value=RP.t;
  if(d.tracks.length) $r('rpcount').textContent=t('rp_tgts',n);
}
RP.frame=()=>{ if(RP.on){ for(const e of RP.els.values()) e.j=-2; frame(); } };
RP.open=()=>{
  if(RP.on) return; RP.on=true; document.body.classList.add('rp'); if(typeof syncMini==='function') syncMini();
  if(typeof closePanels==='function') closePanels();
  if(!$r('rpg')){ const gg=document.createElementNS(NS,'g'); gg.id='rpg'; $r('map').insertBefore(gg,$r('edges')); }
  bar().hidden=false; spd(); days(); load(RP.ws[0]);
  document.addEventListener('keydown',keys);
  if(location.hash!=='#replay') history.replaceState(null,'',location.pathname+location.search+'#replay');
};
function keys(e){
  if(!RP.on||e.target.closest('input:not([type=range]),select,textarea')) return;
  if(e.key===' '){ e.preventDefault(); play(!RP.playing); }
  else if(e.key==='ArrowLeft'){ e.preventDefault(); seek(RP.t-60e3); }
  else if(e.key==='ArrowRight'){ e.preventDefault(); seek(RP.t+60e3); }
  else if(e.key==='Escape') close();
}
function close(){
  play(false); RP.on=false; RP.data=null; RP.asig=null; clearTracks();
  document.body.classList.remove('rp'); const b=$r('rpbar'); if(b) b.hidden=true; if(typeof syncMini==='function') syncMini();
  document.removeEventListener('keydown',keys);
  if(location.hash==='#replay') history.replaceState(null,'',location.pathname+location.search);
  if(typeof render==='function') render();          // the live colours come back at once
}
RP.close=close;
addEventListener('resize',()=>{ if(RP.on) hist(); });
})();
