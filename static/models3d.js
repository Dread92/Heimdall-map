// Heimdall — the threats in 3D (1.58.45). The owner: "could you make some little animated threejs icon for every threat
// that we have" — on the map's marks, in the hover card and in the sheet. And of a Banderol drawn as a "?" disc
// because its post gave no course: "if the target is correctly identified like here, then display a real logo … it needs
// to be a 3D model".
//
// Loaded only by the Tactical page, and only when it can use it (kyiv.html's M3 block): never on Light, in the
// blackout and night looks, with "save data", without WebGL. three.js (static/vendor/three-m3d.min.js, MIT — only the
// parts used here, scripts/build_three.sh) is fetched after the map is up, never before it.
//
// Nothing here is drawn live. Each weapon is built once from plain shapes, then photographed into a strip of frames
// (a sprite sheet) by one small offscreen renderer; the page plays the strip with CSS. Fifty marks during a raid cost
// fifty <image>s, not fifty WebGL scenes, and the renderer is released when the strips are made.
//
// The rules the silhouettes keep (glyphs.js, docs/SAFETY.md) hold here too:
//   - "top" is the mark seen from above and a little behind, nose up — the page turns it ONLY to a course a post
//     reported (orientOf), exactly like the silhouette it replaces;
//   - "spin" turns the weapon on itself without stopping: for a mark whose post gave no course (the old "?" disc) and
//     for the card and the sheet. A model that never holds a heading cannot be read as one;
//   - the colour is the mark's own (the page reads it from the silhouette underneath): orange for a Shahed, red for a
//     missile, pink-red heading for the reader's place, grey when stale — the 3D changes the picture, never the warning.
// Every model is about 24 units nose to tail in a 28-unit frame, the silhouettes' box, so a mark keeps its size.

import * as T from './vendor/three-m3d.min.js';

export const KEYS = ['drone', 'jetdrone', 'banderol', 'missile', 'ballistic', 'supersonic', 'bomb', 'fighter', 'bomber', 'unknown'];
export const VIEWS = {top: {n: 8, dur: 0.8}, spin: {n: 24, dur: 3.2}};   // ten and eight frames a second: alive, not busy
const FRAME = 28;                     // world units across a frame (glyphs.js: viewBox -14 -14 28 28)

