# Hand-drawn look, drawn in code

A module for videos that look hand drawn (pencil, hatching and watercolor on toned paper) while every pixel of the final render is drawn by code. A reference drawing is fitted once into vector data: pencil strokes with width and pressure, residual ink as nested level shapes, a glaze, watercolor wash regions, paper grain and an alpha model. At render time a WebGL2 engine draws that data on the GPU, including the draw-on in the fitted stroke order. No image is loaded at render time, and the renderer fails if one is.

## When to use it

- The brief wants a drawn, illustrated world rather than rebuilt product UI.
- "Made in code" is part of the claim, so the final must not contain reference pixels.

## What is in the folder

| Path | What it does |
| --- | --- |
| `engine/inkwash.js` | WebGL2 renderer. Paper with fitted grain, fibers, flecks and color mottling; a glaze; wash regions with edge darkening, granulation, flow, backruns and soft joins; pencil strokes (width, pressure, graphite tooth, MIN-blended so crossings do not double up) drawn on in fitted order; texture strokes; residual ink levels; hatching regenerated from a field when the drawing has one; alpha as `mask`, `straight` or `field`. `draw(t)` is a pure function of time. `tip(t)` says where the pencil is. Debug passes (`ink`, `wash`, `paper`, `paperink`, `glaze`) serve the fitter. |
| `engine/pencil.js` | An on-screen pencil in flat-shaded polygons with a soft shadow. It follows `tip(t)` and lifts between strokes. |
| `fit/fit.py` | Fits a reference image into `drawing.json`. Runs the steps below in order. |
| `fit/lines.py` | Ink and wash split, paper floor, ridge and oriented line filters, hysteresis, thinning, skeleton walk, joining of stroke ends, width and pressure sampling. |
| `fit/raster.py` | CUDA rasterizer of the renderer's stroke model with analytic gradients (CuPy RawModule). |
| `fit/optimize.py` | Stroke optimizer: Adam on every vertex's position, width and pressure against the reference ink, with a blurred term and a smoothness term; between rounds it traces the missing darkness into new strokes. |
| `fit/residual.py` | Residual ink the strokes cannot explain, as nested even-odd level shapes with a flat transmittance each. |
| `fit/hatch.py` | Marks hatching (short, straight, parallel strokes). Keeps it as strokes by default, or turns it into a field for regenerated hatching. |
| `fit/paper.py` | Paper tone, tint, seven grain octaves, mottling, flecks and fibers, closed through the real renderer. |
| `fit/wash.py` | Glaze (one pigment over a smooth field) and wash regions (CIELAB clusters, connected regions, a quadratic pigment per region), fitted against the renderer's own paper and ink. |
| `fit/alpha.py` | Alpha models: `mask` (cut-out), `straight` (soft alpha as quadratic regions), `field` (pigment unmixed against a background). |
| `fit/glrender.py` | Runs fitting passes through the real renderer (`tools/jobs.mjs`) and reads the pixels back. |
| `fit/common.py` | Array backend, filters, thinning, color conversion, image I/O. |
| `tools/render.mjs` | Renders any page that implements `window.__film` to MP4 and stills in headless Chrome on the GPU. Exit 2 if any picture is fetched or decoded, exit 3 if WebGL is on a software renderer. Writes a request log next to the video. |
| `tools/jobs.mjs`, `tools/jobs.html` | The fitter's render passes in headless Chrome, with the same picture guard. |
| `tools/browser.mjs` | Local server, Chrome launch with the GPU flags, and the picture guard. |
| `tools/gpu_check.mjs` | Prints the WebGL2 renderer and the fitter's backend. Exit 0 when both are on the GPU. |
| `tools/metrics.py` | Gate numbers for a render against its reference (see below). |
| `tools/side.py` | Side-by-side review sheet with 2x crops and the gate numbers. |
| `demo/` | An 11 second scene: the pencil draws the structure of a palace, the hatching builds up, the charcoal shading is laid in, then the muted washes bloom from the center and a warm glaze follows. The fit runs on `demo/reference.jpg`. Schönbrunn Palace, Vienna. Reference image generated with an image model; every pixel of the video is drawn by code. |
| `tools/prep_reference.py` | Center-crops a reference to 16:9, scales it to 1920 x 1080 and saves a high-quality JPEG of about 1 MB. |

## Requirements

- An NVIDIA GPU with CuPy (`pip install cupy-cuda12x` or the build matching your CUDA). The fitter's rasterizer, optimizer, residual, paper and wash steps run on the GPU.
- Python 3 with NumPy and OpenCV (`pip install numpy opencv-python`).
- Node.js 18 or later, Playwright (`npm i -D playwright-core`, or set `PW_CORE` to a playwright-core folder) and Google Chrome (`/opt/google/chrome/chrome`, `/usr/bin/google-chrome`, or `CHROME=/path`).
- ffmpeg. `h264_nvenc` is used when available, else `libx264`.

What runs on the CPU:

