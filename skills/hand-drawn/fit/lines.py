"""Line art to pressure polylines. Splits a reference drawing into ink (dark marks) and the wash under it, finds line
centers with a ridge filter, thins them to a one-pixel skeleton, walks the skeleton into ordered polylines and
samples width (from the distance transform) and pressure (from the ink darkness) along each one.

Output: a list of strokes {p: [[x, y, width, pressure], ...], col: [r, g, b], L: length}. Colors are linear-light
ink transmittance at full pressure."""
import numpy as np
from common import xp, asnp, asxp, gauss, gauss_d, close, dilate_max, edt, hysteresis, skeletonize, srgb_to_lin, lum

NB8 = [(-1, 0), (0, 1), (1, 0), (0, -1), (-1, 1), (1, 1), (1, -1), (-1, -1)]   # 4-neighbors first


def split_ink(rgb_srgb, radius=4):
    """Ink transmittance T and darkness d over the local wash. The wash is the upper envelope (gray closing),
    so any mark thinner than 2 * radius counts as ink."""
    lin = srgb_to_lin(asxp(rgb_srgb))
    env = xp.stack([gauss(close(lin[..., c], radius), 1.5) for c in range(3)], -1)
    T = xp.clip(lin / xp.maximum(env, 1e-4), 0, 1)
    return env, T, 1 - lum(T)


def ridge(d, s):
    """Bright-line ridge strength of the darkness map at scale s (largest Hessian eigenvalue, scale normalized)."""
    dxx, dyy, dxy = gauss_d(d, s, 0, 2), gauss_d(d, s, 2, 0), gauss_d(d, s, 1, 1)
    lam = (dxx + dyy) / 2 - xp.sqrt(((dxx - dyy) / 2) ** 2 + dxy ** 2)
    return xp.maximum(-lam, 0) * s * s


def walk(skel):
    """One-pixel skeleton (NumPy bool) to polylines of (y, x). Paths run between end and junction pixels; loops are cut
    once."""
    H, W = skel.shape
    on = np.pad(skel, 1)
    ys, xs = np.nonzero(on)
    deg = np.zeros_like(on, np.int8)
    for dy, dx in NB8:
        deg += np.roll(np.roll(on, dy, 0), dx, 1)
    deg = deg * on
    used = set()
    paths = []

    def nbrs(p):
        y, x = p
        return [(y + dy, x + dx) for dy, dx in NB8 if on[y + dy, x + dx]]

    def go(a, b):
        path = [a, b]; used.add((a, b)); used.add((b, a))
        prev, cur = a, b
        while deg[cur] == 2:
            nxt = next((q for q in nbrs(cur) if q != prev and (cur, q) not in used), None)
            if nxt is None:
                break
            used.add((cur, nxt)); used.add((nxt, cur))
            path.append(nxt); prev, cur = cur, nxt
        return path

    nodes = [p for p in zip(ys.tolist(), xs.tolist()) if deg[p] != 2]
    for p in nodes:
        for q in nbrs(p):
            if (p, q) not in used:
                paths.append(go(p, q))
    for p in zip(ys.tolist(), xs.tolist()):              # closed loops have no nodes
        if deg[p] == 2 and not any((p, q) in used for q in nbrs(p)):
            deg[p] = 3                                     # cut the loop here
            q = nbrs(p)[0]
            paths.append(go(p, q))
    return [np.asarray(pth, np.float32) - 1 for pth in paths if len(pth) >= 2]


