"""Residual ink as nested level shapes. The ink the strokes cannot explain (dark fills, window panes, smudges, soft
graphite) is quantized into darkness levels. Each level is the region where the residual reaches it, traced as polygon
rings (holes included, even-odd), so the levels nest. Each level multiplies the ink by a flat transmittance, chosen so
the stack of levels a pixel sits in reproduces the residual at that level's midpoint."""
import numpy as np
import cv2
import cupy as cp
from cupyx.scipy import ndimage as cnd

LEVELS = (0.08, 0.13, 0.19, 0.26, 0.37, 0.5, 0.65, 0.8)


def rings_of(mask, eps=0.7, min_area=4.0, ss=2):
    """Even-odd polygon rings of a binary mask, traced at ss x supersampling, in GL pixel coordinates."""
    up = cv2.resize(np.pad(mask.astype(np.uint8), 1), None, fx=ss, fy=ss, interpolation=cv2.INTER_NEAREST)
    cnts, _ = cv2.findContours(up, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        c = cv2.approxPolyDP(c.astype(np.float32), eps * ss, True).reshape(-1, 2)
        c = (c + 0.5) / ss - 1.0
        if len(c) >= 3 and abs(cv2.contourArea(c.astype(np.float32))) >= min_area:
            out.append([round(float(v), 2) for v in c.ravel()])
    return out


def fit_residual(Dt, Dm, T, levels=LEVELS, sigma=1.0, min_px=14, log=print):
    """Dt: target ink darkness, Dm: darkness the strokes draw (both H x W). T: target ink transmittance (H, W, 3)."""
    Dt = cp.asarray(Dt); Dm = cp.asarray(Dm)
    r = cp.clip((Dt - Dm) / cp.maximum(1 - Dm, 1e-3), 0, 1)        # extra darkness on top of the strokes
    r = cnd.gaussian_filter(r, sigma)
    r_h = cp.asnumpy(r)
    Tn = np.asarray(T)
    # one ink color for the residual: the darkness-weighted mean hue of the target ink where the residual is strong
    sel = r_h > 0.2
    if sel.sum() > 20:
        tc = (1 - Tn[sel]).mean(0); tc = tc / max(tc.mean(), 1e-4)    # relative darkness per channel
    else:
        tc = np.ones(3)
    out, prev_T = [], 1.0
    for i, lv in enumerate(levels):
        m = r_h >= lv
        if m.sum() < min_px:
            break
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        keep = np.isin(lab, np.nonzero(st[:, cv2.CC_STAT_AREA] >= min_px)[0][1:])
        if not keep.any():
            break
        hi = levels[i + 1] if i + 1 < len(levels) else min(1.0, lv + 0.15)
        target = 1 - 0.5 * (lv + hi)                                   # cumulative transmittance in this band
        f = target / prev_T; prev_T = target                           # this level's own factor
        col = np.clip(1 - (1 - f) * tc, 0.02, 1.0)
        rings = rings_of(keep)
        out.append(dict(level=lv, t=[round(float(c), 4) for c in col], rings=rings))
    log(f'  residual: {len(out)} levels, {sum(len(l["rings"]) for l in out)} rings')
    return dict(levels=out)


def residual_model(res, H, W):
    """Transmittance (H, W) of the residual levels, for checks (the renderer draws them itself)."""
    Tm = np.ones((H, W, 3), np.float32)
    for l in res['levels']:
        m = np.zeros((H * 4, W * 4), np.uint8)
        for r in l['rings']:
            t = np.zeros_like(m); cv2.fillPoly(t, [np.round(np.array(r).reshape(-1, 2) * 4).astype(np.int32)], 1); m ^= t
        m = cv2.resize(m.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)
        Tm *= 1 - m[..., None] * (1 - np.asarray(l['t'], np.float32))
    return Tm
