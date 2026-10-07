"""Stroke optimizer on the GPU. Moves every stroke vertex, and fits its width and pressure, so the rendered pencil
darkness (raster.py, the renderer's stroke model) matches the reference ink darkness pixel for pixel. Between rounds it
traces the darkness that is still missing into new strokes and drops strokes that add nothing.

Loss per pixel: (D - Dt)^2 + blur_w * (blur(D) - blur(Dt))^2 (the blurred term pulls strokes from a distance), plus a
smoothness term on vertex positions so strokes stay pencil lines, not zigzags. Adam steps with separate rates for
position, width and pressure."""
import numpy as np
import cupy as cp
from cupyx.scipy import ndimage as cnd
from raster import Pack, forward, backward
from lines import trace


def _adam(n):
    return dict(m=cp.zeros((n, 4), cp.float32), v=cp.zeros((n, 4), cp.float32), t=0)


def optimize(strokes, Dt, T, rounds=3, iters=120, lr=(0.12, 0.04, 0.02), blur_s=2.0, blur_w=4.0, smooth_w=0.02,
             wmin=0.7, wmax=3.6, resid_lo=0.07, log=print):
    Dt = cp.asarray(Dt, cp.float32); H, W = Dt.shape
    Bt = cnd.gaussian_filter(Dt, blur_s)
    lrv = cp.asarray([lr[0], lr[0], lr[1], lr[2]], cp.float32)
    for rd in range(rounds):
        P = Pack(strokes)
        n = int(P.V.shape[0]); A = _adam(n)
        hasp, hasn = P.prev >= 0, P.next >= 0
        pi, ni = cp.where(hasp, P.prev, 0), cp.where(hasn, P.next, 0)
        for it in range(iters):
            D, best = forward(P, H, W)
            E = D - Dt
            G = 2 * E + blur_w * cnd.gaussian_filter(2 * (cnd.gaussian_filter(D, blur_s) - Bt), blur_s)
            g = backward(P, H, W, best, G)
            # smoothness: pull interior vertices toward the midpoint of their neighbors
            xy = P.V[:, :2]
            mid = 0.5 * (xy[pi] + xy[ni])
            inner = (hasp & hasn)[:, None]
            g[:, :2] += smooth_w * 2 * cp.where(inner, xy - mid, 0)
            A['t'] += 1
            A['m'] = 0.9 * A['m'] + 0.1 * g
            A['v'] = 0.999 * A['v'] + 0.001 * g * g
            mh = A['m'] / (1 - 0.9 ** A['t']); vh = A['v'] / (1 - 0.999 ** A['t'])
            P.V -= lrv * mh / (cp.sqrt(vh) + 1e-8)
            P.V[:, 2] = cp.clip(P.V[:, 2], wmin, wmax); P.V[:, 3] = cp.clip(P.V[:, 3], 0.0, 1.0)
            P.V[:, 0] = cp.clip(P.V[:, 0], 0, W); P.V[:, 1] = cp.clip(P.V[:, 1], 0, H)
            if it == 0 or it == iters - 1:
                log(f'  optimize round {rd} iter {it}: mean |ink error| {float(cp.abs(E).mean()):.4f}, {len(strokes)} strokes')
        strokes = P.strokes(strokes)
        # prune strokes that are almost invisible
        strokes = [s for s in strokes if float(np.mean(s['p'][:, 3])) * (1 - float(np.mean(s['col']))) > 0.03]
        if rd < rounds - 1:
            D, _ = forward(Pack(strokes), H, W)
            resid = cp.clip(Dt - D, 0, 1)
            Tres = cp.clip(1 - (1 - cp.asarray(T)) * (resid / cp.maximum(Dt, 1e-3))[..., None], 0, 1)
            new = trace(resid, Tres, line_lo=resid_lo, min_len=4, orient_lo=0, log=lambda *a: None)
            for s in new:
                s['cls'] = 3
            strokes += new
            log(f'  optimize round {rd}: +{len(new)} strokes from the missing darkness')
    D, _ = forward(Pack(strokes), H, W)
    log(f'  optimize done: {len(strokes)} strokes, {sum(len(s["p"]) for s in strokes)} vertices, mean |ink error| {float(cp.abs(D - Dt).mean()):.4f}')
    return strokes, D
