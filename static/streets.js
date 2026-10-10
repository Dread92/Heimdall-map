// Heimdall 1.56 — the streets and the settlements of an oblast (OpenStreetMap), searched on this phone.
// The owner: "a complete registry of the streets within the city / the oblast, so the user can set the pin
// accurately — all the towns and streets of Ukraine". A page loads this file when its pin picker opens (Tactical's
// #homesheet, Light's #pick); it downloads the chosen oblast's list (/static/streets/<uid>.json, built by
// scripts/build_streets.py) and searches it here: what is typed never leaves the phone — the server sees only which
// oblast's list was opened, as it sees the map tiles a phone shows. Data © OpenStreetMap contributors, ODbL 1.0.
(function(){
'use strict';
const V=1;
const ORDER=['31','14','4','8','9','28','10','11','12','13','15','16','27','17','18','19','5','20','21','22','23','3','24','26','25','29','30'];
const F={}, P={};                 // the files, by uid (null: could not be had); the downloads under way
const tt=(k,...a)=>{ try{ return t(k,...a); }catch(e){ return k; } };
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// lower case, apostrophes out (лук'янівка = лукянівка), words only
const N=s=>' '+String(s||'').toLowerCase().replace(/[’ʼ`´'"]/g,'').replace(/ё/g,'е').replace(/[^0-9a-zа-яіїєґ]+/g,' ').trim();
const TL={а:'a',б:'b',в:'v',г:'h',ґ:'g',д:'d',е:'e',є:'ie',ж:'zh',з:'z',и:'y',і:'i',ї:'i',й:'i',к:'k',л:'l',м:'m',н:'n',о:'o',п:'p',
  р:'r',с:'s',т:'t',у:'u',ф:'f',х:'kh',ц:'ts',ч:'ch',ш:'sh',щ:'shch',ь:'',ю:'iu',я:'ia',ы:'y',э:'e',ъ:''};
// Latin typed against Cyrillic names: both sides to one skeleton (Yahotyn = Iahotyn, Kyiv = Kyiv)
const SK=s=>{ let o=''; for(const c of s) o+=TL[c]!==undefined?TL[c]:c; return o.replace(/y(?=[aeiou])/g,'i').replace(/j/g,'i'); };
const TR=s=>typeof translit==='function'?translit(s):s;
const KIND=['hs_k0','hs_k1','hs_k2','hs_k3'];

function prep(d,uid){
  d.uid=uid;
  d.T=d.t.map(x=>({n:x[0],h:N(x[0]),X:x[1]*10,Y:x[2]*10,k:x[3],r:x[4]>=0?d.r[x[4]]:null}));
  d.S=d.s.map(x=>{ const T=d.T[x[1]], al=typeof x[5]==='string'?x[5]:null;
    return {n:x[0],al,ti:x[1],hn:N(x[0]),h:N(x[0])+(al?N(al):''),lon:(T.X+x[2])/1e5,lat:(T.Y+x[3])/1e5,km:x[4]*1.1e-3,dist:x[6]!=null?d.r[x[6]]:null}; });
  return d; }
function load(uid){
  if(uid in F) return Promise.resolve(F[uid]);
  return P[uid]||(P[uid]=fetch(`/static/streets/${uid}.json?v=${V}`).then(r=>r.ok?r.json():null).then(d=>F[uid]=d&&d.v===1?prep(d,uid):null)
    .catch(()=>F[uid]=null).finally(()=>{ delete P[uid]; })); }

// every word typed starts a word of the street or of its settlement, and one at least of the street
function find(q,ds,places){
  const toks=N(q).trim().split(' ').filter(Boolean);
  if(!toks.length||toks.join('').length<2) return null;
  const lat=/[a-z]/.test(toks.join('')), tk=toks.map(x=>' '+(lat?SK(x):x));
  const hs=d=>lat?(d.SL||(d.SL=d.S.map(s=>SK(s.h)))):d.S.map(s=>s.h);
  const ht=d=>lat?(d.TLh||(d.TLh=d.T.map(x=>SK(x.h)))):d.T.map(x=>x.h);
  const S=[], T=[];
  for(const d of ds){ const sh=hs(d), th=ht(d);
    for(let i=0;i<d.S.length;i++){ const s=sh[i], w=th[d.S[i].ti]; let inS=0, inT=0, ok=true;
      for(const x of tk){ const a=s.includes(x), b=w.includes(x); if(!a&&!b){ ok=false; break; } if(a) inS++; else inT++; }
      if(ok&&inS){ const st=d.S[i], mn=lat?SK(st.hn):st.hn;      // found by its other name only: say which
        S.push({d,s:st,inT,byAl:!!st.al&&tk.some(x=>s.includes(x)&&!w.includes(x)&&!mn.includes(x))}); } }
    for(let i=0;i<d.T.length;i++) if(tk.every(x=>th[i].includes(x))) T.push({d,t:d.T[i]}); }
  // the settlement named first, then the bigger settlement, the oblast chosen first (Kyiv before its oblast), the shorter name
  S.sort((a,b)=>b.inT-a.inT||a.d.T[a.s.ti].k-b.d.T[b.s.ti].k||ds.indexOf(a.d)-ds.indexOf(b.d)||a.s.n.length-b.s.n.length||a.s.n.localeCompare(b.s.n));
  // a settlement the page's own list already has (the same name within 3 km) is not shown twice
  const pl=(places||[]).map(p=>({h:N(p.uk||p.name),lon:+p.lon,lat:+p.lat}));
  const dup=x=>pl.some(p=>p.h===x.h&&Math.abs(p.lon-x.X/1e5)<0.04&&Math.abs(p.lat-x.Y/1e5)<0.03);
  const T2=T.filter(o=>!dup(o.t)).sort((a,b)=>a.t.k-b.t.k||a.t.n.localeCompare(b.t.n));
  return {S:S.slice(0,50),Sn:S.length,T:T2.slice(0,20),Tn:T2.length}; }

let M=null;
function css(){ const st=document.createElement('style');
  st.textContent='.hsl{display:flex;gap:8px;align-items:center;margin:8px 0 0;font:13px var(--sans);color:var(--ink2)}.hsl select{flex:1;min-width:0;padding:8px;border:1px solid var(--line);border-radius:3px;background:var(--panel);color:var(--ink);font:14px var(--sans)}'
    +'.hsh{font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink3);padding:12px 6px 4px}.hsf{font:12px/1.45 var(--sans);color:var(--ink3);padding:8px 6px}.hsf a{color:inherit}';
  document.head.appendChild(st); }
function opts(){ const v=M.sel.value;
  M.sel.innerHTML=`<option value="31,14">${esc(tt('hs_kyiv2'))}</option>`+ORDER.slice(2).map(u=>[u,typeof oblFull==='function'?oblFull(u):u])
    .sort((a,b)=>a[1].localeCompare(b[1])).map(([u,n])=>`<option value="${u}">${esc(n)}</option>`).join('');
  if(v) M.sel.value=v; }
function pickDefault(){ let u=null; try{ u=M.obl&&M.obl(); }catch(e){}
  let v=u?(u==='31'||u==='14'?'31,14':String(u)):null;
  if(!v){ try{ v=localStorage.getItem('hs_obl'); }catch(e){} }
  M.sel.value=v||'31,14'; if(!M.sel.value) M.sel.value='31,14'; }
// the page's own list is drawn first (its input listener runs before this one); this section goes after it
function draw(res,uids,state){
  const L=M.list; L.querySelectorAll('.hs').forEach(e=>e.remove()); M.items=[];
  const box=document.createElement('div'); box.className='hs';
  const where=M.sel.options[M.sel.selectedIndex]?M.sel.options[M.sel.selectedIndex].textContent:'';
  if(state==='load'){ box.innerHTML=`<div class="hsf">${esc(tt('hs_loading',where))}</div>`; L.appendChild(box); return; }
  if(state==='fail'){ box.innerHTML=`<div class="hsf">${esc(tt('hs_fail'))}</div>`; L.appendChild(box); return; }
  if(!res||(!res.S.length&&!res.T.length)){ if(res){ box.innerHTML=`<div class="hsf">${esc(tt('hs_none',where))}</div>`; L.appendChild(box); } return; }
  const row=(main,sub,right)=>{ const i=M.items.length;
    return M.style==='light'?`<button type="button" data-h="${i}">${esc(main)}<small>${esc([sub,right].filter(Boolean).join(' · '))}</small></button>`
      :`<div class="hitem" data-h="${i}"><div>${esc(main)}${sub?` <span>${esc(sub)}</span>`:''}</div><span>${esc(right)}</span></div>`; };
  const lng=typeof LANG==='string'?LANG:'uk';
  let h='';
  if(res.S.length){ h+=`<div class="hsh">${esc(tt('hs_streets'))}</div>`;
    for(const o of res.S){ const s=o.s, T=o.d.T[s.ti];
      const sub=lng!=='uk'?TR(s.n)+(o.byAl?' · '+tt('hs_was',s.al):''):(s.al?tt('hs_was',s.al):''), right=[T.n,s.dist||(T.k>=2?T.r:null)].filter(Boolean).join(' · ');
      h+=row(s.n,sub,right);
      M.items.push({street:true,uk:`${s.n}, ${T.n}`,name:TR(`${s.n}, ${T.n}`),lon:+s.lon.toFixed(5),lat:+s.lat.toFixed(5),obl:o.d.uid,km:s.km}); }
    if(res.Sn>res.S.length) h+=`<div class="hsf">${esc(tt('hs_more',res.Sn-res.S.length))}</div>`; }
  if(res.T.length){ h+=`<div class="hsh">${esc(tt('hs_towns'))}</div>`;
    for(const o of res.T){ const x=o.t;
      h+=row(x.n,lng!=='uk'?TR(x.n):'',[tt(KIND[x.k]),x.r].filter(Boolean).join(' · '));
      M.items.push({street:false,uk:x.n,name:TR(x.n),lon:x.X/1e5,lat:x.Y/1e5,obl:o.d.uid,km:x.k<2?3:1}); } }
  h+=`<div class="hsf">${esc(tt('hs_osm'))} — <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap</a></div>`;
  box.innerHTML=h;
  const em=L.querySelector('.empty'); if(em) em.remove();      // "no match" was the page's own list only
  L.appendChild(box); }
async function go(){ const my=++M.seq, q=M.q.value, uids=M.sel.value.split(',');
  if(N(q).trim().replace(/ /g,'').length<2){ draw(null,uids); return; }
  if(uids.some(u=>!(u in F))){ draw(null,uids,'load'); await Promise.all(uids.map(load)); if(my!==M.seq) return; }
  const ds=uids.map(u=>F[u]).filter(Boolean);
  if(!ds.length){ draw(null,uids,'fail'); return; }
  draw(find(q,ds,M.places&&M.places()),uids); }
// mount({q, list, style: 'tac' | 'light', obl: () => the pin's oblast, places: () => the page's own places, pick(item)})
function mount(o){
  if(!M){ M=Object.assign({seq:0,items:[]},o); css();
    const lb=document.createElement('label'); lb.className='hsl'; lb.innerHTML='<span></span><select></select>';
    o.q.insertAdjacentElement('afterend',lb); M.lbl=lb; M.sel=lb.querySelector('select');
    M.sel.addEventListener('change',()=>{ try{ localStorage.setItem('hs_obl',M.sel.value); }catch(e){} go(); });
    o.q.addEventListener('input',()=>{ clearTimeout(M.tm); M.tm=setTimeout(go,90); });
    o.list.addEventListener('click',e=>{ const el=e.target.closest('[data-h]'); if(!el||!M.list.contains(el)) return; e.stopPropagation();
      const it=M.items[+el.dataset.h]; if(it) M.pick(it); }); }
  else Object.assign(M,o);
  M.lbl.querySelector('span').textContent=tt('hs_in'); opts(); pickDefault();
  go(); }
window.HS={mount,load,find,N,SK,_prep:prep,_F:F};
})();
