// Heimdall 1.57.2 — the Light radar's background: plain (the default), the satellite picture or the street map, as on
// the Tactical map. The owner: "the light version should show the satellite / map too". Loaded only when a reader asks
// for it (the button on the radar), so the page itself stays light (tests/test_light.py); the choice is kept on the
// phone (localStorage `lbg`).
//
// The pins never leave the phone, and a picture under the radar must not say where one is: the radar is centred on the
// place, so the tiles of exactly its 60 km would. The tiles asked for cover the view as seen from the ~10 km cell the
// place is in (the cell the push stores, HOME_CELL_KM in app/server.py) with the cell's margin round it — every place of
// one cell asks for the same tiles. Fewer than 50 tiles a view: one zoom less rather than more.
(function(){
'use strict';
const CELL_LAT=10/111, CELL_LON=10/71, MARGIN_KM=7.5, MAX_TILES=49;
const ATTR={sat:'© ESA WorldCover 2021 · contains modified Copernicus Sentinel data (2021)',
  map:'Powered by Esri · Esri, TomTom, Garmin, FAO, NOAA, USGS, © OpenStreetMap contributors, and the GIS User Community'};
const MORE={uk:'більше даних',en:'uses more data',fr:'plus de données'};
const CSS='#rwrap.tl #radar{position:relative;z-index:1}#rwrap.tl #radar .bg{fill:rgba(10,13,18,.45)}'
  +'#rwrap.tl #radar .rb{stroke:rgba(200,210,225,.45)}#rwrap.tl #radar .obl{stroke:rgba(230,236,245,.75)}'
  +'#rtile{position:absolute;left:0;top:0;width:100%;height:auto;pointer-events:none}#rtile image{opacity:.9}#rwrap.empty #rtile,#rwrap.empty~#rtattr{display:none}'
  +'#rtattr{margin:2px 8px 0;font:10.5px/1.3 sans-serif;color:var(--ink3);text-align:center}'
  +'#rtmenu{position:absolute;right:54px;top:4px;z-index:3;display:flex;flex-direction:column;gap:4px;padding:6px;border:1px solid var(--line);border-radius:4px;background:rgba(22,27,36,.97)}'
  +'#rtmenu b{font:700 12px sans-serif;color:var(--ink3);text-transform:uppercase;letter-spacing:.04em}'
  +'#rtmenu button{min-width:120px;min-height:40px;padding:0 10px;text-align:left;border:1px solid var(--line);border-radius:4px;background:none;color:var(--ink);font:600 15px sans-serif}'
  +'#rtmenu button.on{border-color:#5aa9ff;background:rgba(90,169,255,.14)}#rtmenu button:disabled{opacity:.35}#rtmenu small{font:11px sans-serif;color:var(--ink3)}';
const get=()=>{ try{ return localStorage.getItem('lbg')||''; }catch(e){ return ''; } };
const put=v=>{ try{ if(v) localStorage.setItem('lbg',v); else localStorage.removeItem('lbg'); }catch(e){} };
const tr=k=>(typeof t==='function'?t(k):k);
const lang=()=>(typeof LANG!=='undefined'?LANG:'en');
// what the server has: its own satellite tiles (their version, their deepest zoom), Esri's street map
function avail(){ const c=(typeof STATE!=='undefined'&&STATE&&STATE.config)||{};
  return {sat:!!c.sat, v:String(c.sat_v||'1'), zmax:Math.max(5,Math.min(16,+c.sat_z||12)), map:c.esri_st===undefined?!!c.esri:!!c.esri_st}; }
const n2lon=(x,n)=>x/n*360-180, n2lat=(y,n)=>Math.atan(Math.sinh(Math.PI*(1-2*y/n)))*180/Math.PI;
const lon2n=(lon,n)=>(lon+180)/360*n, lat2n=(lat,n)=>{ const f=lat*Math.PI/180; return (1-Math.log(Math.tan(f)+1/Math.cos(f))/Math.PI)/2*n; };
let KEY='', PLACE='';
const LT={
  base:get(),
  // the tiles for the radar's view around place p: [{k, x, y, w, h, href}] in radar units
  tiles(p,base,a,rz,pxw,dpr){
    const kx=111*Math.cos(p.lat*Math.PI/180), half=66/rz.z/S;                       // km from the view's centre to its edge
    const clon=p.lon+rz.cx/S/kx, clat=p.lat-rz.cy/S/111;                            // the view's centre
    const slon=Math.round(clon/CELL_LON)*CELL_LON, slat=Math.round(clat/CELL_LAT)*CELL_LAT;   // its cell's
    const r=half+MARGIN_KM, lo0=slon-r/kx, lo1=slon+r/kx, la0=slat-r/111, la1=slat+r/111;
    const mpx=(2*half*1000)/Math.max(1,pxw)/(dpr||1);                               // metres per device pixel
    let z=Math.round(Math.log2(156543*Math.cos(p.lat*Math.PI/180)/mpx));
    const zmin=base==='sat'?5:4, zmax=base==='sat'?a.zmax:18;
    if(base==='map') z-=1;                                                          // Esri's map tiles are 512 px
    z=Math.max(zmin,Math.min(zmax,z));
    let n, x0, x1, y0, y1;
    for(;;){ n=2**z; x0=Math.floor(lon2n(lo0,n)); x1=Math.floor(lon2n(lo1,n)); y0=Math.floor(lat2n(la1,n)); y1=Math.floor(lat2n(la0,n));
      if((x1-x0+1)*(y1-y0+1)<=MAX_TILES||z<=zmin) break; z--; }
    const loc=(lon,lat)=>[(lon-p.lon)*kx*S,-(lat-p.lat)*111*S], out=[];
    for(let x=x0;x<=x1;x++) for(let y=y0;y<=y1;y++){ const [ax,ay]=loc(n2lon(x,n),n2lat(y,n)), [bx,by]=loc(n2lon(x+1,n),n2lat(y+1,n));
      out.push({k:`${base}/${z}/${x}/${y}`, x:ax, y:ay, w:bx-ax, h:by-ay,
        href:base==='sat'?`/tiles/sat/${z}/${x}/${y}.webp?v=${a.v}`:`/tiles/esri/mapn/${z}/${x}/${y}.png?lang=${lang()}`}); }
    return out; },
  draw(p){ const wrap=document.getElementById('rwrap'), rad=document.getElementById('radar'); if(!wrap||!rad) return;
    const a=avail(), base=LT.base==='sat'&&a.sat?'sat':LT.base==='map'&&a.map?'map':'';
    let sv=document.getElementById('rtile'), at=document.getElementById('rtattr');
    wrap.classList.toggle('tl',!!(base&&p));
    if(!base||!p){ if(sv) sv.remove(); if(at) at.remove(); KEY=''; return; }
    if(!sv){ sv=document.createElementNS('http://www.w3.org/2000/svg','svg'); sv.id='rtile';
      sv.innerHTML='<defs><clipPath id="rtclip"><circle r="60"/></clipPath></defs><g clip-path="url(#rtclip)"></g>';
      wrap.insertBefore(sv,wrap.firstChild);
      // the radar's zoom and pan move the picture at once, not at the next paint
      new MutationObserver(()=>{ const s2=document.getElementById('rtile'); if(s2) s2.setAttribute('viewBox',rad.getAttribute('viewBox')); }).observe(rad,{attributes:true,attributeFilter:['viewBox']}); }
    sv.setAttribute('viewBox',rad.getAttribute('viewBox')||'-66 -66 132 132');
    if(!at){ at=document.createElement('div'); at.id='rtattr'; wrap.parentNode.insertBefore(at,wrap.nextSibling); }
    at.textContent=ATTR[base];
    const rz=typeof RZ!=='undefined'?RZ:{z:1,cx:0,cy:0}, w=rad.getBoundingClientRect().width||400;
    const pk=p.lon+','+p.lat, key=[base,pk,rz.z.toFixed(3),rz.cx.toFixed(1),rz.cy.toFixed(1),a.v,lang(),Math.round(w)].join('|');
    if(key===KEY) return; KEY=key;
    const g=sv.querySelector('g'); if(PLACE!==pk+base){ g.innerHTML=''; PLACE=pk+base; }
    const want=LT.tiles(p,base,a,rz,w,window.devicePixelRatio||1), have={};
    g.querySelectorAll('image').forEach(im=>{ have[im.dataset.k]=im; });
    const keep=new Set(want.map(q=>q.k));
    for(const q of want){ if(have[q.k]) continue;
      const im=document.createElementNS('http://www.w3.org/2000/svg','image'); im.dataset.k=q.k;
      im.setAttribute('x',q.x.toFixed(3)); im.setAttribute('y',q.y.toFixed(3)); im.setAttribute('width',q.w.toFixed(3)); im.setAttribute('height',q.h.toFixed(3));
      im.setAttribute('preserveAspectRatio','none'); im.setAttribute('href',q.href); g.appendChild(im); }
    // the tiles of another zoom go once the new ones have come (2 s at most): no black between two pictures
    const old=Object.keys(have).filter(k=>!keep.has(k)).map(k=>have[k]);
    if(old.length) setTimeout(()=>old.forEach(im=>im.remove()),2000); },
  // the button's menu: plain, satellite, map — what the server has; the choice is kept on this phone
  menu(){ let m=document.getElementById('rtmenu'); if(m){ m.remove(); return; }
    const a=avail(), b=LT.base, o=(v,k,ok)=>`<button type="button" data-v="${v}"${b===v?' class="on"':''}${ok?'':' disabled'}>${tr(k)}${v?`<br><small>${MORE[lang()]||MORE.en}</small>`:''}</button>`;
    m=document.createElement('div'); m.id='rtmenu'; m.innerHTML=`<b>${tr('l_base')}</b>`+o('','l_plain',true)+o('sat','l_sat',a.sat)+o('map','l_map',a.map);
    document.getElementById('rwrap').appendChild(m);
    m.addEventListener('click',e=>{ const bt=e.target.closest('button[data-v]'); if(!bt||bt.disabled) return;
      LT.base=bt.dataset.v; put(LT.base); m.remove(); KEY=''; if(typeof paint==='function') paint(); });
    setTimeout(()=>document.addEventListener('click',function off(e){ if(!m.contains(e.target)&&!e.target.closest('#zbg')){ m.remove(); } document.removeEventListener('click',off); }),0); }};
const st=document.createElement('style'); st.textContent=CSS; document.head.appendChild(st);
window.LT=LT;
})();
