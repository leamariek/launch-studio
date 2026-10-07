"""Fit a reference drawing into code-drawable data (drawing.json): pencil strokes, residual ink levels, paper, glaze,
wash regions and an alpha model. The output holds no pixels; engine/inkwash.js draws it.

usage: python fit.py reference.png out/drawing.json [options]
  --rounds 3 --iters 120     stroke optimizer rounds (each adds strokes for missing darkness) and Adam steps per round
  --line-lo 0.06             ridge threshold for line tracing (lower finds fainter lines)
  --wash-k 40 --wash-min 10  wash clusters and smallest region (px)
  --alpha auto|opaque|mask|straight|field   alpha model for a reference with an alpha channel
  --bg background.png        what a field layer lies over (needed for --alpha field)
  --hatch keep|regen         keep traced hatching as strokes (default) or regenerate it from a field
  --texture                  draw long parallel hatching as texture strokes (crisp core, tooth at the edges)
  --no-glaze --no-optimize --cpu-paper
Steps that render (paper loop, pressure calibration, wash fit) run engine/inkwash.js in headless Chrome
(tools/jobs.mjs), so the fit sees exactly what the renderer draws."""
import argparse, json, os, sys, time
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cupy as cp
from common import backend, read_rgb, asnp, r
from lines import fit_lines
from optimize import optimize
from raster import Pack, forward
from residual import fit_residual
from hatch import classify, hatch_field
from paper import fit_paper
from wash import fit_wash
from alpha import fit_alpha, fit_target, choose
from glrender import render, to_lin

L_W = np.array([0.2126, 0.7152, 0.0722], np.float32)


def order_strokes(strokes, start=(0.0, 0.0)):
    """Drawing order: long contours, then details, then hatching, then texture strokes; each group as a nearest-neighbor
    tour of the pencil (a stroke may be reversed so it starts where the pencil is)."""
    out = []
    pos = np.asarray(start, np.float64)
    groups = [lambda s: s.get('cls') not in (4, 5) and s['L'] >= 60, lambda s: s.get('cls') not in (4, 5) and s['L'] < 60,
              lambda s: s.get('cls') == 4, lambda s: s.get('cls') == 5]
    for gi, group in enumerate(groups):
        todo = [s for s in strokes if group(s)]
        if not todo:
            continue
        A = np.array([s['p'][0, :2] for s in todo], np.float64); B = np.array([s['p'][-1, :2] for s in todo], np.float64)
        left = np.ones(len(todo), bool)
        for _ in range(len(todo)):
            d0 = np.hypot(*(A - pos).T); d1 = np.hypot(*(B - pos).T)
            d = np.where(left, np.minimum(d0, d1), np.inf)
            i = int(np.argmin(d)); left[i] = False
            s = todo[i]
            if d1[i] < d0[i]:
                s['p'] = s['p'][::-1].copy()
            if gi < 2:
                s['cls'] = 1 if s['L'] >= 60 else 3
            out.append(s); pos = s['p'][-1, :2].astype(np.float64)
    return out


def pack_drawing(W, H, paper, strokes, residual, wash, alpha, hatch=None, look=None):
    return dict(format='hand-drawn/2', size=[W, H], paper=paper, look=look or {},
                strokes=[dict(c=int(s.get('cls', 1)), t=[r(v, 4) for v in s['col']], p=[r(v, 2) for v in np.asarray(s['p']).ravel()]) for s in strokes],
                residual=residual, wash=wash, alpha=alpha, hatch=hatch,
                note='fitted vector data; no image is loaded at render time')


def calibrate(drawing, strokes, Dt, workdir, rounds=2, log=print):
    """Closed-loop pressure: render the strokes through the real renderer, compare darkness along every stroke with the
    reference ink, rescale pressures (smoothed along the stroke)."""
    H, W = Dt.shape
    Dk = cv2.dilate(Dt.astype(np.float32), np.ones((3, 3), np.uint8))
    for it in range(rounds):
        d = dict(drawing, residual=dict(levels=[]), wash=dict(regions=[]),
                 strokes=[dict(c=int(s.get('cls', 1)), t=[r(v, 4) for v in s['col']], p=[r(v, 2) for v in s['p'].ravel()]) for s in strokes])
        ink = to_lin(render(d, [dict(debug='ink')], workdir)[0][..., :3])
        Dr = cv2.dilate((1 - ink @ L_W).astype(np.float32), np.ones((3, 3), np.uint8))
        errs = []
        for s in strokes:
            p = s['p']
            xi = np.clip(p[:, 0].astype(int), 0, W - 1); yi = np.clip(p[:, 1].astype(int), 0, H - 1)
            f = np.clip((Dk[yi, xi] + 0.02) / (Dr[yi, xi] + 0.02), 0.7, 1.5)
            if len(f) >= 3:
                f = np.convolve(np.pad(f, 1, mode='edge'), [0.25, 0.5, 0.25], 'valid')
            errs.append(np.abs(Dk[yi, xi] - Dr[yi, xi]).mean())
            p[:, 3] = np.clip(p[:, 3] * f, 0.01, 1.0)
        log(f'  calib round {it}: mean |reference - render| along strokes {np.mean(errs):.4f}')
    return strokes


