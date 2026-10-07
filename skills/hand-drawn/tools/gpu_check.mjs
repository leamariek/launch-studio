#!/usr/bin/env node
// GPU check: launches headless Chrome with the GPU flags and prints the WebGL2 renderer, then asks the fitter's Python
// which array backend it gets (CuPy on the GPU or NumPy on the CPU). Exit 0 when both are on the GPU, 1 otherwise.
//   node tools/gpu_check.mjs [--python /path/to/python] [--chrome PATH]
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { playwright, GPU_ENV, GPU_ARGS, isGPU } from './browser.mjs';
import fs from 'node:fs';

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const here = path.dirname(fileURLToPath(import.meta.url));

const { chromium } = playwright();
const exe = [opt('chrome'), process.env.CHROME, '/opt/google/chrome/chrome', '/usr/bin/google-chrome'].find(p => p && fs.existsSync(p));
const browser = await chromium.launch({ executablePath: exe, env: { ...process.env, ...GPU_ENV }, args: GPU_ARGS });
const page = await browser.newPage();
const renderer = await page.evaluate(() => {
  const gl = document.createElement('canvas').getContext('webgl2');
  if (!gl) return 'no WebGL2';
  const d = gl.getExtension('WEBGL_debug_renderer_info');
  return d ? gl.getParameter(d.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
});
await browser.close();
const webglOK = isGPU(renderer) && renderer !== 'no WebGL2';
console.log(`WebGL2 renderer: ${renderer} -> ${webglOK ? 'GPU' : 'SOFTWARE'}`);

let py = 'not checked', pyOK = false;
try {
  py = execFileSync(opt('python', process.env.PYTHON || 'python3'), ['-c', 'import sys; sys.path.insert(0, sys.argv[1]); import common; print(common.backend())', path.join(here, '..', 'fit')], { encoding: 'utf8' }).trim();
  pyOK = py.startsWith('cupy');
} catch (e) { py = 'python failed: ' + String(e.message).split('\n')[0]; }
console.log(`fitter backend: ${py} -> ${pyOK ? 'GPU' : 'CPU'}`);
process.exit(webglOK && pyOK ? 0 : 1);
