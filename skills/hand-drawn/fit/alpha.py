"""Alpha models for layers that move over other layers.

  opaque    no alpha.
  mask      a cut-out: silhouette rings (alpha >= 0.5) plus a fitted gaussian feather.
  straight  a soft layer whose alpha is its own field: silhouette at a floor alpha, plus regions (quantized alpha levels
            split into connected pieces) with a quadratic alpha surface each, plus a fitted feather. The color is fitted
            unpremultiplied, so the layer can move over anything.
  field     a soft layer that is pigment over a background (an unmixed sky wash, light): silhouette rings plus the
            layer's ink color; at render time the drawing is unmixed against the background texture along that color.
choose() picks mask, field or opaque from the alpha channel when the caller does not say."""
import numpy as np
import cv2
from residual import rings_of


def choose(a):
    if a.min() > 0.98:
        return 'opaque'
    part = float(((a > 0.02) & (a < 0.98)).mean())
    return 'field' if part > 0.3 else 'mask'


def _raster(rings, H, W, ss=4):
    m = np.zeros((H * ss, W * ss), np.uint8)
    for r in rings:
        t = np.zeros_like(m); cv2.fillPoly(t, [np.round(np.array(r, np.float32).reshape(-1, 2) * ss).astype(np.int32)], 1); m ^= t
    return cv2.resize(m.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)


def _feather(model, a, sigmas):
    best = (1e9, 0.0)
    for s in sigmas:
        m = cv2.GaussianBlur(model, (0, 0), s) if s > 0 else model
        e = float(((m - a) ** 2).mean())
        if e < best[0]:
            best = (e, s)
    return best[1]


def fit_alpha(a, rgb=None, mode=None, close=5, field_feather=0.8, levels=24, min_px=12, log=print):
    H, W = a.shape
    mode = mode or choose(a)
    if mode == 'opaque':
        return dict(mode='opaque')
    thr = 0.5 if mode == 'mask' else 0.02
    sil = (a >= thr).astype(np.uint8)
    if mode != 'mask' and close > 1:
        sil = cv2.morphologyEx(sil, cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
    rings = rings_of(sil, eps=0.3, min_area=1.5, ss=4)
    base = _raster(rings, H, W)
    rec = dict(mode=mode, rings=rings)
    if mode == 'mask':
        rec['feather'] = _feather(base, a, (0.0, 0.4, 0.6, 0.8, 1.0, 1.3, 1.7, 2.2))
        m = cv2.GaussianBlur(base, (0, 0), rec['feather']) if rec['feather'] else base
    elif mode == 'field':
        rec['feather'] = field_feather
        sel = a > 0.15
        rec['ink'] = [round(float(v), 4) for v in (np.median(rgb[sel], 0) if (rgb is not None and sel.any()) else [0.3, 0.33, 0.38])]
        m = cv2.GaussianBlur(base, (0, 0), field_feather)
    else:   # straight
        ab = cv2.GaussianBlur(a.astype(np.float32), (0, 0), 0.8)
        on = ab > 0.006
        qs = np.quantile(ab[on], np.linspace(0, 1, levels + 1)[1:-1]) if on.any() else np.array([])
        lab = np.where(on, np.digitize(ab, qs) + 1, 0).astype(np.int32)
        regions, model = [], np.zeros((H, W), np.float32)
        for j in range(1, levels + 1):
            n, cc, st, _ = cv2.connectedComponentsWithStats((lab == j).astype(np.uint8), 8)
            for i in range(1, n):
                if st[i, cv2.CC_STAT_AREA] < min_px:
                    continue
                py, px = np.nonzero(cc == i)
                x0, x1, y0, y1 = px.min(), px.max(), py.min(), py.max()
                cx, cy = (x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2; s = max(x1 - x0, y1 - y0, 8) / 2
                u = (px + 0.5 - cx) / s; v = (py + 0.5 - cy) / s; area = len(px)
                deg = 2 if area > 4000 else (1 if area > 300 else 0)
                M = np.stack([np.ones_like(u)] + ([u, v] if deg >= 1 else []) + ([u * u, u * v, v * v] if deg >= 2 else []), 1)
                coef = np.linalg.solve(M.T @ M + 1e-3 * np.eye(M.shape[1]), M.T @ a[py, px])
                model[py, px] = M @ coef
                k6 = np.zeros(6); k6[:M.shape[1]] = coef
                crop = cv2.dilate(np.pad((cc[y0:y1 + 1, x0:x1 + 1] == i).astype(np.uint8), 2), np.ones((3, 3), np.uint8))
                rr = [[round(float(q + (x0 - 2 if k % 2 == 0 else y0 - 2)), 2) for k, q in enumerate(r)] for r in rings_of(crop, eps=0.7, ss=1)]
                regions.append(dict(c=[round(float(cx), 1), round(float(cy), 1), round(float(s), 2)], p=[round(float(q), 5) for q in k6],
                                    bb=[int(x0), int(y0), int(x1) + 1, int(y1) + 1], rings=rr))
        floor = 0.03
        rec.update(floor=floor, regions=regions)
        ms = _raster(rings, H, W) >= 0.5
        model = np.where(ms, np.maximum(model, floor), 0)
        rec['feather'] = _feather(model, a, (0.0, 0.5, 0.8, 1.2, 1.6))
        m = cv2.GaussianBlur(model, (0, 0), rec['feather']) if rec['feather'] else model
    t2 = 0.5 if mode == 'mask' else 0.02
    rec['iou_fit'] = round(float(((m >= t2) & (a >= t2)).sum() / max(((m >= t2) | (a >= t2)).sum(), 1)), 4)
    if mode != 'field':   # a field layer's alpha comes from unmixing at render time, so only its outline is fitted here
        rec['alpha_mae'] = round(float(np.abs(np.clip(m, 0, 1) - a).mean()), 4)
    log(f'  alpha {mode}: {len(rings)} rings, feather {rec["feather"]}, IoU {rec["iou_fit"]}' + (f', MAE {rec["alpha_mae"]}' if 'alpha_mae' in rec else ''))
    return rec


def fit_target(rgb, a, mode, bg=None):
    """The color the drawing is fitted to. mask, straight: the layer's own color with edge colors extended outward
    (no seams); field: the layer seen over its background (bg, same size)."""
    if mode == 'field':
        if bg is None:
            raise ValueError('field layers need the background (--bg) to fit against')
        return rgb * a[..., None] + bg * (1 - a[..., None])
    if mode in ('mask', 'straight'):
        hole = (a < (0.25 if mode == 'mask' else 0.05)).astype(np.uint8)
        if hole.any() and not hole.all():
            _, lab = cv2.distanceTransformWithLabels(hole, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
            ys, xs = np.nonzero(hole == 0)
            src = np.zeros((lab.max() + 1, 3), np.float32); src[lab[ys, xs]] = rgb[ys, xs]
            out = rgb.copy(); out[hole > 0] = src[lab[hole > 0]]
            return out
    return rgb