LOOKS = {   # watercolor effects of the renderer, from full to none; the fit keeps the one that matches the reference best
    'full': dict(edge=0.15, gran=0.4, flow=0.06, back=0.05, wob=0.8, soft0=0.02, soft1=0.08),
    'calm': dict(edge=0.12, gran=0.3, flow=0.03, back=0.0, wob=0.6, soft0=-1.0, soft1=-0.5),
    'plain': dict(edge=0.0, gran=0.15, flow=0.0, back=0.0, wob=0.3, soft0=-1.0, soft1=-0.5),
}


def choose_look(drawing, ref_srgb, workdir, log=print):
    """Closed loop over the renderer's watercolor effects: render each candidate, keep the lowest CIEDE2000 at half size."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
    from metrics import ciede2000, lab
    H, W = ref_srgb.shape[:2]
    size = (W // 2, H // 2)
    rp = cv2.resize(ref_srgb, size, interpolation=cv2.INTER_AREA)
    names = list(LOOKS)
    outs = render(drawing, [dict(look=LOOKS[n]) for n in names], workdir)
    scores = {n: float(ciede2000(lab(rp), lab(cv2.resize(o[..., :3], size, interpolation=cv2.INTER_AREA))).mean()) for n, o in zip(names, outs)}
    best = min(scores, key=scores.get)
    log(f'  look: {", ".join(f"{n} {v:.3f}" for n, v in scores.items())} -> {best}')
    return dict(drawing['look'], **LOOKS[best], name=best)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('reference'); ap.add_argument('out')
    ap.add_argument('--rounds', type=int, default=3); ap.add_argument('--iters', type=int, default=120)
    ap.add_argument('--line-lo', type=float, default=0.06); ap.add_argument('--orient-lo', type=float, default=0.03)
    ap.add_argument('--wash-k', type=int, default=40); ap.add_argument('--wash-min', type=int, default=10)
    ap.add_argument('--alpha', default='auto'); ap.add_argument('--bg')
    ap.add_argument('--hatch', default='keep'); ap.add_argument('--texture', action='store_true')
    ap.add_argument('--no-glaze', action='store_true'); ap.add_argument('--no-optimize', action='store_true')
    ap.add_argument('--tooth', type=float, default=0.25)
    a = ap.parse_args()
    t0 = time.time()
    log = lambda *x: print(*x, flush=True)
    log(f'backend: {backend()}')
    work = os.path.join(os.path.dirname(os.path.abspath(a.out)), '_fit_work')
    rgb, alpha_ch = read_rgb(a.reference)
    H, W = rgb.shape[:2]
    mode = choose(alpha_ch) if a.alpha == 'auto' else a.alpha
    bg = read_rgb(a.bg)[0] if a.bg else None
    tgt = fit_target(rgb, alpha_ch, mode, bg)
    support = (alpha_ch > 0.1) if mode != 'opaque' else None

    strokes, T, Dt = fit_lines(tgt, support=support, line_lo=a.line_lo, orient_lo=a.orient_lo, log=log)
    if not a.no_optimize:
        strokes, _ = optimize(strokes, Dt, T, rounds=a.rounds, iters=a.iters, log=log)
    hidx = classify(strokes)
    for i in hidx:
        strokes[i]['cls'] = 5 if (a.texture and strokes[i]['L'] > 40) else 4
    hatch = None
    if a.hatch == 'regen':
        hatch = hatch_field([s for s in strokes if s.get('cls') == 4])
        strokes = [s for s in strokes if s.get('cls') != 4]
    log(f'  hatching: {len(hidx)} strokes {"kept as strokes" if a.hatch == "keep" else "regenerated from a field"}{", texture strokes on" if a.texture else ""}')
    strokes = order_strokes(strokes)
    log(f'lines done: {len(strokes)} strokes, {time.time() - t0:.0f} s')

    paper = fit_paper(tgt, Dt, work, log=log)
    look = dict(lineGain=1.0, tooth=a.tooth)
    base = pack_drawing(W, H, paper, strokes, dict(levels=[]), dict(regions=[]), dict(mode='opaque'), hatch, look)
    strokes = calibrate(base, strokes, Dt, work, log=log)
    base = pack_drawing(W, H, paper, strokes, dict(levels=[]), dict(regions=[]), dict(mode='opaque'), hatch, look)
    ink = to_lin(render(base, [dict(debug='ink')], work)[0][..., :3])
    Dm = 1 - ink @ L_W
    residual = fit_residual(Dt, np.clip(Dm, 0, 1), T, log=log)
    base['residual'] = residual
    pi = to_lin(render(base, [dict(debug='paperink')], work)[0][..., :3])
    wash = fit_wash(tgt, pi, K=a.wash_k, min_area=a.wash_min, glaze=not a.no_glaze, log=log)
    alpha = fit_alpha(alpha_ch, rgb, mode, log=log)
    look = choose_look(pack_drawing(W, H, paper, strokes, residual, wash, dict(mode='opaque'), hatch, look), tgt, work, log=log)
    out = pack_drawing(W, H, paper, strokes, residual, wash, alpha, hatch, look)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, 'w'), separators=(',', ':'))
    for f in os.listdir(work):
        os.remove(os.path.join(work, f))
    os.rmdir(work)
    log(f'wrote {a.out}: {len(strokes)} strokes ({sum(len(s["p"]) for s in strokes)} vertices), {len(residual["levels"])} residual levels, '
        f'{len(wash["regions"])} wash regions, alpha {alpha["mode"]}, {os.path.getsize(a.out) / 1e6:.1f} MB, {time.time() - t0:.0f} s')


if __name__ == '__main__':
    main()