// ---- shapes ---------------------------------------------------------------------------------------------------------
// The world is Z up; a model lies in the XY plane, nose towards +Y, as the silhouettes are drawn nose-up.
const V = (x, y) => new T.Vector2(x, y);
// a body of revolution along Y from a profile [[r, y], …] (nose first)
function body(prof, mat, seg = 20) {
  const g = new T.LatheGeometry(prof.map(([r, y]) => V(Math.max(r, 0.0001), y)).reverse(), seg);
  return new T.Mesh(g, mat);
}
// a flat plate (wing, tailplane) from its outline seen from above, mirrored in X; th = thickness, z = height
function plate(pts, th, mat, z = 0, mirror = true) {
  const g = new T.Group();
  for (const s of mirror ? [1, -1] : [1]) {
    const sh = new T.Shape(pts.map(([x, y]) => V(x * s, y)));
    const geo = new T.ExtrudeGeometry(sh, {depth: th, bevelEnabled: false});
    const m = new T.Mesh(geo, mat); m.position.z = z - th / 2; g.add(m);
  }
  return g;
}
// a fin standing on the body: outline [[y, h], …] in its own plane, turned `ang` degrees about the nose axis
// (0 = straight up, 90 = out to the right), set `off` units out from the axis
function fin(pts, th, mat, ang = 0, off = 0) {
  const geo = new T.ExtrudeGeometry(new T.Shape(pts.map(([y, h]) => V(y, h))), {depth: th, bevelEnabled: false});
  // shape X → along the body (Y), shape Y → up (Z), the extrusion → across (X), centred on its thickness
  geo.rotateX(Math.PI / 2); geo.rotateZ(Math.PI / 2); geo.translate(-th / 2, 0, 0);
  const m = new T.Mesh(geo, mat); m.position.z = off;
  const holder = new T.Group(); holder.add(m);
  holder.rotation.y = ang * Math.PI / 180;     // about the nose axis (Y): 0 up, 90 right
  return holder;
}
function cyl(r0, r1, y0, y1, mat, x = 0, z = 0, seg = 16) {
  const top = y0 > y1 ? r0 : r1, bot = y0 > y1 ? r1 : r0;          // CylinderGeometry: radiusTop is +Y's end
  const m = new T.Mesh(new T.CylinderGeometry(top, bot, Math.abs(y1 - y0), seg), mat);
  m.position.set(x, (y0 + y1) / 2, z); return m;
}
// the exhaust: an outer flame and a white core along -Y from y0; flickers by scale (anim)
function flame(y0, len, r, x = 0, z = 0) {
  const g = new T.Group(); g.position.set(x, y0, z);
  const outer = new T.Mesh(new T.ConeGeometry(r, len, 14, 1, true), MAT.flame);
  outer.rotation.x = Math.PI; outer.position.y = -len / 2; g.add(outer);
  const core = new T.Mesh(new T.ConeGeometry(r * 0.5, len * 0.55, 12, 1, true), MAT.core);
  core.rotation.x = Math.PI; core.position.y = -len * 0.275; g.add(core);
  g.userData.flame = true; return g;
}
// a propeller turning about Y: blades and the blur of them
function prop(y, r, blades, x = 0, z = 0) {
  const g = new T.Group(); g.position.set(x, y, z);
  const rot = new T.Group(); g.add(rot);
  for (let i = 0; i < blades; i++) {
    const b = new T.Mesh(new T.BoxGeometry(0.42, 0.14, r), MAT.dark);
    b.position.z = r / 2; const p = new T.Group(); p.rotation.y = i * 2 * Math.PI / blades; p.add(b); rot.add(p);
  }
  const disc = new T.Mesh(new T.CircleGeometry(r, 24), MAT.blur); disc.rotation.x = Math.PI / 2; g.add(disc);
  g.userData.prop = rot; g.userData.blades = blades; return g;
}

const MAT = {};
function mats(col) {
  const c = new T.Color(col);
  MAT.skin = new T.MeshStandardMaterial({color: c, metalness: 0.25, roughness: 0.5});
  MAT.skin2 = new T.MeshStandardMaterial({color: c.clone().multiplyScalar(0.72), metalness: 0.3, roughness: 0.55});
  MAT.dark = new T.MeshStandardMaterial({color: '#20262e', metalness: 0.4, roughness: 0.5});
  MAT.glass = new T.MeshStandardMaterial({color: '#0d1620', metalness: 0.8, roughness: 0.15});
  MAT.blur = new T.MeshBasicMaterial({color: '#cfd6df', transparent: true, opacity: 0.22, side: T.DoubleSide, depthWrite: false});
  MAT.flame = new T.MeshBasicMaterial({color: '#ffb347', transparent: true, opacity: 0.85, side: T.DoubleSide, depthWrite: false});
  MAT.core = new T.MeshBasicMaterial({color: '#fff4d6', transparent: true, opacity: 0.95, side: T.DoubleSide, depthWrite: false});
  MAT.sign = new T.MeshStandardMaterial({color: '#080b10', metalness: 0.1, roughness: 0.6});
}

