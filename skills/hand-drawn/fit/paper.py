"""Paper as fitted procedural grain, closed through the real renderer. In the quietest window of the reference (no ink)
it measures tone, grain energy in seven octave bands, per-channel tint, color mottling, dark flecks and fiber
anisotropy. Then it renders the paper alone with engine/inkwash.js, measures the same statistics in the same window,
and rescales the parameters until the two agree."""
import numpy as np
import cv2
from glrender import render, to_lin

L_W = np.array([0.2126, 0.7152, 0.0722], np.float32)


def quiet_window(rgb, ink_d, h=200, w=320):
    g = cv2.cvtColor((np.clip(rgb, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    hp = np.abs(g - cv2.GaussianBlur(g, (0, 0), 3)) + 40 * (ink_d > 0.12) + 0.05 * np.abs(cv2.GaussianBlur(g, (0, 0), 20) - np.median(g))
    # paper is neutral to warm: a cool (blue) area is a wash such as sky, not bare paper
    b = cv2.cvtColor((np.clip(rgb, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2LAB)[..., 2].astype(np.float32)
    hp += 2.0 * np.clip(131 - cv2.GaussianBlur(b, (0, 0), 8), 0, None)
    sc = cv2.boxFilter(hp, -1, (w, h))
    H, W = g.shape
    sc[:h // 2 + 4] = 1e9; sc[-h // 2 - 4:] = 1e9; sc[:, :w // 2 + 4] = 1e9; sc[:, -w // 2 - 4:] = 1e9
    cy, cx = np.unravel_index(np.argmin(sc), sc.shape)
    return [int(cy - h // 2), int(cy + h // 2), int(cx - w // 2), int(cx + w // 2)]


def _lab(srgb):
    return cv2.cvtColor(np.clip(srgb, 0, 1).astype(np.float32), cv2.COLOR_RGB2LAB)


def stats(srgb, win):
    y0, y1, x0, x1 = win
    lin = to_lin(np.clip(srgb, 0, 1)).astype(np.float32)
    L = lin @ L_W
    res = (L / cv2.GaussianBlur(L, (0, 0), 40) - 1)[y0:y1, x0:x1]
    bands = []
    for k in range(7):
        a = cv2.GaussianBlur(res, (0, 0), 2.0 ** (k - 1)) if k else res
        bands.append(float((a - cv2.GaussianBlur(res, (0, 0), 2.0 ** k)).std()))
    rc = (lin / cv2.GaussianBlur(lin, (0, 0), 40) - 1)[y0:y1, x0:x1].reshape(-1, 3); rl = res.ravel()
    tint = [float((rc[:, c] * rl).sum() / max((rl * rl).sum(), 1e-12)) for c in range(3)]
    lab = _lab(srgb)
    ab = (lab[..., 1:] - cv2.GaussianBlur(lab[..., 1:], (0, 0), 20))[y0:y1, x0:x1]
    fine = res - cv2.GaussianBlur(res, (0, 0), 2.0)
    fleck = float((fine < -3.0 * fine.std()).mean())
    # fiber anisotropy: strongest over mean response of thin elongated line filters on the mid-band residual
    mid = (cv2.GaussianBlur(res, (0, 0), 0.8) - cv2.GaussianBlur(res, (0, 0), 6)).astype(np.float32)
    resp = []
    for a in np.linspace(0, np.pi, 8, endpoint=False):
        k = cv2.getGaborKernel((31, 31), 4.0, a, 6.0, 0.25, 0, ktype=cv2.CV_32F); k -= k.mean()
        resp.append(np.abs(cv2.filter2D(mid, -1, k)))
    resp = np.stack(resp)
    fiber = float(resp.max(0).mean() / max(resp.mean(), 1e-9))
    tone = np.median(lin[y0:y1, x0:x1].reshape(-1, 3), 0)
    return dict(bands=np.array(bands), tint=np.array(tint), chroma=float(ab.std()), fleck=fleck, fiber=fiber, tone=tone)


def fit_paper(ref_srgb, ink_d, workdir, window=None, rounds=5, log=print):
    H, W = ref_srgb.shape[:2]
    win = window or quiet_window(ref_srgb, ink_d)
    k = stats(ref_srgb, win)
    paper = dict(tone=[round(float(v), 5) for v in k['tone']], tint=[round(float(v), 4) for v in k['tint']],
                 amps=[round(float(b * 2.2), 5) for b in k['bands']], chroma=0.015, fleck=0.02, fiber=0.004, window=win)
    base = dict(format='hand-drawn/2', size=[W, H], strokes=[], wash=dict(regions=[]))
    for it in range(rounds):
        out = render(dict(base, paper=paper), [dict(debug='paper')], workdir)[0][..., :3]
        r = stats(out, win)
        amps = np.array(paper['amps']) * np.clip(k['bands'] / np.maximum(r['bands'], 1e-6), 0.3, 3.0) ** 0.85
        paper['amps'] = [round(float(a), 5) for a in amps]
        paper['chroma'] = round(float(np.clip(paper['chroma'] * (k['chroma'] / max(r['chroma'], 1e-6)) ** 0.85, 0, 0.2)), 4)
        paper['fleck'] = round(float(np.clip(paper['fleck'] * ((k['fleck'] + 1e-4) / (r['fleck'] + 1e-4)) ** 0.7, 0, 0.2)), 4)
        fr = (k['fiber'] - 1) / max(r['fiber'] - 1, 1e-3)
        paper['fiber'] = round(float(np.clip(paper['fiber'] * np.clip(fr, 0.5, 2.0) ** 0.7, 0, 0.05)), 5)
        paper['tone'] = [round(float(t * np.clip(a / max(b, 1e-6), 0.8, 1.25)), 5) for t, a, b in zip(paper['tone'], k['tone'], r['tone'])]
        log(f'  paper loop {it}: band error {np.abs(k["bands"] - r["bands"]).mean() / k["bands"].mean():.3f}, '
            f'chroma {r["chroma"]:.3f}/{k["chroma"]:.3f}, fleck {r["fleck"]:.4f}/{k["fleck"]:.4f}, fiber {r["fiber"]:.3f}/{k["fiber"]:.3f}')
    # the coarse octaves (16 px and up) are left to the washes, which are fitted against this paper: the paper keeps the
    # grain, the washes carry the reference's own mottling (otherwise the washes would have to undo random blotches)
    a = paper['amps']; paper['amps_fit'] = list(a)
    paper['amps'] = a[:4] + [round(a[4] * 0.5, 5), round(a[5] * 0.15, 5), round(a[6] * 0.1, 5)]
    return paper
