// 1.58.47 — static/jar3d.webp: the donation jar (static/models3d.js, `BUILD.jar`) photographed once into a strip of
// frames, so the map's jar button plays it with CSS and never loads three.js for it.
//
//   node scripts/render_jar.js            (from the repository's root; needs Node and Playwright with a Chromium)
//
// It serves static/ on a free local port, has the browser build the strip (WebGL; a software one is fine), saves it as
// WebP and stops. Run it again after changing the jar.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.join(__dirname, '..');
const PX = 112;                      // a frame: the button shows it at 46 px, sharp up to a 2.4x screen
const TYPES = { '.js': 'text/javascript', '.html': 'text/html' };
const PAGE = `<!doctype html><meta charset="utf-8"><script type="module">
import * as M from '/static/models3d.js';
await M.init();
const s = await M.sheet('jar', 'jar', '#ffffff', ${PX}, 'rgba(8,11,16,0.9)');
const im = new Image(); im.src = s.url; await im.decode();
const c = document.createElement('canvas'); c.width = im.width; c.height = im.height; c.getContext('2d').drawImage(im, 0, 0);
const b = await new Promise(r => c.toBlob(r, 'image/webp', 0.82));
window.OUT = { n: s.n, dur: s.dur, data: await new Promise(r => { const f = new FileReader(); f.onload = () => r(f.result); f.readAsDataURL(b); }) };
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
    await p.waitForFunction(() => window.OUT, null, { timeout: 120000 });
    const o = await p.evaluate(() => window.OUT);
    const out = path.join(ROOT, 'static', 'jar3d.webp');
    fs.writeFileSync(out, Buffer.from(o.data.split(',')[1], 'base64'));
    console.log(`static/jar3d.webp: ${o.n} frames of ${PX} px, ${o.dur} s, ${fs.statSync(out).size} bytes`);
  } finally { await b.close(); srv.close(); }
});