// ---- the weapons (outlines after glyphs.js, so a mark keeps its silhouette) ---------------------------------------------
const BUILD = {
  // Shahed-136: slim body, a big delta from just behind the nose, fins at the wingtips (above and below), pusher propeller
  drone() {
    const g = new T.Group();
    g.add(body([[0, 11.6], [1.1, 10], [1.7, 7.6], [1.7, -5.2], [1.25, -6.6], [0.8, -7.4]], MAT.skin));
    g.add(plate([[0.8, 4.6], [10.4, -5.4], [10.4, -6.3], [0.8, -6.3]], 0.45, MAT.skin));
    for (const s of [1, -1]) {
      const up = fin([[-2.4, 0], [-5.4, 0], [-6.3, 2.4], [-3.4, 2.4]], 0.3, MAT.skin2); up.position.x = 10.2 * s; g.add(up);
      const dn = fin([[-2.6, 0], [-5.6, 0], [-6.3, -1.6], [-3.6, -1.6]], 0.3, MAT.skin2); dn.position.x = 10.2 * s; g.add(dn);
    }
    g.add(cyl(0.8, 0.55, -7.4, -8.1, MAT.dark));
    g.add(prop(-8.3, 2.7, 2));
    return g;
  },
  // the same airframe with a turbojet on its spine and a flame — what tells a jet one from a Shahed
  jetdrone() {
    const g = BUILD.drone(); g.children.filter(c => c.userData.prop).forEach(c => g.remove(c));
    g.add(cyl(1.0, 1.15, 0.6, -6.6, MAT.skin2, 0, 1.75));
    g.add(cyl(1.15, 0.85, -6.6, -7.6, MAT.dark, 0, 1.75));
    const ring = new T.Mesh(new T.CylinderGeometry(1.05, 1.05, 0.3, 16, 1, true), MAT.dark); ring.position.set(0, 0.7, 1.75); g.add(ring);
    g.add(flame(-7.6, 5.4, 0.8, 0, 1.75));
    return g;
  },
  // S8000 Banderol: slim body, straight wings mid-body, the small turbojet on its back behind them, an X tail
  banderol() {
    const g = new T.Group();
    g.add(body([[0, 11.6], [1.0, 9.6], [1.55, 7.2], [1.55, -7.2], [1.1, -8.4]], MAT.skin));
    g.add(plate([[1.2, 1.2], [10.6, -1.3], [10.6, -2.8], [1.2, -2.2]], 0.35, MAT.skin));
    g.add(cyl(0.75, 0.85, -2.6, -6.4, MAT.skin2, 0, 1.55));
    g.add(cyl(0.85, 0.6, -6.4, -7.0, MAT.dark, 0, 1.55));
    g.add(flame(-7.0, 4.2, 0.55, 0, 1.55));
    for (const a of [45, 135, 225, 315]) g.add(fin([[-5.6, 0], [-8.2, 0], [-8.4, 2.6], [-7.0, 2.6]], 0.22, MAT.skin2, a, 1.1));
    return g;
  },
  // a cruise missile (Kh-101 / Kalibr class): a long body, small swept wings, a cross tail, the engine under the tail
  missile() {
    const g = new T.Group();
    g.add(body([[0, 12], [0.8, 10.2], [1.25, 8.4], [1.25, -8.6], [0.95, -9.6]], MAT.skin));
    g.add(plate([[1.0, 0.8], [5.6, -1.6], [5.6, -2.6], [1.0, -1.6]], 0.28, MAT.skin));
    for (const a of [0, 90, 180, 270]) g.add(fin([[-7.4, 0], [-9.6, 0], [-9.8, 1.7], [-8.6, 1.7]], 0.2, MAT.skin2, a, 0.9));
    g.add(cyl(0.6, 0.7, -5.2, -8.8, MAT.skin2, 0, -1.35));
    g.add(flame(-8.8, 2.6, 0.45, 0, -1.35));
    return g;
  },
  // a ballistic missile (Iskander class): a thick body, a long ogive, four fins at the base, a big plume; it rolls
  ballistic() {
    const g = new T.Group();
    g.add(body([[0, 12], [0.9, 10.4], [1.7, 7.8], [2.1, 5.6], [2.1, -8.0], [1.8, -8.6]], MAT.skin, 24));
    const band = cyl(2.13, 2.13, 2.6, 2.0, MAT.skin2); g.add(band);
    for (const a of [45, 135, 225, 315]) g.add(fin([[-5.4, 0], [-8.6, 0], [-8.6, 1.7], [-6.6, 1.7]], 0.25, MAT.skin2, a, 1.9));
    g.add(flame(-8.6, 6.2, 1.6));
    g.userData.roll = 90;            // four-fold: a quarter turn per loop is seamless
    return g;
  },
  // Kh-22 (supersonic): a big body, a cropped delta, a tall fin above and a ventral one below
  supersonic() {
    const g = new T.Group();
    g.add(body([[0, 12.5], [1.0, 10], [1.8, 6], [1.9, -10], [1.4, -11.4]], MAT.skin, 22));
    g.add(plate([[1.6, -1.0], [8.4, -7.0], [8.4, -8.6], [1.6, -6.4]], 0.4, MAT.skin));
    g.add(fin([[-4.8, 0], [-11.2, 0], [-11.4, 3.6], [-9.0, 3.6]], 0.3, MAT.skin2, 0, 1.7));
    g.add(fin([[-6.8, 0], [-11.2, 0], [-11.0, 2.0], [-9.6, 2.0]], 0.3, MAT.skin2, 180, 1.7));
    g.add(flame(-11.4, 3.4, 1.0));
    return g;
  },
  // a guided bomb with its glide kit (KAB + UMPK): a fat rounded body, a cross tail, long thin wings on a pylon
  bomb() {
    const g = new T.Group();
    g.add(body([[0, 10.5], [2.0, 9.2], [3.5, 6.6], [4.0, 3], [3.9, -3.6], [2.8, -6.8], [2.3, -7.8]], MAT.skin, 24));
    for (const a of [45, 135, 225, 315]) g.add(fin([[-6.2, 0], [-9.6, 0], [-11.2, 3.0], [-9.4, 3.0]], 0.3, MAT.skin2, a, 2.2));
    g.add(cyl(0.5, 0.5, 1.2, -1.2, MAT.dark, 0, 4.3));
    g.add(plate([[0, 1.0], [11.0, 0.6], [11.0, -0.8], [0, -1.0]], 0.25, MAT.skin2, 4.9));
    return g;
  },
  // a fighter (tactical aviation, MiG-31K): two engines, swept wings, two tails, the afterburners lit
  fighter() {
    const g = new T.Group();
    g.add(body([[0, 12.8], [0.9, 10.8], [1.5, 7.6], [1.6, 3.0], [1.4, -6]], MAT.skin));
    const can = new T.Mesh(new T.SphereGeometry(1, 16, 10), MAT.glass); can.scale.set(0.75, 2.2, 0.6); can.position.set(0, 7.4, 1.2); g.add(can);
    for (const s of [1, -1]) { g.add(cyl(1.05, 1.15, 3.6, -11.4, MAT.skin2, 1.45 * s, -0.2)); g.add(flame(-11.4, 2.8, 0.85, 1.45 * s, -0.2)); }
    g.add(plate([[2.2, 2.6], [9.6, -4.2], [9.6, -6.0], [2.2, -4.6]], 0.3, MAT.skin));
    g.add(plate([[2.4, -7.4], [4.2, -10.4], [4.2, -11.6], [2.4, -11.0]], 0.25, MAT.skin));
    for (const s of [1, -1]) { const f = fin([[-6.4, 0], [-10.8, 0], [-11.6, 3.4], [-9.6, 3.4]], 0.25, MAT.skin2, 12 * s, 0); f.position.x = 1.9 * s; f.position.z = 0.9; g.add(f); }
    return g;
  },
  // a strategic bomber (Tu-95MS): a long body, swept wings, four engines with contra-rotating propellers
  bomber() {
    const g = new T.Group();
    g.add(body([[0, 12], [1.0, 10.6], [1.6, 8.8], [1.6, -8.4], [0.7, -12.4]], MAT.skin));
    g.add(plate([[1.6, 1.2], [12.4, -4.4], [12.4, -6.4], [1.6, -3.4]], 0.35, MAT.skin));
    for (const s of [1, -1]) for (const x of [4.5, 8.2]) {
      const yLe = 1.2 - (x - 1.6) * (5.6 / 10.8);
      g.add(cyl(0.55, 0.45, yLe + 1.4, yLe - 2.4, MAT.skin2, x * s, -0.25));
      g.add(prop(yLe + 1.7, 1.55, 4, x * s, -0.25));
    }
    g.add(plate([[0.6, -8.6], [4.6, -11.2], [4.6, -12.2], [0.6, -11.4]], 0.25, MAT.skin));
    g.add(fin([[-7.6, 0], [-12.2, 0], [-12.4, 3.8], [-10.4, 3.8]], 0.3, MAT.skin2, 0, 1.2));
    return g;
  },
  // not a weapon: the warning sign of a target reported with no type — it never points anywhere
  unknown() {
    const g = new T.Group();
    const tri = new T.Shape([V(0, 9.4), V(9.6, -7.4), V(-9.6, -7.4)]);
    const m = new T.Mesh(new T.ExtrudeGeometry(tri, {depth: 1.6, bevelEnabled: true, bevelThickness: 0.5, bevelSize: 0.6, bevelSegments: 2}), MAT.skin);
    m.position.z = -0.8; g.add(m);
    const bar = new T.Mesh(new T.BoxGeometry(1.7, 6.4, 0.6), MAT.sign); bar.position.set(0, 1.6, 1.3); g.add(bar);
    const dot = new T.Mesh(new T.BoxGeometry(1.8, 1.8, 0.6), MAT.sign); dot.position.set(0, -3.9, 1.3); g.add(dot);
    g.userData.sign = true;
    return g;
  },
};

