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
// 1.58.47: the donation jar (not a threat: no KEYS entry, never on the map) — seen from the front and a little above,
// rocking; photographed once into static/jar3d.webp by scripts/render_jar.js
VIEWS.jar = {n: 36, dur: 4.0};
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
// the exhaust: an outer flame and a white core along -Y from y0; flickers by scale (anim). `big` (1.58.46, the jet drone —
// the owner: "the animation must be clearer, put flames behind the engine to tell it from the normal Shahed"): a third,
// red outer plume, a glowing nozzle and two shock diamonds, and a stronger flicker
function flame(y0, len, r, x = 0, z = 0, big = false) {
  const g = new T.Group(); g.position.set(x, y0, z);
  const cone = (rad, l, mat) => { const m = new T.Mesh(new T.ConeGeometry(rad, l, 14, 1, true), mat); m.rotation.x = Math.PI; m.position.y = -l / 2; g.add(m); return m; };
  if (big) cone(r * 1.45, len * 1.12, MAT.plume);
  cone(r, len, big ? MAT.hot : MAT.flame);
  cone(r * 0.5, len * 0.55, MAT.core);
  if (big) {
    const noz = new T.Mesh(new T.CylinderGeometry(r * 1.05, r * 1.05, 0.25, 18, 1, true), MAT.glow); noz.position.y = -0.1; g.add(noz);
    for (const [at, k] of [[0.3, 0.55], [0.55, 0.38]]) {
      const d = new T.Mesh(new T.SphereGeometry(r * k, 12, 8), MAT.core); d.scale.set(1, 1.9, 1); d.position.y = -len * at; g.add(d);
    }
  }
  g.userData.flame = big ? 2 : 1; return g;
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
  MAT.plume = new T.MeshBasicMaterial({color: '#ff3d00', transparent: true, opacity: 0.42, side: T.DoubleSide, depthWrite: false});
  MAT.hot = new T.MeshBasicMaterial({color: '#ffd23a', transparent: true, opacity: 0.8, side: T.DoubleSide, depthWrite: false});
  MAT.glow = new T.MeshBasicMaterial({color: '#ffd27a', side: T.DoubleSide});
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
    g.add(flame(-7.6, 6.6, 1.3, 0, 1.75, true));
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
  // 1.58.47 — the owner, of the jar button: "make the jar better looking, in three.js — right now it's not really standing
  // out". A glass jar (Y is up here), the lid and a band in the flag's blue and yellow, coins piled inside, one dropping
  // through the slot with a glint; the jar rocks a little. Its own materials: it has no threat colour.
  jar() {
    const g = new T.Group();
    const glass = new T.MeshStandardMaterial({color: '#cfe9ff', emissive: '#16324d', transparent: true, opacity: 0.24, roughness: 0.05,
                                              metalness: 0.1, side: T.DoubleSide, depthWrite: false});
    const shine = new T.MeshBasicMaterial({color: '#ffffff', transparent: true, opacity: 0.42, depthWrite: false, side: T.DoubleSide});
    const rim = new T.MeshStandardMaterial({color: '#ffffff', transparent: true, opacity: 0.55, roughness: 0.1, side: T.DoubleSide, depthWrite: false});
    const gold = new T.MeshStandardMaterial({color: '#ffcf3f', emissive: '#6b4a00', metalness: 0.45, roughness: 0.28});
    const blue = new T.MeshStandardMaterial({color: '#1f63d6', metalness: 0.35, roughness: 0.38});
    const yellow = new T.MeshStandardMaterial({color: '#ffd21f', roughness: 0.45});
    const dark = new T.MeshStandardMaterial({color: '#11151c', roughness: 0.6});
    const spark = new T.MeshBasicMaterial({color: '#fffbe6', transparent: true, opacity: 0.95, depthWrite: false, side: T.DoubleSide});
    // the coins first (inside), the glass drawn over them
    const coin = () => new T.Mesh(new T.CylinderGeometry(1.75, 1.75, 0.5, 20), gold);
    // a pile up to just under the band: layers of coins, each a little tilted (fixed, so every frame is the same pile)
    let n = 0;
    for (let y = -9.9; y < -2.6; y += 0.62) {
      const w = 6.4 - Math.max(0, y + 6) * 0.9;                                  // a mound: narrower towards the top
      for (let a = 0; a < 6.28; a += 1.25) {
        n += 1;
        const r = (n * 0.37) % 1 * w, c = coin();
        c.position.set(Math.cos(a + n) * r, y + (n % 3) * 0.12, Math.sin(a + n) * r);
        c.rotation.set(((n * 13) % 7 - 3) * 0.09, 0, ((n * 7) % 5 - 2) * 0.12); g.add(c);
      }
    }
    const body = new T.Mesh(new T.LatheGeometry([[0, -10.6], [6.8, -10.6], [7.8, -9.6], [8.1, -6], [8.1, 4.2], [7.4, 6.6], [5.9, 7.9], [5.7, 9.2]]
      .map(([r, y]) => V(r, y)), 40), glass);
    body.renderOrder = 2; g.add(body);
    for (const [x, z, h, w, rot] of [[-5.6, 5.6, 12.5, 0.75, 0.78], [-3.9, 6.9, 9, 0.35, 0.5]]) {   // the light on the glass
      const st = new T.Mesh(new T.BoxGeometry(w, h, 0.04), shine); st.position.set(x, -0.6, z); st.rotation.y = -rot; st.renderOrder = 3; g.add(st);
    }
    const ring = new T.Mesh(new T.CylinderGeometry(5.8, 5.8, 0.5, 40, 1, true), rim); ring.position.y = 9.0; ring.renderOrder = 3; g.add(ring);
    const band = new T.Mesh(new T.CylinderGeometry(8.16, 8.16, 3.2, 48, 1, true), yellow); band.position.y = 1.8; g.add(band);
    const band2 = new T.Mesh(new T.CylinderGeometry(8.18, 8.18, 0.6, 48, 1, true), blue); band2.position.y = 3.7; g.add(band2);
    const lid = new T.Mesh(new T.CylinderGeometry(6.3, 6.3, 2.3, 40), blue); lid.position.y = 10.25; g.add(lid);
    const lip = new T.Mesh(new T.CylinderGeometry(6.5, 6.5, 0.6, 40), blue); lip.position.y = 9.35; g.add(lip);
    const slot = new T.Mesh(new T.BoxGeometry(3.4, 0.3, 0.75), dark); slot.position.y = 11.42; g.add(slot);
    const drop = coin(); drop.rotation.x = Math.PI / 2; g.add(drop);                  // on its edge, falling into the slot
    const glint = new T.Group(); glint.position.set(0, 12.6, 0.6);
    for (const r of [0, Math.PI / 2]) { const b = new T.Mesh(new T.BoxGeometry(0.28, 3.4, 0.05), spark); b.rotation.z = r + Math.PI / 4; glint.add(b); }
    g.add(glint);
    g.userData.anim = f => {
      g.rotation.y = 0.38 * Math.sin(f * 2 * Math.PI);                                    // it rocks
      const t = Math.min(1, f / 0.3);                                                      // the coin drops, turning
      drop.visible = f < 0.3;
      drop.position.set(0, 14.8 - 3.6 * t * t, 0);
      drop.rotation.y = f * 14;
      const k = f >= 0.27 && f < 0.48 ? Math.sin((f - 0.27) / 0.21 * Math.PI) : 0;      // and glints going in
      glint.visible = k > 0.02; glint.scale.setScalar(0.4 + 0.9 * k); glint.rotation.z = f * 3;
    };
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
  if (model.userData.anim) model.userData.anim(f);
  model.traverse(o => {
    if (o.userData.prop) o.userData.prop.rotation.y = f * (view === 'spin' ? 9 : 1) * 2 * Math.PI / o.userData.blades;
    // the jet's flame breathes harder: longer and shorter, wider and narrower, so it reads at map size
    if (o.userData.flame === 2) { const k = 0.72 + 0.42 * Math.abs(Math.sin(f * 2 * Math.PI * (view === 'spin' ? 9 : 3) + 0.7)); o.scale.set(0.9 + 0.2 * k, k, 0.9 + 0.2 * k); }
    else if (o.userData.flame) o.scale.set(1, fl, 1);
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
  if (view === 'jar') {                       // Y is up for the jar: from the front, 14° above
    const e = 14 * Math.PI / 180;
    CAM.position.set(0, 80 * Math.sin(e), 80 * Math.cos(e)); CAM.up.set(0, 1, 0); CAM.lookAt(0, 1.2, 0);
    CAM.zoom = 0.94; CAM.updateProjectionMatrix(); return;
  }
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
  // the flames go on a layer of their own, drawn last with a glow and no outline (a black edge made them read as a solid
  // part); the body still hides them where it is in front (its depth is written, not its colour)
  const flames = []; model.traverse(o => { if (o.userData.flame) flames.push(o); });
  const FX = new Set([MAT.flame, MAT.core, MAT.plume, MAT.hot, MAT.glow]);
  const body = Object.values(MAT).filter(m => !FX.has(m));
  const fx = flames.length ? document.createElement('canvas') : null, fc = fx && fx.getContext('2d');
  if (fx) { fx.width = out.width; fx.height = px; }
  for (let i = 0; i < n; i++) {
    pose(holder, model, view, i / n);
    flames.forEach(f => { f.visible = false; }); R.render(SCENE, CAM); ctx.drawImage(R.domElement, i * px, 0);
    if (fx) {
      flames.forEach(f => { f.visible = true; }); body.forEach(m => { m.colorWrite = false; });
      R.render(SCENE, CAM); fc.drawImage(R.domElement, i * px, 0);
      body.forEach(m => { m.colorWrite = true; });
    }
  }
  SCENE.remove(holder);
  const own = new Set(Object.values(MAT));
  holder.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material && !own.has(o.material)) o.material.dispose(); });
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
  if (fx) for (let i = 0; i < n; i++) {
    ctx.save(); ctx.beginPath(); ctx.rect(i * px, 0, px, px); ctx.clip();
    try { ctx.filter = `blur(${o * 1.6}px)`; } catch (e) { /* no canvas filters (older Safari): no glow */ }
    ctx.globalAlpha = 0.9; ctx.drawImage(fx, i * px, 0, px, px, i * px, 0, px, px);
    ctx.filter = 'none'; ctx.globalAlpha = 1; ctx.drawImage(fx, i * px, 0, px, px, i * px, 0, px, px);
    ctx.restore();
  }
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