- `tools/metrics.py`, `tools/side.py` and `tools/prep_reference.py`.
- Rendering on a software WebGL renderer works with `--allow-cpu` on `render.mjs` and `jobs.mjs`, but slowly. It is meant for checks, not for final videos.
- The fitter does not run without CuPy in this version.

## Run the demo

From this folder:

```bash
node tools/gpu_check.mjs --python /path/to/python-with-cupy     # optional: confirms both GPU paths
PYTHON=/path/to/python-with-cupy demo/run_demo.sh
```

Step by step, the script runs:

```bash
$PYTHON fit/fit.py demo/reference.jpg demo/build/drawing.json
node tools/render.mjs --root . --page demo/index.html --query pencil=0 --stills 11 --stills-dir demo/renders --prefix gate
node tools/render.mjs --root . --page demo/index.html --out demo/renders/demo.mp4 --stills 4,11
python3 tools/metrics.py demo/reference.jpg demo/renders/gate_11.00.png --json demo/renders/metrics.json
python3 tools/side.py demo/reference.jpg demo/renders/gate_11.00.png demo/renders/side.jpg --metrics demo/renders/metrics.json --crop 320x200
```

Outputs: `demo/renders/demo.mp4`, stills `demo_4.00.png` (mid-drawing) and `demo_11.00.png`, the gate still `gate_11.00.png` (no pencil on top), `metrics.json`, `side.jpg` and `demo.requests.json` (every request the page made). On an RTX laptop GPU the fit takes about 7 minutes (about 19,500 strokes) and the 331-frame render about 130 s. `demo/reference.jpg`, `demo.mp4` and `demo_11.00.png` are meant to be committed; the rest of `demo/renders/` and all of `demo/build/` are regenerated by the script. To use another reference, prepare it with `python3 tools/prep_reference.py source.png demo/reference.jpg`.

## Fitting your own reference

```bash
python fit/fit.py reference.png out/drawing.json [options]
```

| Option | Default | Effect |
| --- | --- | --- |
| `--rounds`, `--iters` | 3, 120 | optimizer rounds (each adds strokes for missing darkness) and Adam steps per round |
| `--line-lo`, `--orient-lo` | 0.06, 0.03 | thresholds of the ridge and oriented line filters (lower finds fainter lines) |
| `--wash-k`, `--wash-min` | 40, 10 | wash clusters and the smallest region in px |
| `--alpha` | auto | `opaque`, `mask`, `straight` or `field` for a reference with an alpha channel |
| `--bg` | | the background a `field` layer lies over (a reference image of it) |
| `--hatch` | keep | `regen` turns hatching into a field and the renderer draws fresh hatching from it |
| `--texture` | off | long parallel hatching becomes texture strokes (crisp core, tooth at the edges) |
| `--no-glaze`, `--no-optimize`, `--tooth` | | switch off the glaze or the optimizer; graphite tooth strength (0.25) |

The fitter renders through the real engine three times: the paper loop, the pressure calibration and the wash fit. It also picks one of three watercolor effect settings (`full`, `calm`, `plain`) by rendering each and keeping the closest. Expect 1 to 4 minutes for a 1920 x 1088 reference.

## Pipeline for a real video

1. **Story and spine.** Pick one world the camera never leaves (for example a sketchbook on a desk) and one recurring actor that performs every gesture (for example the pencil). Scenes grow out of that world instead of cutting between pictures.
2. **Reference keyframes.** One reference drawing per scene, with a locked look. Build factual geometry (buildings, maps, emblems, logos) from real proportions, data or the official vector source, so it is correct before it is drawn. Make sure you have the rights to every reference.
3. **Layer split.** Anything that moves gets its own reference layer with an alpha channel: `mask` for cut-outs, `straight` for soft layers that move over anything, `field` for pigment that lies on a background.
4. **Motion first.** Build the full take on the layered references, then audit the motion before any redraw.
5. **Redraw every layer in code.** Run `fit/fit.py` per layer and per plate, then draw each with `createInkWash`. Draw a layer into a texture by passing your own framebuffer as `target`.
6. **Gate per scene** before integration: side-by-side sheet plus the numbers below and a request log that shows no picture was loaded.
7. **Text drawn, never set.** Write lettering by hand or trace a lettering drawing with the same fitter; the draw-on then follows the traced strokes.
8. **Music in code** on the video's clock, with your usual audio tools.
9. **Final render on the GPU** with the picture guard on, then frame QA and a loudness check.

## Gate metrics

`tools/metrics.py reference.png render.png` reports, with the pass thresholds:

| Number | Threshold | Meaning |
| --- | --- | --- |
| Phone CIEDE2000 | at most 2.5 | mean color difference with both images at 480 px wide |
| Phone SSIM | at least 0.78 | structure of luminance at 480 px wide |
| Edge F1 | at least 0.85 | Canny edges at full size, matched within 2 px |
| Silhouette IoU | at least 0.95 | alpha at 0.5 when alpha images are given, else the area that is not plain paper |

