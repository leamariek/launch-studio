"""Watercolor as procedural data: a glaze and wash regions, fitted inversely against what the renderer draws without
them (paper x ink, rendered by engine/inkwash.js), so the composite matches the reference.

1. Wash transmittance A = blur(reference) / blur(paper x ink), linear light.
2. Glaze: one pigment over a smooth strength field (gaussian RBFs on a grid). The pigment is the low-frequency color
   excess of the picture over its lightest areas; the field is that excess projected on the pigment.
3. Regions: A divided by the glaze is clustered in CIELAB (k-means), split into connected regions; small pieces join
   their neighbors. Each region gets a quadratic pigment transmittance per channel and polygon rings."""
import numpy as np
import cv2
import cupy as cp
from cupyx.scipy import ndimage as cnd
from common import to_lab, lin_to_srgb, srgb_to_lin


def _blur(x, s):
    return cp.stack([cnd.gaussian_filter(x[..., c], s) for c in range(x.shape[-1])], -1)


def fit_glaze(A, grid=(8, 6), strength_max=0.58, log=print):
    H, W = A.shape[:2]
    Ab = _blur(cp.clip(A, 0.05, 2.0), 25)
    L = -cp.log(Ab)                                                       # pigment density
    base = cp.stack([cp.percentile(L[..., c], 10) for c in range(3)])
    E = L - base
    mag = cp.linalg.norm(E, axis=-1)
    thr = float(cp.percentile(mag, 80))
    v = cp.asnumpy(E[mag >= thr].mean(0))
    if v.max() <= 1e-4:
        return dict(pigment=[1, 1, 1], base=0.0, sigma=200.0, centers=[]), cp.ones_like(A)
    v = np.clip(v, 0, None); v = v / np.linalg.norm(v)
    dens = v / v.max() * -np.log(1 - strength_max)                         # pigment at full strength
    P = np.exp(-dens)
    gfield = cp.clip((E @ cp.asarray(v, cp.float32)) / float(np.linalg.norm(dens)), 0, 1)
    gx, gy = grid
    cx = np.linspace(0, W, gx); cy = np.linspace(0, H, gy)
    sig = float(max(W / (gx - 1), H / (gy - 1)) * 0.8)
    ds = 8
    yy, xx = np.mgrid[0:H:ds, 0:W:ds]
    cen = [(x, y) for y in cy for x in cx]
    B = np.stack([np.ones(yy.size)] + [np.exp(-((xx - x) ** 2 + (yy - y) ** 2).ravel() / (2 * sig * sig)) for x, y in cen], 1)
    w = np.linalg.solve(B.T @ B + 1e-3 * np.eye(B.shape[1]), B.T @ cp.asnumpy(gfield[::ds, ::ds]).ravel())
    yy1, xx1 = np.mgrid[0:H, 0:W]
    g = np.full((H, W), w[0], np.float32)
    for (x, y), wi in zip(cen, w[1:]):
        g += wi * np.exp(-((xx1 - x) ** 2 + (yy1 - y) ** 2) / (2 * sig * sig)).astype(np.float32)
    g = np.clip(g, 0, 1)
    G = 1 - cp.asarray(g)[..., None] * (1 - cp.asarray(P, cp.float32))
    log(f'  glaze: pigment {np.round(P, 3)}, mean strength {g.mean():.3f}')
    return dict(pigment=[round(float(p), 4) for p in P], base=round(float(w[0]), 5), sigma=round(sig, 1),
                centers=[[round(float(x), 1), round(float(y), 1), round(float(wi), 5)] for (x, y), wi in zip(cen, w[1:])]), G