def join(paths, snap=4.0, max_turn=40):
    """Chain path ends that touch and continue nearly straight, so one pen movement stays one stroke."""
    paths = [p for p in paths if len(p) >= 2]

    def end(p, first, k=5):
        seg = p[:k + 1] if first else p[-k - 1:][::-1]
        v = seg[0] - seg[-1]; n = np.hypot(*v)
        return seg[0], (v / n if n else v)

    ends = [(i, f, *end(p, f)) for i, p in enumerate(paths) for f in (True, False)]
    grid = {}
    for k, e in enumerate(ends):
        grid.setdefault((int(e[2][0] // snap), int(e[2][1] // snap)), []).append(k)
    cands = []
    for a, (i, fi, pi, di) in enumerate(ends):
        gy, gx = int(pi[0] // snap), int(pi[1] // snap)
        for yy in (gy - 1, gy, gy + 1):
            for xx in (gx - 1, gx, gx + 1):
                for b in grid.get((yy, xx), []):
                    j, fj, pj, dj = ends[b]
                    if b <= a or i == j or np.hypot(*(pi - pj)) > snap:
                        continue
                    c = float(np.dot(di, dj))              # outward directions point at each other when straight
                    if c < -np.cos(np.radians(max_turn)):
                        cands.append((c, a, b))
    mate = {}
    for c, a, b in sorted(cands):                          # straightest continuations first, each end used once
        if a not in mate and b not in mate:
            mate[a] = b; mate[b] = a
    seen, out = set(), []

    def chain(k):                                          # k: index of the free end where the chain starts
        parts = []
        while True:
            i, first = ends[k][0], ends[k][1]
            seen.add(i)
            parts.append(paths[i] if first else paths[i][::-1])
            other = 2 * i + (1 if first else 0)            # the path's opposite end
            if other not in mate or ends[mate[other]][0] in seen:
                break
            k = mate[other]
        return np.concatenate([parts[0]] + [p[1:] for p in parts[1:]])

    for k in range(len(ends)):                             # open chains from their free ends
        if k not in mate and ends[k][0] not in seen:
            out.append(chain(k))
    for k in range(len(ends)):                             # what is left is closed loops
        if ends[k][0] not in seen:
            out.append(chain(k))
    return out


def resample(p, step=2.0):
    seg = np.hypot(*np.diff(p, axis=0).T); s = np.concatenate([[0], np.cumsum(seg)])
    n = max(2, int(s[-1] / step) + 1); u = np.linspace(0, s[-1], n)
    return np.stack([np.interp(u, s, p[:, k]) for k in range(p.shape[1])], 1), s[-1]


def smooth(p, n=2):
    q = p.copy()
    for _ in range(n):
        if len(q) >= 5:
            q[1:-1] = 0.25 * q[:-2] + 0.5 * q[1:-1] + 0.25 * q[2:]
    return q


def oriented(d, n=12, su=6.0, sv=1.0, r=18):
    """Response of elongated line filters (second derivative across, gaussian along) in n directions: finds faint
    hatching and keeps broken pencil lines connected. Returns (max response, best direction index)."""
    H, W = d.shape
    y, x = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32)
    P = r + 2
    dp = xp.pad(d, P, mode='reflect'); Hp, Wp = dp.shape
    F = xp.fft.rfft2(dp)
    best = arg = None
    for i in range(n):
        a = np.pi * i / n
        u = x * np.cos(a) + y * np.sin(a); v = -x * np.sin(a) + y * np.cos(a)
        k = (1 - v * v / sv ** 2) / sv ** 2 * np.exp(-v * v / (2 * sv * sv) - u * u / (2 * su * su))
        k -= k.mean(); k /= np.abs(k).sum()
        kp = np.zeros((Hp, Wp), np.float32); kp[:k.shape[0], :k.shape[1]] = k
        kp = np.roll(np.roll(kp, -r, 0), -r, 1)
        resp = xp.fft.irfft2(F * xp.fft.rfft2(xp.asarray(kp)), s=(Hp, Wp))[P:P + H, P:P + W]
        if best is None:
            best, arg = resp, xp.zeros((H, W), xp.int32)
        else:
            m = resp > best; best = xp.where(m, resp, best); arg = xp.where(m, i, arg)
    return best, arg


def fit_lines(rgb_srgb, support=None, line_lo=0.06, scales=(1.0, 1.6), min_len=5, ink_sat=0.5, orient_lo=0.025, log=print):
    """Traced strokes of a reference drawing. support: optional bool mask (NumPy) of where lines may be."""
    env, T, d = split_ink(rgb_srgb)
    # the paper's own grain valleys read as faint "ink" against the local envelope: measure that floor in the quietest
    # paper window and take it off, so strokes explain drawn marks, not the paper (the paper fit carries the grain)
    from paper import quiet_window
    dn = asnp(d); y0, y1, x0, x1 = quiet_window(np.asarray(rgb_srgb), dn)
    f = float(np.percentile(dn[y0:y1, x0:x1], 75))
    d = xp.clip((d - f) / (1 - f), 0, 1)
    T = xp.clip(1 - (1 - T) * (d / xp.maximum(asxp(dn), 1e-4))[..., None], 0, 1)
    log(f'  paper floor of the ink map: {f:.3f}')
    strokes = trace(d, T, support, line_lo, scales, min_len, ink_sat, orient_lo, log)
    return strokes, asnp(T), asnp(d)


def trace(d, T, support=None, line_lo=0.06, scales=(1.0, 1.6), min_len=5, ink_sat=0.5, orient_lo=0.025, log=print):
    """Strokes from a darkness map d (backend array) and ink transmittance T (for the ink color). Coordinates follow
    the GL convention (pixel centers at +0.5)."""
    d = asxp(d); T = asxp(T)
    R = xp.maximum(*[ridge(d, s) for s in scales])
    mask = hysteresis(R, line_lo, line_lo * 1.7, 10)
    if orient_lo:
        O, _ = oriented(d)
        mask |= hysteresis(O, orient_lo, orient_lo * 1.6, 16) & (R > line_lo * 0.35)
    if support is not None:
        mask &= asxp(support)
    sk = asnp(skeletonize(mask))
    half = mask & (d > 0.45 * dilate_max(d, 5))           # ink at least half as dark as its local peak = the stroke body
    width = asnp(edt(half)) * 2.0
    dS = asnp(dilate_max(d, 3)); Tn = asnp(T)
    H, W = sk.shape
    strokes = []
    for pth in join(walk(sk)):
        if len(pth) < 3:
            continue
        q, L = resample(smooth(pth[:, ::-1].astype(np.float64)), 2.0)   # (x, y)
        if L < min_len:
            continue
        xi = np.clip(np.round(q[:, 0]).astype(int), 0, W - 1); yi = np.clip(np.round(q[:, 1]).astype(int), 0, H - 1)
        w = np.clip(np.convolve(np.pad(width[yi, xi], 1, mode="edge"), np.ones(3) / 3, "valid") + 0.3, 0.8, 3.6)
        pr = np.clip(dS[yi, xi], 0.02, 1.0)
        if L < 10 and pr.mean() < 0.15:
            continue
        col = np.median(Tn[yi, xi], 0)
        # full-strength ink color: the darkness d at pressure p should reproduce the measured transmittance
        dd = max(1e-3, float(pr.mean()))
        full = np.clip(1 - (1 - col) / dd, 0, 1)
        # graphite reads neutral: keep only a little of the measured hue (color at line edges is mostly the wash)
        fl = float(full @ np.array([0.2126, 0.7152, 0.0722]))
        full = fl + (full - fl) * ink_sat
        w = np.minimum(w, 1.4 * np.median(w))                # junction blobs do not widen the whole stroke
        strokes.append(dict(p=np.column_stack([q + 0.5, w, pr]).astype(np.float32), col=full, L=float(L)))
    log(f'  traced {len(strokes)} strokes, {sum(len(s["p"]) for s in strokes)} points')
    return strokes
