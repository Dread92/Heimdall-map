// 1.58.16 — the outlines of the hromadas, shared by the Tactical and the Light page.
//
// The official «Повітряна тривога» data names some alerts by hromada ("м. Нікополь та Нікопольська територіальна
// громада"). Until 1.58.16 the map had no shapes for them: such an alert coloured its whole raion, and a place in
// that raion read "alert in part of your raion". static/hromadas/<oblast uid>.json (scripts/build_hromadas.py, from
// OCHA's COD-AB, CC BY 3.0 IGO) holds the outline of each official hromada, in the map's own kilometres. It is fetched
// for an oblast only once an official alert there names a hromada (about 30 KB gzipped). Until it is here — or for a
// hromada with no outline — everything works as before. The test is made on the phone: no place is ever sent.
var HROMADA=(function(){
  var files={}, asked={};
  // the outlines are right to a few hundred metres: a house this close to the line belongs to both sides — it gets
  // the hromada's alert, never neither (the Light page's rule for raions)
  var BORDER_KM=1.5;
  // the official hromada id of an alert ("ua-351" → "351"), or null
  function id(a){ return a&&a.location_type==='hromada'&&/^ua-\d+$/.test(a.location_uid||'')?a.location_uid.slice(3):null; }
  function rings(h){
    if(!h.rings){ h.rings=h.p.map(function(r){ var o=[]; for(var k=0;k<r.length;k+=2) o.push([r[k],r[k+1]]); return o; });
      var b=[1e9,1e9,-1e9,-1e9]; h.rings.forEach(function(g){ g.forEach(function(q){ b[0]=Math.min(b[0],q[0]); b[1]=Math.min(b[1],q[1]); b[2]=Math.max(b[2],q[0]); b[3]=Math.max(b[3],q[1]); }); });
      h.bb=b; }
    return h.rings;
  }
  // the outline of the hromada an alert names: {id, o (oblast), r (parent raion key), uk, en, p, rings, bb} — or null
  function of(a){ var i=id(a), f=i&&files[a.oblast_uid], h=f&&f.h[i]; if(!h) return null; rings(h);
    return {id:i, o:a.oblast_uid, r:h.r, uk:h.uk, en:h.en, p:h.p, rings:h.rings, bb:h.bb}; }
  // fetch the outlines of each oblast that has a hromada alert among `active` (and that `want` accepts, when given);
  // `done(oblast)` once one has arrived. A failed fetch is tried again a minute later.
  function need(active, done, want){
    (active||[]).forEach(function(a){ var o=a.oblast_uid; if(!id(a)||files[o]||(want&&!want(a))) return;
      if(asked[o]&&Date.now()-asked[o]<60000) return; asked[o]=Date.now();
      fetch('/static/hromadas/'+encodeURIComponent(o)+'.json').then(function(r){ return r.ok?r.json():null; })
        .then(function(j){ if(j&&j.h){ files[o]=j; if(done) done(o); } }).catch(function(){}); });
  }
  function inside(x,y,rs){ var c=false;
    rs.forEach(function(g){ for(var i=0,j=g.length-1;i<g.length;j=i++){ var xi=g[i][0],yi=g[i][1],xj=g[j][0],yj=g[j][1];
      if(((yi>y)!==(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi)) c=!c; } });
    return c; }
  function edge(x,y,rs){ var best=1e9;
    rs.forEach(function(g){ for(var i=0,j=g.length-1;i<g.length;j=i++){ var ax=g[j][0],ay=g[j][1],dx=g[i][0]-ax,dy=g[i][1]-ay,L=dx*dx+dy*dy||1e-9;
      var u=Math.max(0,Math.min(1,((x-ax)*dx+(y-ay)*dy)/L)); best=Math.min(best,Math.hypot(ax+u*dx-x,ay+u*dy-y)); } });
    return best; }
  // is the point (x, y in the map's km) in the hromada, or within BORDER_KM of its outline?
  function covers(h,x,y){ var b=h.bb, m=BORDER_KM;
    if(x<b[0]-m||x>b[2]+m||y<b[1]-m||y>b[3]+m) return false;
    return inside(x,y,h.rings)||edge(x,y,h.rings)<=m; }
  // an SVG path of the outline (holes included: draw it with fill-rule evenodd)
  function path(h,f){ f=f||function(x,y){ return x+','+y; };
    return h.p.map(function(r){ var s='M'+f(r[0],r[1]); for(var k=2;k<r.length;k+=2) s+=' '+f(r[k],r[k+1]); return s+'Z'; }).join(''); }
  // `load(oblast, data)`: outlines already at hand (the tests, run with node)
  function load(o,j){ files[o]=j; }
  return {id:id, of:of, need:need, covers:covers, path:path, load:load, BORDER_KM:BORDER_KM};
})();
if(typeof module!=='undefined') module.exports=HROMADA;