def fit_wash(ref_srgb, pi_lin, K=40, min_area=10, sigma=1.2, amax=1.6, glaze=True, log=print):
    """ref_srgb: reference (H, W, 3) sRGB. pi_lin: renderer's paper x ink without washes, linear (H, W, 3)."""
    H, W = ref_srgb.shape[:2]
    key = srgb_to_lin(cp.asarray(ref_srgb, cp.float32))
    A = _blur(key, sigma) / cp.maximum(_blur(cp.asarray(pi_lin, cp.float32), sigma), 1e-3)
    gz, G = fit_glaze(A, log=log) if glaze else (dict(pigment=[1, 1, 1], base=0.0, sigma=200.0, centers=[]), cp.ones_like(A))
    Ar = cp.clip(A / G, 0.05, amax)
    lab = to_lab(lin_to_srgb(cp.clip(_blur(Ar, 1.2), 0, amax) / amax))      # scaled so lifts above paper stay distinct
    X = lab.reshape(-1, 3)
    rng = np.random.default_rng(5)
    Kk = int(min(K, max(2, X.shape[0] // 400)))
    C = X[cp.asarray(rng.choice(X.shape[0], Kk, replace=False))]
    CH = 400000
    for _ in range(25):
        idx = cp.concatenate([((X[s:s + CH, None] - C[None]) ** 2).sum(-1).argmin(1) for s in range(0, X.shape[0], CH)])
        for j in range(Kk):
            sel = idx == j
            if int(sel.sum()):
                C[j] = X[sel].mean(0)
    Lb = idx.reshape(H, W).astype(cp.int32)
    oh = cp.stack([cnd.uniform_filter((Lb == j).astype(cp.float32), 7) for j in range(Kk)], 0)   # majority filter
    Lb = oh.argmax(0).astype(cp.int32); del oh
    comp = cp.zeros((H, W), cp.int32); n = 0
    for j in range(Kk):
        lj, nj = cnd.label(Lb == j, structure=cp.ones((3, 3)))
        comp = cp.where(lj > 0, lj + n, comp); n += int(nj)
    sz = cp.bincount(comp.ravel(), minlength=n + 1)
    small = (sz < min_area)[comp]
    if bool(small.any()) and not bool(small.all()):
        _, ix = cnd.distance_transform_edt(small, return_indices=True)
        comp = comp[ix[0], ix[1]]
    comp_h = cp.asnumpy(comp); A_h = cp.asnumpy(Ar).astype(np.float64)
    ids = np.unique(comp_h)
    order = np.argsort(comp_h.ravel(), kind='stable'); flat = comp_h.ravel()[order]
    regions = []
    for rid in ids:
        lo, hi = np.searchsorted(flat, rid), np.searchsorted(flat, rid, 'right')
        pix = order[lo:hi]; py, px = pix // W, pix % W; area = len(pix)
        x0, x1, y0, y1 = px.min(), px.max(), py.min(), py.max()
        cx, cy = (x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2; s = max(x1 - x0, y1 - y0, 8) / 2
        u = (px + 0.5 - cx) / s; v = (py + 0.5 - cy) / s
        deg = 2 if area > 1500 else (1 if area > 60 else 0)
        cols = [np.ones_like(u)] + ([u, v] if deg >= 1 else []) + ([u * u, u * v, v * v] if deg >= 2 else [])
        M = np.stack(cols, 1)
        sub = np.arange(area) if area <= 6000 else rng.choice(area, 6000, replace=False)
        Y = A_h[py[sub], px[sub]]
        coef = np.linalg.solve(M[sub].T @ M[sub] + 1e-2 * np.eye(M.shape[1]), M[sub].T @ Y)
        k6 = np.zeros((6, 3)); k6[:M.shape[1]] = coef
        crop = np.pad((comp_h[y0:y1 + 1, x0:x1 + 1] == rid).astype(np.uint8), 2)
        crop = cv2.dilate(crop, np.ones((3, 3), np.uint8))                 # 1 px overlap: no seams between regions
        cnts, _ = cv2.findContours(crop, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        rings = []
        for c in cnts:
            c = cv2.approxPolyDP(c.astype(np.float32), 0.9, True).reshape(-1, 2) + [x0 - 2 + 0.5, y0 - 2 + 0.5]
            if len(c) >= 3:
                rings.append([round(float(q), 1) for q in c.ravel()])
        if rings:
            regions.append(dict(c=[round(float(cx), 1), round(float(cy), 1), round(float(s), 2)],
                                k=[[round(float(q), 4) for q in row] for row in k6], bb=[int(x0), int(y0), int(x1) + 1, int(y1) + 1], rings=rings))
    log(f'  wash: {len(regions)} regions from {Kk} clusters')
    return dict(glaze=gz, regions=regions)
