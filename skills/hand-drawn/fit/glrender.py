"""Link from the fitters to the real renderer: writes a drawing, runs passes through tools/jobs.mjs (engine/inkwash.js in
headless Chrome on the GPU) and reads the pixels back. The closed loops (paper grain, pressure, washes) use it, so they
fit what the renderer actually draws, not a Python approximation of it."""
import json, os, subprocess, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', 'tools')


def render(drawing, jobs, workdir, allow_cpu=False):
    """drawing: dict (written to workdir/_job_drawing.json). jobs: list of {debug?, look?, t?, override?}.
    Returns a list of sRGB float32 arrays (H, W, 4), image row 0 first."""
    os.makedirs(workdir, exist_ok=True)
    dpath = os.path.abspath(os.path.join(workdir, '_job_drawing.json'))
    json.dump(drawing, open(dpath, 'w'), separators=(',', ':'))
    root = os.path.commonpath([os.path.abspath(os.path.join(HERE, '..')), dpath])
    spec, outs = [], []
    for i, j in enumerate(jobs):
        out = os.path.abspath(os.path.join(workdir, f'_job_{i}.rgba'))
        spec.append(dict(j, data=os.path.relpath(dpath, root).replace(os.sep, '/'), out=out)); outs.append(out)
    jf = os.path.join(workdir, '_jobs.json'); json.dump(spec, open(jf, 'w'))
    cmd = ['node', os.path.join(TOOLS, 'jobs.mjs'), '--root', root, '--jobs', jf] + (['--allow-cpu'] if allow_cpu else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('render jobs failed:\n' + r.stderr[-3000:])
    res = []
    for o in outs:
        m = json.load(open(o.replace('.rgba', '.json')))
        res.append(np.fromfile(o, np.uint8).reshape(m['h'], m['w'], 4).astype(np.float32) / 255.0)
        os.remove(o); os.remove(o.replace('.rgba', '.json'))
    return res


def to_lin(srgb):
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
