"""Hatching. By default hatching is traced like any line and kept as strokes (class 4), which reproduces the reference
most closely and draws on in the artist's order. Optionally (--hatch regen) short, straight, parallel strokes are
turned into a field per cell (angle, total and mean stroke length, pressure, ink color, width) from which the renderer
regenerates fresh hatching with a seeded random generator, for loose areas such as skies."""
import numpy as np


def _props(s):
    p = s['p'][:, :2]
    v = p[-1] - p[0]
    return float(np.hypot(*v)) / max(s['L'], 1e-3), float(np.arctan2(v[1], v[0])) % np.pi, p.mean(0)


def classify(strokes, min_len=6, max_len=120, straight=0.88, radius=24, min_mates=2, tol_deg=14):
    """Marks hatching (cls 4): short straight strokes with near-parallel neighbors. Returns the indices."""
    cand = []
    for i, s in enumerate(strokes):
        if min_len <= s['L'] <= max_len:
            st, ang, mid = _props(s)
            if st >= straight:
                cand.append((i, ang, mid))
    if not cand:
        return set()
    mids = np.array([c[2] for c in cand]); angs = np.array([c[1] for c in cand])
    cell = {}
    for k, m in enumerate(mids):
        cell.setdefault((int(m[0] // radius), int(m[1] // radius)), []).append(k)
    tol = np.radians(tol_deg); out = set()
    for k, (i, a, m) in enumerate(cand):
        cx, cy = int(m[0] // radius), int(m[1] // radius); mates = 0
        for yy in (cy - 1, cy, cy + 1):
            for xx in (cx - 1, cx, cx + 1):
                for j in cell.get((xx, yy), []):
                    if j != k and np.hypot(*(mids[j] - m)) < radius:
                        dd = abs(a - angs[j]) % np.pi
                        if min(dd, np.pi - dd) < tol:
                            mates += 1
        if mates >= min_mates:
            out.add(i)
    return out


def hatch_field(hatch, cell=16):
    """Sparse cell list: [cy, cx, angle, total_len, mean_len, pressure, r, g, b, width]."""
    acc = {}
    for s in hatch:
        st, ang, mid = _props(s)
        k = (int(mid[1] // cell), int(mid[0] // cell))
        a = acc.setdefault(k, dict(z=0j, L=0.0, n=0, pr=0.0, w=0.0, col=np.zeros(3)))
        a['z'] += s['L'] * np.exp(2j * ang); a['L'] += s['L']; a['n'] += 1
        a['pr'] += float(s['p'][:, 3].mean()) * s['L']; a['w'] += float(s['p'][:, 2].mean()) * s['L']; a['col'] += np.asarray(s['col']) * s['L']
    cells = []
    for (cy, cx), a in sorted(acc.items()):
        cells.append([cy, cx, round(float(np.angle(a['z']) / 2) % np.pi, 3), round(a['L'], 1), round(a['L'] / a['n'], 1),
                      round(a['pr'] / a['L'], 3), *[round(float(c), 3) for c in a['col'] / a['L']], round(a['w'] / a['L'], 2)])
    return dict(cell=cell, fields=['cy', 'cx', 'angle', 'total_len', 'mean_len', 'pressure', 'r', 'g', 'b', 'width'], cells=cells)
