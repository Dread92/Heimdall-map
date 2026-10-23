// 1.58.55 — static/threats3d.webp: the threats of the guide's cards (static/guide.html, "What to do — threat cheat
// sheet") turning on themselves, photographed once from static/models3d.js, so the guide plays them with CSS and never
// loads three.js (it has to open on 2G, and with no network at all).
//
//   node scripts/render_models.js         (from the repository's root; needs Node and Playwright with a Chromium)
//
// One picture: a row a weapon (ROWS, in this order), each row the 'spin' view's frames side by side, PX pixels each.
// The guide reads the order, the frame count and the time from guide.html's M3G — change them together, then run this
// again. It serves static/ on a free local port, has the browser build the rows (WebGL; a software one is fine), saves
// them as WebP and stops.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.join(__dirname, '..');
const PX = 96;                       // a frame: the guide shows it at 42 px, sharp up to a 2.2x screen
// [model, colour, outline] — the colours of the guide's cards (and of the map's silhouettes); a ballistic missile white
// with its red edge, as everywhere
const ROWS = [['drone', '#ff8a3d'], ['jetdrone', '#ffb15c'], ['missile', '#ff5b52'], ['ballistic', '#ffffff', '#ff1744'],
  ['bomb', '#b07cff']];
const TYPES = { '.js': 'text/javascript', '.html': 'text/html' };
const PAGE = `<!doctype html><meta charset="utf-8"><script type="module">
import * as M from '/static/models3d.js';
await M.init();
const ROWS = ${JSON.stringify(ROWS)}, PX = ${PX};
const ims = [];
for (const [k, col, line] of ROWS) {
  const s = await M.sheet(k, 'spin', col, PX, line || 'rgba(8,11,16,0.9)');
  const im = new Image(); im.src = s.url; await im.decode(); ims.push([im, s]);
}
M.release();
const c = document.createElement('canvas'); c.width = ims[0][0].width; c.height = PX * ims.length;
const g = c.getContext('2d'); ims.forEach(([im], i) => g.drawImage(im, 0, i * PX));
const b = await new Promise(r => c.toBlob(r, 'image/webp', 0.7));
window.OUT = { n: ims[0][1].n, dur: ims[0][1].dur, w: c.width, h: c.height,
  data: await new Promise(r => { const f = new FileReader(); f.onload = () => r(f.result); f.readAsDataURL(b); }) };
</script>`;

const srv = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  if (u === '/') { res.writeHead(200, { 'Content-Type': 'text/html' }); return res.end(PAGE); }
  const f = path.normalize(path.join(ROOT, u));
  if (!f.startsWith(path.join(ROOT, 'static')) || !fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});

srv.listen(0, '127.0.0.1', async () => {
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--no-proxy-server'],
    executablePath: process.env.CHROMIUM || undefined });
  try {
    const p = await b.newPage();
    await p.goto(`http://127.0.0.1:${srv.address().port}/`);
    await p.waitForFunction(() => window.OUT, null, { timeout: 180000 });
    const o = await p.evaluate(() => window.OUT);
    const out = path.join(ROOT, 'static', 'threats3d.webp');
    fs.writeFileSync(out, Buffer.from(o.data.split(',')[1], 'base64'));
    console.log(`static/threats3d.webp: ${ROWS.map(r => r[0]).join(', ')} — ${o.n} frames of ${PX} px each, ${o.dur} s, ` +
      `${o.w}x${o.h}, ${fs.statSync(out).size} bytes`);
  } finally { await b.close(); srv.close(); }
});
