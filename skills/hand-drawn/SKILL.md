---
name: hand-drawn
description: Makes videos that look hand drawn (pencil, hatching and watercolor on toned paper) while every pixel of the render is drawn by code. Fits a reference drawing into vector strokes, ink levels, washes and paper on the GPU, then renders it with a WebGL2 engine that draws it on in stroke order and fails if any image is loaded. Use when a launch or occasion video should have an illustrated, drawn look and "made in code" is part of the claim.
---

# Hand-drawn look, drawn in code

Read `README.md` in this folder first. It covers the pipeline, the fitter, the renderer, the quality gate and the demo.

Quick start (needs an NVIDIA GPU with CuPy, Chrome, Node, ffmpeg and Playwright):

```bash
cd skills/hand-drawn
bash demo/run_demo.sh
```

The demo fits `demo/reference.jpg` (Schönbrunn Palace, Vienna) and renders `demo/renders/demo.mp4`, an 11 second draw-on where every pixel is drawn by code.

Use it inside the launch-film pipeline: the reference keyframes replace the rebuild kit as the source of truth, the six Gate C stills are rendered from the fitted drawing, and the gate numbers in the README are checked per scene before the full take is built.
