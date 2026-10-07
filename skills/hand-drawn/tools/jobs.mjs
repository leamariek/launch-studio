#!/usr/bin/env node
// Runs fitting passes through the real renderer (tools/jobs.html in headless Chrome on the GPU, picture guard on).
//   node tools/jobs.mjs --root DIR --jobs jobs.json
//   jobs: [{ data: "path/drawing.json" (relative to root), out: "/abs/file.rgba", debug?, look?, t?, override? }]
// Each output is raw RGBA8, image row 0 first, with a sidecar .json { w, h }. Exit 2 on a picture fetch, 3 on software GL.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { openPage, isGPU } from './browser.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) { const n = arr[i + 1]; acc.push([a.slice(2), n && !n.startsWith('--') ? n : true]); }
  return acc;
}, []));
const root = path.resolve(args.root || '.');
const here = path.dirname(fileURLToPath(import.meta.url));
const page = path.relative(root, path.join(here, 'jobs.html')).split(path.sep).join('/');
const jobs = JSON.parse(fs.readFileSync(args.jobs, 'utf8'));
const S = await openPage({ root, chrome: args.chrome });
await S.page.goto(`${S.origin}/${page}`);
await S.page.waitForFunction(() => window.ready, null, { timeout: 60000 });
const renderer = await S.page.evaluate(() => window.renderer);
if (!isGPU(renderer) && !args['allow-cpu']) { console.error('FATAL: software renderer', renderer); await S.close(); process.exit(3); }
for (const j of jobs) {
  const t0 = Date.now();
  const r = await S.page.evaluate((job) => window.runJob(job), { ...j, data: '/' + j.data, bgData: j.bgData ? '/' + j.bgData : undefined });
  const buf = Buffer.from(r.b64, 'base64'), row = r.w * 4, flip = Buffer.alloc(buf.length);
  for (let y = 0; y < r.h; y++) buf.copy(flip, (r.h - 1 - y) * row, y * row, (y + 1) * row);
  fs.writeFileSync(j.out, flip);
  fs.writeFileSync(j.out.replace(/\.rgba$/, '.json'), JSON.stringify({ w: r.w, h: r.h, stats: r.stats }));
  console.error(`job ${path.basename(j.out)} ${j.debug || 'final'} ${r.w}x${r.h} ${Date.now() - t0} ms`);
}
const v = await S.checkGuard();
await S.close();
if (v.length) { console.error('FATAL: picture guard:', v.join('; ')); process.exit(2); }