Demo result on an RTX laptop GPU: phone CIEDE2000 1.50, phone SSIM 0.941, full-size CIEDE2000 3.53, full-size SSIM 0.728, edge F1 0.916, silhouette IoU 1.0, pass. On a dense 1920 x 1088 pencil and watercolor painting the fit reaches phone CIEDE2000 1.42, phone SSIM 0.924, full-size CIEDE2000 2.82, full-size SSIM 0.733 and edge F1 0.926.

## Data format (`drawing.json`)

```json
{ "format": "hand-drawn/2", "size": [1920, 1080],
  "paper": { "tone": [0.8, 0.7, 0.5], "tint": [1.1, 1.0, 0.9], "amps": [7 octave amplitudes], "chroma": 0.5, "fleck": 0.02, "fiber": 0.004 },
  "look": { "lineGain": 1.0, "tooth": 0.25, "edge": 0.12, "gran": 0.3, "flow": 0.03, "back": 0.0, "wob": 0.6, "soft0": -1, "soft1": -0.5 },
  "strokes": [ { "c": 1, "t": [r, g, b], "p": [x, y, width, pressure, ...] } ],
  "residual": { "levels": [ { "level": 0.08, "t": [r, g, b], "rings": [[x, y, ...]] } ] },
  "wash": { "glaze": { "pigment": [r, g, b], "base": 0.1, "sigma": 260, "centers": [[x, y, weight]] },
            "regions": [ { "c": [cx, cy, scale], "k": [[6 x 3 coefficients]], "bb": [x0, y0, x1, y1], "rings": [[x, y, ...]] } ] },
  "alpha": { "mode": "opaque" },
  "hatch": null }
```

- Coordinates are drawing pixels with pixel centers at +0.5, y down. Colors are linear-light transmittance; a stroke's `t` is its ink at full pressure.
- Stroke classes: 1 long contour, 3 detail, 4 hatching, 5 texture stroke. Strokes are listed in drawing order.
- A wash region's transmittance is `k0 + k1 u + k2 v + k3 u^2 + k4 u v + k5 v^2` per channel, with `u = (x - cx) / scale` and `v = (y - cy) / scale`.
- Alpha: `mask` has `rings` and `feather`; `straight` adds `floor` and `regions` with a quadratic alpha `p`; `field` has `rings`, `feather` and the layer's ink color `ink`.

## Using the engine in your own page

```js
import { createInkWash } from './engine/inkwash.js';
import { createPencil } from './engine/pencil.js';
const D = await (await fetch('drawing.json')).json();
const gl = canvas.getContext('webgl2', { antialias: false, preserveDrawingBuffer: true, stencil: true });
const ink = createInkWash(gl, D, {
  // seconds: structure, then the traced hatching builds up, shading, washes, glaze
  timing: { lines: [0.5, 4.6], hatchStrokes: [4.0, 7.6], residual: [6.2, 8.4], wash: [7.9, 2.0], glaze: [8.8, 1.6], washSeed: [960, 600] },
  look: { vignette: 0 },   // optional darkening toward the corners; fitted washes already carry a reference's own
});
const pencil = createPencil(gl, D.size, { angle: -58, scale: 1.5 });
function frame(t) { ink.draw(t); pencil.draw(ink.tip(t)); }
```

- Field layers need the background drawn by code: `createInkWash(gl, layer, { bg: { tex, x, y, w, h } })`, where `tex` holds the background as this engine draws it (texel row 0 is the bottom row).
- For the render tools, expose `window.__film = { duration, fps, width, height, ready, seek(t), pixels() }` as `demo/index.html` does. `pixels()` returns the canvas as base64 RGBA from `gl.readPixels`, a plain buffer copy that avoids the browser's Blob quota on long renders.

## GPU setup notes (WSL2 with an NVIDIA card)

- Headless Chrome defaults to software rendering (SwiftShader or llvmpipe). `tools/browser.mjs` sets `GALLIUM_DRIVER=d3d12` and `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA` with the flags `--use-angle=gl --enable-gpu --ignore-gpu-blocklist`, and the tools stop unless the WebGL renderer string is a hardware one.
- On other systems (native Linux, Windows, macOS) the defaults usually reach the GPU already. Run `tools/gpu_check.mjs` to see.

## Limits of this version

- The fitter needs CuPy and an NVIDIA GPU; there is no CPU fallback for the optimizer and the wash fit.
- The stroke model in the optimizer leaves out the graphite tooth; the pressure calibration through the renderer absorbs its mean.
- Sky hatching that is very faint and long is traced as several shorter strokes, so it reads a little softer than in the reference.
- The paper grain matches the reference's band energies, not its exact pattern, so full-size SSIM stays well below phone-size SSIM.
- Wash regions are flat to quadratic pigment patches; very smooth gradients can show faint region edges at full size.
- Fine stipple and gravel texture is traced as short wiggly strokes, which read as worm-like marks at 2x. At full size it reads as texture.
- The engine draws one layer per call. Camera, parallax and layer motion are up to the host page (for example the frame-engine skill).
- The picture guard watches network requests, `<img>` sources and `createImageBitmap`. It cannot tell whether a JSON file smuggles pixel arrays, so keep the fitter as the only writer of data files.
