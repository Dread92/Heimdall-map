// Heimdall 1.57 — the shelters Kyiv city lists (KMDA, ІАС «Майно»: gis.kyivcity.gov.ua/shelter), in
// static/shelters.json (scripts/build_shelters.py). Loaded only when a pin is in Kyiv or the layer is on, and kept by
// the service worker, so it answers with no network. Everything is worked out on this phone: no pin and no position
// ever leaves it. A distance is a straight line — never a route, a walking time or an arrival time — and nothing here
// says a place is safe: the city lists it, Heimdall does not check it.
(function(){
'use strict';
const T={
  uk:{c:['Метро','Підземний перехід','Захисна споруда','Споруда подвійного призначення','Найпростіше укриття','Мобільне укриття'],
    k:['','станція','вхід','','протирадіаційне укриття','підвал','цокольний поверх','перший поверх','паркінг','заклад освіти','наземна будівля'],
    strong:'Метро, переходи, захисні споруди',any:'Підвали, паркінги та інші укриття',h24:'цілодобово',hq:'режим не вказано',
    chk:'перевірте, чи відчинено',ramp:'пандус',line:'відстань по прямій',short:'по прямій',m:'м',km:'км',title:'Укриття поруч',from:'від: {0}',
    none:'У переліку міста немає укриття ближче {0} км — перелік охоплює лише місто Київ.',
    note:'Перелік міста Києва (КМДА, ІАС «Майно»), дані на {0}. Heimdall укриттів не перевіряє: укриття може бути зачинене чи переповнене.',
    out:'Під час атаки на вулиці небезпечно. Якщо не встигаєте дійти — правило двох стін, подалі від вікон.',
    map:'Мапа укриттів міста ↗',show:'Показати на мапі',tel:'тел.',one:'Укриття з переліку міста',any1:'найближче будь-яке:',
    sday:'у навчальний день — лише для учнів і працівників',sonly:'лише для учнів і працівників закладу',repair:'ремонт — може бути зачинене'},
  en:{c:['Metro','Underpass','Civil-defence shelter','Dual-use structure','Simplest shelter','Modular shelter'],
    k:['','station','entrance','','anti-radiation shelter','basement','semi-basement','ground floor','parking garage','school building','above-ground building'],
    strong:'Metro, underpasses, civil-defence shelters',any:'Basements, parkings and other shelters',h24:'24/7',hq:'hours not stated',
    chk:'check it is open',ramp:'ramp',line:'straight-line distance',short:'straight line',m:'m',km:'km',title:'Shelters nearby',from:'from {0}',
    none:'No shelter on the city\'s list within {0} km — the list covers Kyiv city only.',
    note:'Kyiv city\'s list (KMDA, «Майно» system), data of {0}. Heimdall does not check shelters: one may be closed, locked or full.',
    out:'Outside is dangerous during an attack. If you cannot get there in time: two walls between you and the street, away from windows.',
    map:'The city\'s shelter map ↗',show:'Show on the map',tel:'tel.',one:'A shelter on the city\'s list',any1:'nearest of any kind:',
    sday:'on school days, for pupils and staff only',sonly:'for the school\'s pupils and staff only',repair:'under repair — may be closed'},
  fr:{c:['Métro','Passage souterrain','Abri de protection civile','Ouvrage à double usage','Abri sommaire','Abri modulaire'],
    k:['','station','entrée','','abri antiradiation','sous-sol','demi-sous-sol','rez-de-chaussée','parking','bâtiment scolaire','bâtiment hors sol'],
    strong:'Métro, passages, abris de protection civile',any:'Sous-sols, parkings et autres abris',h24:'24 h/24',hq:'horaires non indiqués',
    chk:'vérifiez qu\'il est ouvert',ramp:'rampe',line:'distance à vol d\'oiseau',short:'à vol d\'oiseau',m:'m',km:'km',title:'Abris à proximité',from:'depuis {0}',
    none:'Aucun abri de la liste de la ville à moins de {0} km — elle ne couvre que la ville de Kyiv.',
    note:'Liste de la ville de Kyiv (KMDA, système « Майно »), données du {0}. Heimdall ne vérifie pas les abris : un abri peut être fermé, verrouillé ou plein.',
    out:'Dehors, pendant une attaque, c\'est dangereux. Si vous ne pouvez pas y arriver à temps : deux murs entre vous et la rue, loin des fenêtres.',
    map:'La carte des abris de la ville ↗',show:'Voir sur la carte',tel:'tél.',one:'Un abri de la liste de la ville',any1:'le plus proche, tout type :',
    sday:'les jours d\'école, réservé aux élèves et au personnel',sonly:'réservé aux élèves et au personnel de l\'établissement',repair:'en travaux — peut être fermé'}};
const STRONG=3;                 // categories 0–2: metro, underpasses, civil-defence shelters
const LINE_STRONG_KM=2, LINE_ANY_KM=1, LIST_KM=3;
const LIGHT_CSS='.lsh{display:flex;align-items:center;gap:8px;margin:8px 14px 0;padding:8px 10px;border:1px solid var(--line);border-left:4px solid #5aa9ff;border-radius:4px;background:var(--panel);cursor:pointer}'
  +'.lsh[hidden]{display:none}.lsh>div{flex:1;min-width:0}.lsh .shg{font-size:20px}.lsh b,.lsh small,.shi b,.shi small{display:block}.lsh small,.shi small{color:var(--ink2)}'
  +'.lsh .km{font:700 17px monospace;text-align:right}.lsh .km small{font:12px sans-serif}.lsh:has(.type){display:block}.lsh .type{font-weight:800;font-size:17px}'
  +'.shi{display:block;width:100%;margin-top:5px;padding:6px 8px;text-align:left;color:inherit;font:inherit;background:none;border:1px solid var(--line);border-left:3px solid #2e4f78}.shi.st{border-left-color:#5aa9ff}'
  +'.shh{margin-top:10px;font-weight:700;font-size:13px;color:var(--ink3)}.lsh .kv1{margin-top:6px;font-size:14px}.lsh .muted{color:var(--ink3)}.lsh a{color:#8fb4ff}.lsh .hx,.lsh .shout{color:#ffd166}';
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const L=lang=>T[lang]||T.en;
const fmt=(s,...a)=>s.replace(/\{(\d)\}/g,(_,i)=>a[+i]);
const SH={D:null,P:null,T,STRONG,LINE_STRONG_KM,LINE_ANY_KM,LIST_KM,
  // Kyiv city and a margin: outside it there is nothing to load
  inCity:(lon,lat)=>lon>30.2&&lon<30.85&&lat>50.2&&lat<50.6,
  load(){ if(SH.D) return Promise.resolve(SH.D); if(SH.P) return SH.P;
    SH.P=fetch('/static/shelters.json?v=1').then(r=>r.ok?r.json():Promise.reject(new Error('shelters '+r.status)))
      .then(d=>{ if(!d||!Array.isArray(d.s)) throw new Error('shelters: no list'); SH.D=d; return d; })
      .catch(e=>{ SH.P=null; throw e; });
    return SH.P; },
  km(lon,lat,s){ const k=Math.cos(lat*Math.PI/180)*111.32; return Math.hypot((s[0]-lon)*k,(s[1]-lat)*110.57); },
  // the n nearest — of the strong categories, of the others (weak), or of any — within max km: [[index, km], …], nearest first
  // — never one for a school's pupils and staff only, or one under repair (`closed`)
  near(lon,lat,o){ o=o||{}; const n=o.n||1, max=o.max||LIST_KM, strong=!!o.strong, weak=!!o.weak, out=[]; if(!SH.D) return out;
    const dLat=max/110.57, dLon=max/(Math.cos(lat*Math.PI/180)*111.32);
    SH.D.s.forEach((s,i)=>{ if((strong&&s[2]>=STRONG)||(weak&&s[2]<STRONG)||SH.closed(i)) return; if(Math.abs(s[1]-lat)>dLat||Math.abs(s[0]-lon)>dLon) return;
      const d=SH.km(lon,lat,s); if(d<=max) out.push([i,d]); });
    return out.sort((a,b)=>a[1]-b[1]).slice(0,n); },
  name(i,lang){ const s=SH.D.s[i], t=L(lang), k=t.k[s[3]]||''; return t.c[s[2]]+(k?' · '+k:''); },
  dist(d,lang){ const t=L(lang); return d<1?(Math.max(10,Math.round(d*100)*10))+' '+t.m:(d<10?d.toFixed(1).replace('.',lang==='en'?'.':','):Math.round(d))+' '+t.km; },
  // who may come in, and when, as the city wrote it (scripts/build_shelters.py, `_access`): "" round the clock, "?" not
  // stated, "s" a school's — its pupils and staff on school days —, "S" theirs only, "r" under repair, or the hours
  hours(i,lang){ const h=SH.D.s[i][6], t=L(lang);
    return h===''?t.h24:h==='s'?t.sday:h==='S'?t.sonly:h==='r'?t.repair:(h==='?'?t.hq:h)+' — '+t.chk; },
  open24(i){ return SH.D.s[i][6]===''; },
  closed(i){ const h=SH.D.s[i][6]; return h==='S'||h==='r'; },
  // one shelter, as a row of a list
  row(i,d,lang){ const s=SH.D.s[i], t=L(lang);
    return `<button type="button" class="shi${s[2]<STRONG?' st':''}" data-sh="${i}"><b>${esc(SH.name(i,lang))} · ${esc(SH.dist(d,lang))}</b>`
      +`<small>${esc(s[5]||'—')} · <span class="${SH.open24(i)?'h24':'hx'}">${esc(SH.hours(i,lang))}</span>${s[4]?' · ♿ '+esc(t.ramp):''}</small></button>`; },
  // the line of a pin's card: the nearest of the strong kind (2 km at most), and the nearest of any kind when nearer
  line(lon,lat,lang){ if(!SH.D||!SH.inCity(lon,lat)) return null;
    const st=SH.near(lon,lat,{strong:true,max:LINE_STRONG_KM})[0]||null, an=SH.near(lon,lat,{max:LINE_ANY_KM})[0]||null;
    if(!st&&!an) return null;
    return {st,an:an&&(!st||(an[0]!==st[0]&&an[1]<st[1]-0.1))?an:null}; },
  lineHTML(lon,lat,lang){ const l=SH.line(lon,lat,lang); if(!l) return ''; const t=L(lang), a=l.st||l.an, i=a[0];
    return `<span class="shg" aria-hidden="true">🛡</span><div><b>${esc(SH.name(i,lang))}</b><small>${esc(SH.D.s[i][5]||'')} · ${esc(SH.hours(i,lang))}`
      +`${l.st&&l.an?' · '+esc(t.any1+' '+SH.dist(l.an[1],lang)):''}</small></div><div class="km">${esc(SH.dist(a[1],lang))}<small>${esc(t.short)}</small></div>`; },
  // the list: the three nearest of the strong kinds, the three nearest of the others, what the list is and is not
  listHTML(lon,lat,lang,place){ const t=L(lang); if(!SH.D) return '';
    // one row per address: a station's three entrances are one place to go
    const uniq=a=>{ const seen=new Set(); return a.filter(([i])=>{ const k=SH.D.s[i][5]||i; if(seen.has(k)) return false; seen.add(k); return true; }).slice(0,3); };
    const st=uniq(SH.near(lon,lat,{strong:true,n:12})), an=uniq(SH.near(lon,lat,{weak:true,n:12}));
    let h=`<div class="type">🛡 ${esc(t.title)}</div>`+(place?`<div class="kv1 muted">${esc(fmt(t.from,place))} · ${esc(t.line)}</div>`:'');
    if(!st.length&&!an.length) h+=`<div class="kv1">${esc(fmt(t.none,LIST_KM))}</div>`;
    if(st.length) h+=`<div class="shh">${esc(t.strong)}</div>`+st.map(([i,d])=>SH.row(i,d,lang)).join('');
    if(an.length) h+=`<div class="shh">${esc(t.any)}</div>`+an.map(([i,d])=>SH.row(i,d,lang)).join('');
    return h+SH.footHTML(lang); },
  // one shelter, tapped on the map; d: its distance from the pin, if there is one
  oneHTML(i,lang,d,place){ const s=SH.D.s[i], t=L(lang);
    return `<div class="type">🛡 ${esc(SH.name(i,lang))}</div><div class="kv1"><b>${esc(s[5]||'—')}</b></div>`
      +(d!=null?`<div class="kv1 muted">${esc(SH.dist(d,lang))} ${esc(fmt(t.from,place||''))} · ${esc(t.line)}</div>`:'')
      +`<div class="kv1"><span class="${SH.open24(i)?'h24':'hx'}">${esc(SH.hours(i,lang))}</span>${s[4]?' · ♿ '+esc(t.ramp):''}</div>`
      +(s[7]?`<div class="kv1">${esc(t.tel)} <a href="tel:${esc(s[7].replace(/[^\d+]/g,''))}">${esc(s[7])}</a></div>`:'')
      +(s[8]?`<div class="kv1 muted">${esc(s[8])}</div>`:'')+SH.footHTML(lang); },
  // the Light page: one line under the place's status while an alert concerns it; a tap lists more. Its look is here,
  // so the page itself stays light (tests/test_light.py)
  light(e,p,k,lang,place,paint){ if(!e) return;
    if(!p||k==='G'||!SH.inCity(p.lon,p.lat)){ e.hidden=true; return; }
    if(!SH.D){ e.hidden=true; SH.load().then(paint,()=>{}); return; }
    if(!SH.light.css){ SH.light.css=1; const st=document.createElement('style'); st.textContent=LIGHT_CSS; document.head.appendChild(st);
      e.addEventListener('click',ev=>{ if(ev.target.closest('a')) return; e.o=!e.o; paint(); }); }
    const h=e.o?SH.listHTML(p.lon,p.lat,lang,place):SH.lineHTML(p.lon,p.lat,lang); if(e._h!==h){ e._h=h; e.innerHTML=h; } e.hidden=!h; },
  asof(lang){ try{ return new Date(SH.D.asof+'T12:00:00Z').toLocaleDateString({uk:'uk-UA',fr:'fr-FR'}[lang]||'en-GB',{day:'numeric',month:'long',year:'numeric'}).replace(/\s*р\.$/,''); }catch(e){ return SH.D.asof; } },
  footHTML(lang){ const t=L(lang);
    return `<div class="kv1 shout">${esc(t.out)}</div><div class="kv1 muted">${esc(fmt(t.note,SH.asof(lang)))} <a href="${esc(SH.D.url)}" target="_blank" rel="noopener">${esc(t.map)}</a></div>`; }};
window.SH=SH;
})();