// ---- posing ---------------------------------------------------------------------------------------------------------
// f in [0, 1): the place in the loop. The propellers and the flame move every frame; a ballistic missile rolls; the
// sign rocks a little. In "spin" the whole model also turns once about its vertical axis.
function pose(holder, model, view, f) {
  // the sign is not turned round (its back is a blank plate): it rocks, facing the reader
  const turn = view !== 'spin' ? 0 : model.userData.sign ? 0.55 * Math.sin(f * 2 * Math.PI) : f * 2 * Math.PI;
  holder.rotation.set(0, 0, 0);
  holder.rotation.z = turn;
  model.rotation.set(0, 0, 0);
  if (model.userData.roll) model.rotation.y = f * model.userData.roll * Math.PI / 180 * (view === 'spin' ? 4 : 1);
  if (model.userData.sign) { model.rotation.x = view === 'spin' ? 1.1 : 0.25 * Math.sin(f * 2 * Math.PI); }
  const fl = 0.82 + 0.18 * Math.abs(Math.sin(f * 37.7 + 1.3)) + 0.08 * Math.sin(f * 91.1);
  model.traverse(o => {
    if (o.userData.prop) o.userData.prop.rotation.y = f * (view === 'spin' ? 9 : 1) * 2 * Math.PI / o.userData.blades;
    if (o.userData.flame) o.scale.set(1, fl, 1);
  });
}

