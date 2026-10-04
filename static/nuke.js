// Heimdall — the nuclear event (1.32).
// Loaded by the two pages only when the server's state carries `nuke`: the dashboard switches it on behind two locks
// (a one-time code from the server, then the phrase typed in full, then a 3-second hold). It draws the radiation
// symbol over the whole map, pulsing, and a banner with the admin's text, what this app is not, and (1.35) a link to
// what to do in a radiation danger (/guide#rad).
// The pulse is one cycle every 1.6 s — far under the three flashes a second that can trigger a seizure — and it
// holds still for a reader whose phone asks for less motion. The admin's text is set as text, never as HTML.
(function(){
  'use strict';
  var TX={
    uk:{h:'ЯДЕРНА ПОДІЯ — РАДІАЦІЙНА НЕБЕЗПЕКА',f:'Heimdall — неофіційний застосунок, а не система оповіщення. Дійте за вказівками ДСНС і місцевої влади.',min:'Згорнути текст',max:'Показати текст',g:'Що робити при радіаційній небезпеці →'},
    en:{h:'NUCLEAR EVENT — RADIATION DANGER',f:'Heimdall is an unofficial app, not an alert system. Follow the instructions of the State Emergency Service (ДСНС) and local authorities.',min:'Hide the text',max:'Show the text',g:'What to do in a radiation danger →'},
    fr:{h:'ÉVÉNEMENT NUCLÉAIRE — DANGER RADIOLOGIQUE',f:"Heimdall est une application non officielle, pas un système d'alerte. Suivez les consignes du Service d'urgence de l'État (ДСНС) et des autorités locales.",min:'Masquer le texte',max:'Afficher le texte',g:'Que faire en cas de danger radiologique →'}};
  // the trefoil (ISO 361): a disc of radius 1, three 60° blades from 1.5 to 5, one pointing down
  var BL='M0.75 1.299L2.5 4.33A5 5 0 0 1 -2.5 4.33L-0.75 1.299A1.5 1.5 0 0 0 0.75 1.299Z'+
         'M-1.5 0L-5 0A5 5 0 0 1 -2.5 -4.33L-0.75 -1.299A1.5 1.5 0 0 0 -1.5 0Z'+
         'M0.75 -1.299L2.5 -4.33A5 5 0 0 1 5 0L1.5 0A1.5 1.5 0 0 0 0.75 -1.299Z';
  var SYM='<svg viewBox="-6 -6 12 12" aria-hidden="true"><circle r="5.8" fill="#ffd500" stroke="#111" stroke-width=".3"/><circle r="1" fill="#111"/><path fill="#111" d="'+BL+'"/></svg>';
  var CSS=
    '.hnk{position:absolute;inset:0;z-index:5;pointer-events:none;overflow:hidden;display:flex;align-items:center;justify-content:center}'+
    '.hnkw{position:absolute;inset:0;background:radial-gradient(circle at 50% 50%,rgba(255,213,0,.14) 0,rgba(255,213,0,.05) 40%,rgba(196,18,28,.32) 100%);'+
      'box-shadow:inset 0 0 0 4px rgba(196,18,28,.9);animation:hnkw 1.6s ease-in-out infinite}'+
    '.hnks{position:relative;width:min(58%,52vh);max-width:420px;animation:hnkp 1.6s ease-in-out infinite;filter:drop-shadow(0 0 16px rgba(255,213,0,.5))}'+
    '.hnks svg{display:block;width:100%;height:auto}'+
    '@keyframes hnkw{0%,100%{opacity:.5;box-shadow:inset 0 0 0 4px rgba(196,18,28,.9)}50%{opacity:1;box-shadow:inset 0 0 0 4px rgba(255,213,0,.95)}}'+
    '@keyframes hnkp{0%,100%{transform:scale(.9);opacity:.5}50%{transform:scale(1);opacity:.85}}'+
    '.hnkc{background:#c4121c;color:#fff;border-left:6px solid #ffd500;padding:8px 10px 9px 12px;font:500 13.5px/1.4 system-ui,-apple-system,sans-serif}'+
    '.hnkc.flow{margin:0 14px 10px;border-radius:3px}'+
    '.hnkh{display:flex;align-items:center;gap:9px}'+
    '.hnkh b{flex:1;min-width:0;font:800 13.5px/1.2 system-ui,-apple-system,sans-serif;letter-spacing:.05em}'+
    '.hnki{flex:none;width:26px;height:26px}.hnki svg{display:block;width:100%;height:100%}'+
    '.hnkx{flex:none;background:transparent;border:1px solid rgba(255,255,255,.65);color:#fff;width:34px;height:32px;border-radius:4px;font-size:13px;cursor:pointer}'+
    '.hnkt{margin-top:6px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:28vh;overflow:auto;font-size:14.5px}'+
    '.hnkf{margin-top:6px;font-size:12px;color:#ffe3e3}'+
    '.hnkg{display:inline-block;margin-top:6px;color:#fff;font-weight:700;text-decoration:underline}'+
    '.hnkc.min .hnkt,.hnkc.min .hnkf,.hnkc.min .hnkg{display:none}'+
    '@media (prefers-reduced-motion:reduce){.hnkw,.hnks{animation:none}.hnks{opacity:.8}.hnkw{opacity:.8}}';
  var el=null, card=null, key='';
  function ss(k,v){ try{ if(v===undefined) return sessionStorage.getItem(k); sessionStorage.setItem(k,v); }catch(e){} return null; }
  // n: the state's `nuke` ({id, since, text:{uk,en,fr}}) or null. o: {host: where the symbol goes (the map),
  // before: the element the banner is placed before, lang, alarm(): played once per event on this phone,
  // after(): called when the banner changed height}
  function show(n,o){ o=o||{};
    if(!n||!n.id){ if(el){ el.remove(); el=null; } if(card){ card.remove(); card=null; if(o.after) o.after(); } key=''; return; }
    var lang=TX[o.lang]?o.lang:'uk', k=n.id+'|'+lang+'|'+JSON.stringify(n.text||{});
    if(k===key&&el&&el.isConnected&&card&&card.isConnected) return;
    key=k;
    if(!document.getElementById('hnkcss')){ var st=document.createElement('style'); st.id='hnkcss'; st.textContent=CSS; document.head.appendChild(st); }
    if(o.host&&!(el&&el.isConnected)){ el=document.createElement('div'); el.className='hnk'; el.setAttribute('aria-hidden','true');
      el.innerHTML='<div class="hnkw"></div><div class="hnks">'+SYM+'</div>'; o.host.appendChild(el); }
    if(!(card&&card.isConnected)){ card=document.createElement('div'); card.className='hnkc'+(o.flow?' flow':''); card.setAttribute('role','alert');
      if(o.before&&o.before.parentNode) o.before.parentNode.insertBefore(card,o.before); else if(o.host) o.host.appendChild(card); }
    var T=TX[lang], tx=(n.text&&(n.text[lang]||n.text.uk||n.text.en||n.text.fr))||'';
    card.innerHTML='<div class="hnkh"><span class="hnki">'+SYM+'</span><b></b><button type="button" class="hnkx"></button></div><div class="hnkt"></div><div class="hnkf"></div><a class="hnkg" href="/guide#rad"></a>';
    card.querySelector('b').textContent=T.h; card.querySelector('.hnkt').textContent=tx; card.querySelector('.hnkf').textContent=T.f; card.querySelector('.hnkg').textContent=T.g;
    var x=card.querySelector('.hnkx');
    function mini(m){ card.classList.toggle('min',m); x.textContent=m?'▾':'▴'; x.setAttribute('aria-label',m?T.max:T.min); x.title=m?T.max:T.min; if(o.after) o.after(); }
    x.onclick=function(){ var m=!card.classList.contains('min'); ss('nuke_min',m?n.id:''); mini(m); };
    mini(ss('nuke_min')===n.id);
    if(ss('nuke_seen')!==n.id){ ss('nuke_seen',n.id); if(o.alarm){ try{ o.alarm(); }catch(e){} } }
  }
  window.HNuke={show:show};
})();
