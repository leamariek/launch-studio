// Headless Chrome for GPU rendering, with a request guard. Serves a folder over local HTTP, logs every request, and
// records a violation for any picture: an image file by extension or content type, an image resource, a data:image
// URL, an <img> source, createImageBitmap from a Blob, or any request that leaves the local server.
// GPU: in WSL2 with an NVIDIA card, Chrome needs Mesa's d3d12 driver and ANGLE on GL to leave software rendering.
import { createRequire } from 'node:module';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);
export function playwright() {
  for (const id of [process.env.PW_CORE, 'playwright', 'playwright-core']) {
    if (!id) continue;
    try { return require(id); } catch {}
  }
  throw new Error('playwright not found: npm i -D playwright-core, or set PW_CORE to a playwright-core folder');
}

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.bin': 'application/octet-stream' };
const PICTURE = /\.(png|jpe?g|webp|gif|bmp|avif|svg|ico|tiff?|heic)(\?|#|$)/i;

export const GPU_ENV = { GALLIUM_DRIVER: 'd3d12', MESA_D3D12_DEFAULT_ADAPTER_NAME: 'NVIDIA' };
export const GPU_ARGS = ['--use-angle=gl', '--enable-gpu', '--ignore-gpu-blocklist', '--force-color-profile=srgb'];

function chromePath(given) {
  for (const p of [given, process.env.CHROME, '/opt/google/chrome/chrome', '/usr/bin/google-chrome']) if (p && fs.existsSync(p)) return p;
  return undefined;   // playwright's own browser
}

export async function openPage({ root, chrome, gpu = true, width = 1280, height = 720 }) {
  root = path.resolve(root);
  const requests = [], violations = [];
  const server = http.createServer((req, res) => {
    const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    requests.push(rel);
    if (PICTURE.test(rel)) { violations.push('picture file requested: ' + rel); res.writeHead(403); return res.end(); }
    const p = path.join(root, rel);
    if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    fs.createReadStream(p).pipe(res);
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const { chromium } = playwright();
  const browser = await chromium.launch({
    executablePath: chromePath(chrome),
    env: gpu ? { ...process.env, ...GPU_ENV } : process.env,
    args: gpu ? GPU_ARGS : ['--force-color-profile=srgb'],
  });
  const page = await browser.newPage({ viewport: { width, height } });
  await page.addInitScript(() => {
    // in-page picture paths that never reach the network
    const note = (what) => { (window.__pictureViolations ||= []).push(what); };
    const desc = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
    Object.defineProperty(HTMLImageElement.prototype, 'src', { set(v) { note('img src: ' + String(v).slice(0, 80)); return desc.set.call(this, v); }, get() { return desc.get.call(this); } });
    const cib = window.createImageBitmap;
    window.createImageBitmap = function (src, ...a) { if (src instanceof Blob || src instanceof HTMLImageElement) note('createImageBitmap'); return cib.call(this, src, ...a); };
  });
  await page.route('**/*', (route) => {
    const req = route.request(), url = req.url();
    if (url.startsWith('data:image')) { violations.push('data:image URL'); return route.abort(); }
    if (req.resourceType() === 'image' || PICTURE.test(url)) { violations.push('image request: ' + url.slice(0, 120)); return route.abort(); }
    if (!url.startsWith(origin) && !url.startsWith('data:')) { violations.push('external request: ' + url.slice(0, 120)); return route.abort(); }
    return route.continue();
  });
  page.on('console', m => { if (m.type() === 'error') console.error('[page]', m.text().slice(0, 1500)); });
  page.on('pageerror', e => console.error('[pageerror]', e.message));
  page.on('response', r => { const ct = r.headers()['content-type'] || ''; if (ct.startsWith('image/')) violations.push('image response: ' + r.url()); });
  const checkGuard = async () => {
    const inPage = await page.evaluate(() => window.__pictureViolations || []).catch(() => []);
    return violations.concat(inPage);
  };
  const close = async () => { await browser.close(); server.close(); };
  return { page, origin, requests, checkGuard, close };
}

export const isGPU = (renderer) => !/swiftshader|llvmpipe|software|lavapipe/i.test(renderer || '');