// ---- the camera, the light, the strip -----------------------------------------------------------------------------
let R = null, SCENE = null, CAM = null;
function stage(px) {
  if (!R) {
    const cv = document.createElement('canvas');
    R = new T.WebGLRenderer({canvas: cv, alpha: true, antialias: true, preserveDrawingBuffer: true, powerPreference: 'low-power'});
    R.setClearColor(0x000000, 0);
    R.outputColorSpace = T.SRGBColorSpace;
    SCENE = new T.Scene();
    SCENE.add(new T.HemisphereLight(0xffffff, 0x3a4250, 1.55));
    const key = new T.DirectionalLight(0xffffff, 2.1); key.position.set(-6, 8, 14); SCENE.add(key);
    const rim = new T.DirectionalLight(0xbfd4ff, 0.9); rim.position.set(8, -10, 4); SCENE.add(rim);
    CAM = new T.OrthographicCamera(-FRAME / 2, FRAME / 2, FRAME / 2, -FRAME / 2, 0.1, 200);
  }
  R.setPixelRatio(1); R.setSize(px, px, false);
}
function aim(view) {
  // top: from above and a little behind (20°), nose up; spin: from 26° above the horizon, the model turning
  const el = (view === 'top' ? 70 : 26) * Math.PI / 180, d = 80;
  CAM.position.set(0, -d * Math.cos(el), d * Math.sin(el));
  CAM.up.set(0, view === 'top' ? 1 : 0, view === 'top' ? 0 : 1);
  CAM.lookAt(0, 0, 0);
  const z = view === 'top' ? 1 : 1.06; CAM.zoom = z; CAM.updateProjectionMatrix();
}

