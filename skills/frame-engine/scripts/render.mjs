#!/usr/bin/env node
// Launch Studio frame renderer.
// Serves the launch/ directory over HTTP, drives window.__film.seek(t) in headless Chromium,
// pipes PNG frames into ffmpeg, optionally muxes audio. Run from the launch/ directory.
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

// Playwright: the project's own install, else PW_CORE (a playwright-core path).
const require = createRequire(import.meta.url);
const { chromium } = (() => {
  for (const id of ['playwright', process.env.PW_CORE]) {
    if (!id) continue;
    try { return require(id); } catch {}
  }
  throw new Error('playwright not found: npm i -D playwright, or set PW_CORE');
})();

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) {
    const next = arr[i + 1];
    acc.push([a.slice(2), next && !next.startsWith('--') ? next : true]);
  }
  return acc;
}, []));

const root = path.resolve(args.root || '.');
const entry = args.file || 'film/index.html';
const out = args.out || 'renders/draft.mp4';
const scale = parseFloat(args.scale || '1');
const blur = Math.max(1, parseInt(args.blur || '1', 10));
// --blurmap "8.2-9.4:12,15-15.6:12": subframe count per time range (film must expose window.__film.frame)
const blurmap = String(args.blurmap || '').split(',').filter(Boolean).map(s => { const [r, n] = s.split(':'); const [a, b] = r.split('-').map(Number); return { a, b, n: parseInt(n, 10) }; });
const subAt = t => (blurmap.find(m => t >= m.a && t < m.b) || { n: blur }).n;
const aspect = args.aspect || '16x9';
const codec = args.codec || 'h264';
const stills = args.stills ? String(args.stills).split(',').map(Number) : null;

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.otf': 'font/otf',
  '.wav': 'audio/wav', '.mp3': 'audio/mpeg' };

const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}/`;

const chrome = args.chrome || process.env.CHROME || (fs.existsSync('/usr/bin/google-chrome') ? '/usr/bin/google-chrome' : undefined);
const browser = await chromium.launch({ executablePath: chrome, args: ['--font-render-hinting=none', '--disable-lcd-text', '--force-color-profile=srgb'] });
const page = await browser.newPage();
page.on('console', m => { if (m.type() === 'error') console.error('[film]', m.text()); });
page.on('pageerror', e => { console.error('[film error]', e.message); });

// Probe dimensions first
await page.goto(`${base}${entry}?aspect=${aspect}`);
await page.waitForFunction(() => window.__film && window.__film.ready);
await page.evaluate(() => window.__film.ready);
const meta = await page.evaluate(() => ({ d: window.__film.duration, fps: window.__film.fps, w: window.__film.width, h: window.__film.height }));
const fps = parseFloat(args.fps || meta.fps || 60);
const W = Math.round(meta.w * scale), H = Math.round(meta.h * scale);
await page.setViewportSize({ width: meta.w, height: meta.h });
if (scale !== 1) await page.evaluate(s => { document.documentElement.style.zoom = s; }, scale);
await page.setViewportSize({ width: W, height: H });

const seek = t => page.evaluate(tt => window.__film.seek(tt), t);
const hasFrame = await page.evaluate(() => typeof window.__film.frame === 'function');
const frameAt = (t, n) => page.evaluate(([tt, nn]) => window.__film.frame(tt, nn), [t, n]);
const shot = () => page.screenshot({ type: 'png', animations: 'disabled', caret: 'hide' });

if (stills) {
  const dir = path.join(root, 'renders/stills');
  fs.mkdirSync(dir, { recursive: true });
  for (const t of stills) {
    if (hasFrame) await frameAt(t, subAt(t)); else await seek(t);
    fs.writeFileSync(path.join(dir, `still_${aspect}_${t.toFixed(2)}.png`), await shot());
    console.log(`still ${t}s`);
  }
  await browser.close(); server.close(); process.exit(0);
}

const from = parseFloat(args.from || '0');
const to = Math.min(parseFloat(args.to || meta.d), meta.d);
const frames = Math.round((to - from) * fps);
const inRate = hasFrame ? fps : fps * blur;

fs.mkdirSync(path.dirname(path.resolve(root, out)), { recursive: true });
const ff = ['-y', '-f', 'image2pipe', '-framerate', String(inRate), '-c:v', 'png', '-i', '-'];
if (args.audio) ff.push('-ss', String(from), '-t', String(to - from), '-i', path.resolve(root, args.audio));
const vf = !hasFrame && blur > 1 ? [`tmix=frames=${blur}`, `fps=${fps}`] : [];
if (vf.length) ff.push('-vf', vf.join(','));
if (codec === 'prores') ff.push('-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le');
else {
  // RGB frames -> YUV with the BT.709 matrix into TV range, and tag it, so players show the exact source colours.
  // (Untagged BT.601 output shifted colours; a later second range conversion made the X file 18 levels darker.)
  const conv = 'scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p';
  const i = ff.indexOf('-vf'); if (i >= 0) ff[i + 1] += ',' + conv; else ff.push('-vf', conv);
  ff.push('-c:v', 'libx264', '-preset', 'slow', '-crf', String(args.crf || 12), '-profile:v', 'high', '-tune', 'grain',
    '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv', '-movflags', '+faststart');
}
if (args.audio) ff.push('-c:a', codec === 'prores' ? 'pcm_s24le' : 'aac', '-b:a', '320k', '-shortest');
ff.push(path.resolve(root, out));

const enc = spawn('ffmpeg', ff, { stdio: ['pipe', 'inherit', 'pipe'] });
let ffErr = '';
enc.stderr.on('data', d => { ffErr += d; if (ffErr.length > 20000) ffErr = ffErr.slice(-10000); });

const started = Date.now();
for (let f = 0; f < frames; f++) {
  if (hasFrame) {
    // in-browser motion blur: the film averages its own subframes, one screenshot per output frame
    const t = from + f / fps;
    await frameAt(t, subAt(t));
    const buf = await shot();
    if (!enc.stdin.write(buf)) await new Promise(r => enc.stdin.once('drain', r));
  } else for (let s = 0; s < blur; s++) {
    // sub-frames span the interval before each frame time (360° shutter ending on the frame)
    const t = from + (f + (s + 1 - blur) / blur) / fps;
    await seek(Math.max(from, t));
    const buf = await shot();
    if (!enc.stdin.write(buf)) await new Promise(r => enc.stdin.once('drain', r));
  }
  if (f % Math.round(fps) === 0) {
    const el = (Date.now() - started) / 1000;
    process.stdout.write(`\rframe ${f}/${frames}  ${(f / Math.max(el, 0.001)).toFixed(1)} fps  eta ${(((frames - f) / Math.max(f, 1)) * el).toFixed(0)}s   `);
  }
}
enc.stdin.end();
const code = await new Promise(r => enc.on('close', r));
await browser.close(); server.close();
if (code !== 0) { console.error('\nffmpeg failed:\n' + ffErr); process.exit(code); }
console.log(`\nwrote ${out}  (${frames} frames @ ${fps} fps, ${W}x${H}, blur ${blur})`);
