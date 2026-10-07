#!/usr/bin/env node
// Renders a page that implements window.__film ({ duration, fps, width, height, ready, seek(t), pixels() }) to MP4 and
// stills on the GPU, with the picture guard on: the render fails (exit 2) if the page fetches or decodes any image.
// It also fails (exit 3) when WebGL runs on a software renderer, unless --allow-cpu is given.
//
//   node tools/render.mjs --root . --page demo/index.html --out demo/renders/demo.mp4 --stills 1.5,4.5 [--query pencil=0]
//   options: --fps N (default: the page's), --from S --to S, --codec nvenc|x264, --chrome PATH, --allow-cpu
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { openPage, isGPU } from './browser.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) { const n = arr[i + 1]; acc.push([a.slice(2), n && !n.startsWith('--') ? n : true]); }
  return acc;
}, []));
const root = path.resolve(args.root || '.');
const pageRel = args.page || 'demo/index.html';
const out = args.out || null;
const stills = args.stills ? String(args.stills).split(',').map(Number) : [];
const stillsDir = args['stills-dir'] || (out ? path.dirname(out) : 'renders');
const prefix = args.prefix || (out ? path.basename(out, '.mp4') : 'still');

function encoders() {
  try { return execFileSync('ffmpeg', ['-hide_banner', '-encoders'], { encoding: 'utf8' }); } catch { return ''; }
}

const S = await openPage({ root, chrome: args.chrome, gpu: !args['no-gpu'] });
const fail = async (code, msg) => { console.error('FAIL:', msg); await S.close(); process.exit(code); };
await S.page.goto(`${S.origin}/${pageRel}${args.query ? '?' + args.query : ''}`);
await S.page.waitForFunction(() => window.__film && window.__film.ready, null, { timeout: 60000 });
await S.page.evaluate(() => window.__film.ready);
const meta = await S.page.evaluate(() => ({ d: __film.duration, fps: __film.fps, w: __film.width, h: __film.height, renderer: __film.renderer || '' }));
console.error('renderer:', meta.renderer);
if (!isGPU(meta.renderer)) {
  if (!args['allow-cpu']) await fail(3, 'WebGL is on a software renderer (' + meta.renderer + '). Fix the GPU setup or pass --allow-cpu.');
  console.error('warning: software rendering (--allow-cpu)');
}

const grab = async (t) => {
  await S.page.evaluate((t) => __film.seek(t), t);
  return Buffer.from(await S.page.evaluate(() => __film.pixels()), 'base64');
};
const vflipCmd = ['-vf', 'vflip'];
fs.mkdirSync(stillsDir, { recursive: true });
for (const t of stills) {
  const buf = await grab(t);
  const file = path.join(stillsDir, `${prefix}_${t.toFixed(2)}.png`);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${meta.w}x${meta.h}`, '-i', '-', ...vflipCmd, '-frames:v', '1', file], { input: buf });
  console.error('still', file);
}

if (out) {
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const fps = Number(args.fps || meta.fps);
  const from = Number(args.from || 0), to = Number(args.to || meta.d);
  const nv = (args.codec || 'nvenc') === 'nvenc' && /h264_nvenc/.test(encoders());
  const venc = nv ? ['-c:v', 'h264_nvenc', '-preset', 'p7', '-cq', '18', '-b:v', '0'] : ['-c:v', 'libx264', '-preset', 'slow', '-crf', '16'];
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${meta.w}x${meta.h}`, '-r', String(fps), '-i', '-',
    ...vflipCmd, ...venc, '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const n = Math.round((to - from) * fps);
  const t0 = Date.now();
  for (let i = 0; i <= n; i++) {
    const buf = await grab(from + i / fps);
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  console.error(`video ${out}: ${n + 1} frames at ${fps} fps, ${nv ? 'h264_nvenc' : 'libx264'}, ${((Date.now() - t0) / 1000).toFixed(1)} s`);
}

const v = await S.checkGuard();
const log = { renderer: meta.renderer, gpu: isGPU(meta.renderer), requests: [...new Set(S.requests)], picture_violations: v };
if (out) fs.writeFileSync(out.replace(/\.mp4$/, '') + '.requests.json', JSON.stringify(log, null, 1));
console.error('requests:', log.requests.join(', '));
if (v.length) {
  if (out && fs.existsSync(out)) fs.renameSync(out, out + '.FAILED');
  await fail(2, 'picture guard: ' + v.join('; '));
}
console.error('picture guard: clean (no image fetched or decoded)');
await S.close();