// One strip: n frames of `px` side by side, an outline around the shape in the silhouette's own stroke (`line`: near-black
// for a drone, white for a missile, red around a ballistic one's white — it sits on satellite imagery and on red alerts). Resolves to {url, n, dur, px} (a blob: URL — the page's CSP allows blob: images).
export async function sheet(key, view, color, px, line = '#080b10') {
  if (!BUILD[key] || !VIEWS[view]) return null;
  const {n, dur} = VIEWS[view];
  stage(px); aim(view); mats(color);
  const holder = new T.Group(), model = BUILD[key](); holder.add(model); SCENE.add(holder);
  const out = document.createElement('canvas'); out.width = px * n; out.height = px;
  const ctx = out.getContext('2d');
  for (let i = 0; i < n; i++) { pose(holder, model, view, i / n); R.render(SCENE, CAM); ctx.drawImage(R.domElement, i * px, 0); }
  SCENE.remove(holder);
  holder.traverse(o => { if (o.geometry) o.geometry.dispose(); });
  for (const k in MAT) MAT[k].dispose();
  // the outline: the shape in near-black, drawn 8 times around and under it
  const sil = document.createElement('canvas'); sil.width = out.width; sil.height = px;
  const sc = sil.getContext('2d'); sc.drawImage(out, 0, 0); sc.globalCompositeOperation = 'source-in'; sc.fillStyle = line; sc.fillRect(0, 0, sil.width, px);
  const o = Math.max(1, Math.round(px / 64));
  ctx.globalCompositeOperation = 'destination-over';
  for (let i = 0; i < n; i++) {       // frame by frame: an outline must not bleed into the next frame
    ctx.save(); ctx.beginPath(); ctx.rect(i * px, 0, px, px); ctx.clip();
    for (const [dx, dy] of [[o, 0], [-o, 0], [0, o], [0, -o], [o, o], [-o, -o], [o, -o], [-o, o]]) ctx.drawImage(sil, i * px, 0, px, px, i * px + dx, dy, px, px);
    ctx.restore();
  }
  ctx.globalCompositeOperation = 'source-over';
  const blob = await new Promise(res => out.toBlob(res, 'image/png'));
  if (!blob) return null;
  return {url: URL.createObjectURL(blob), n, dur, px};
}

// Can this browser draw it? (A WebGL context that fails, or a software one that would make a phone hot, says no.)
export async function init() {
  try {
    stage(32);
    const gl = R.getContext();
    return !!gl && !gl.isContextLost();
  } catch (e) { R = null; return false; }
}
// The strips are made; the renderer can go (its context is one of the few a page may hold).
export function release() { if (R) { R.dispose(); R.forceContextLoss(); R = null; SCENE = null; CAM = null; } }
