#!/usr/bin/env bash
# The whole demo: fit demo/reference.jpg -> GPU render with the picture guard -> gate metrics and review sheet.
# usage: demo/run_demo.sh            (from the hand-drawn folder)
# env:   PYTHON  python with CuPy for the fitter (default python3)
#        PW_CORE path to a playwright-core install if it is not resolvable from here
#        RENDER_FLAGS extra flags for tools/render.mjs, e.g. --allow-cpu on a machine without a working GPU
# A new reference image is prepared once with: python3 tools/prep_reference.py source.png demo/reference.jpg
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
mkdir -p demo/build demo/renders

"$PY" fit/fit.py demo/reference.jpg demo/build/drawing.json

# gate still: the finished drawing without the pencil on top
node tools/render.mjs --root . --page demo/index.html --query pencil=0 --stills 11 --stills-dir demo/renders --prefix gate ${RENDER_FLAGS:-}
# the video and two stills with the pencil
node tools/render.mjs --root . --page demo/index.html --out demo/renders/demo.mp4 --stills 4,11 ${RENDER_FLAGS:-}

python3 tools/metrics.py demo/reference.jpg demo/renders/gate_11.00.png --json demo/renders/metrics.json || echo "gate: FAIL (see demo/renders/metrics.json)"
python3 tools/side.py demo/reference.jpg demo/renders/gate_11.00.png demo/renders/side.jpg --metrics demo/renders/metrics.json --crop 320x200
