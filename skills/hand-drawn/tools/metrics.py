"""Gate metrics for a code render against its reference drawing.

usage: python metrics.py reference.png render.png [--json out.json] [--alpha-ref a.png --alpha-out b.png]

Numbers (defaults are the pass thresholds):
  phone_ciede2000  mean CIEDE2000 with both images scaled to 480 px wide           <= 2.5
  phone_ssim       SSIM of luminance at 480 px wide                                 >= 0.78
  edge_f1          F1 of Canny edges at full size, matched within 2 px              >= 0.85
  silhouette_iou   IoU of the drawn silhouettes (alpha >= 0.5 if alpha images are given, else the area that is
                   not plain paper, closed and hole-filled)                         >= 0.95
Runs on NumPy and OpenCV (CPU); fast enough for single frames."""
import argparse, json, sys
import numpy as np
import cv2

TH = dict(phone_ciede2000=2.5, phone_ssim=0.78, edge_f1=0.85, silhouette_iou=0.95)


def load(p):
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if im is None:
        sys.exit('cannot read ' + p)
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    return im[..., 2::-1].astype(np.float32) / 255


def lab(srgb):
    lin = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], np.float32)
    xyz = (lin @ M.T) / np.array([0.95047, 1.0, 1.08883], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def ciede2000(l1, l2):
    """CIEDE2000 color difference per pixel (Sharma, Wu and Dalal 2005)."""
    L1, a1, b1 = np.moveaxis(l1.astype(np.float64), -1, 0); L2, a2, b2 = np.moveaxis(l2.astype(np.float64), -1, 0)
    Cb = (np.hypot(a1, b1) + np.hypot(a2, b2)) / 2
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1, C2 = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1, h2 = np.degrees(np.arctan2(b1, a1p)) % 360, np.degrees(np.arctan2(b2, a2p)) % 360
    dL, dC = L2 - L1, C2 - C1
    dh = h2 - h1; dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)); dh = np.where(C1 * C2 == 0, 0, dh)
    dH = 2 * np.sqrt(C1 * C2) * np.sin(np.radians(dh / 2))
    Lm, Cm = (L1 + L2) / 2, (C1 + C2) / 2
    hs = h1 + h2
    hm = np.where(np.abs(h1 - h2) > 180, np.where(hs < 360, hs + 360, hs - 360) / 2, hs / 2); hm = np.where(C1 * C2 == 0, hs, hm)
    Tt = 1 - 0.17 * np.cos(np.radians(hm - 30)) + 0.24 * np.cos(np.radians(2 * hm)) + 0.32 * np.cos(np.radians(3 * hm + 6)) - 0.20 * np.cos(np.radians(4 * hm - 63))
    dth = 30 * np.exp(-((hm - 275) / 25) ** 2)
    Rc = 2 * np.sqrt(Cm ** 7 / (Cm ** 7 + 25.0 ** 7))
    Sl = 1 + 0.015 * (Lm - 50) ** 2 / np.sqrt(20 + (Lm - 50) ** 2); Sc = 1 + 0.045 * Cm; Sh = 1 + 0.015 * Cm * Tt
    Rt = -np.sin(np.radians(2 * dth)) * Rc
    return np.sqrt((dL / Sl) ** 2 + (dC / Sc) ** 2 + (dH / Sh) ** 2 + Rt * (dC / Sc) * (dH / Sh))


def ssim(a, b, s=1.5):
    C1, C2 = 0.01 ** 2, 0.03 ** 2
    g = lambda x: cv2.GaussianBlur(x, (0, 0), s)
    m1, m2 = g(a), g(b)
    s11, s22, s12 = g(a * a) - m1 ** 2, g(b * b) - m2 ** 2, g(a * b) - m1 * m2
    return float((((2 * m1 * m2 + C1) * (2 * s12 + C2)) / ((m1 ** 2 + m2 ** 2 + C1) * (s11 + s22 + C2))).mean())


def edges(img):
    g = cv2.GaussianBlur(cv2.cvtColor((np.clip(img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY), (0, 0), 1.0)
    return cv2.Canny(g, 40, 90) > 0


def edge_f1(er, eo, tol=2.0):
    dr = cv2.distanceTransform((~er).astype(np.uint8), cv2.DIST_L2, 3)
    do = cv2.distanceTransform((~eo).astype(np.uint8), cv2.DIST_L2, 3)
    p = float((dr[eo] <= tol).mean()) if eo.any() else 0.0
    r = float((do[er] <= tol).mean()) if er.any() else 0.0
    return p, r, 2 * p * r / max(p + r, 1e-9)


def silhouette(img, alpha=None):
    if alpha is not None:
        return alpha >= 0.5
    L = lab(cv2.GaussianBlur(img, (0, 0), 2.0))
    paper = np.median(L.reshape(-1, 3), 0)
    m = (np.linalg.norm(L - paper, axis=-1) > 6).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab_, st, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= 200:
            keep[lab_ == i] = 1
    ff = keep.copy(); h, w = ff.shape
    cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 2)
    return (keep == 1) | (ff == 0)


def measure(ref, out, alpha_ref=None, alpha_out=None):
    H, W = ref.shape[:2]
    out = cv2.resize(out, (W, H), interpolation=cv2.INTER_AREA) if out.shape[:2] != (H, W) else out
    ph = (480, round(480 * H / W))
    rp, op = cv2.resize(ref, ph, interpolation=cv2.INTER_AREA), cv2.resize(out, ph, interpolation=cv2.INTER_AREA)
    lum = lambda x: x @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    de_p = float(ciede2000(lab(rp), lab(op)).mean())
    ss_p = ssim(lum(rp), lum(op))
    p, r, f1 = edge_f1(edges(ref), edges(out))
    sr, so = silhouette(ref, alpha_ref), silhouette(out, alpha_out)
    iou = float((sr & so).sum() / max((sr | so).sum(), 1))
    res = dict(phone_480px=dict(ciede2000=round(de_p, 3), ssim=round(ss_p, 4)),
               full=dict(ciede2000=round(float(ciede2000(lab(ref), lab(out)).mean()), 3), ssim=round(ssim(lum(ref), lum(out)), 4),
                         edge_precision=round(p, 4), edge_recall=round(r, 4), edge_f1=round(f1, 4)),
               silhouette_iou=round(iou, 4), thresholds=TH)
    checks = dict(phone_ciede2000=de_p <= TH['phone_ciede2000'], phone_ssim=ss_p >= TH['phone_ssim'],
                  edge_f1=f1 >= TH['edge_f1'], silhouette_iou=iou >= TH['silhouette_iou'])
    res['checks'] = checks; res['pass'] = all(checks.values())
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('reference'); ap.add_argument('render'); ap.add_argument('--json')
    ap.add_argument('--alpha-ref'); ap.add_argument('--alpha-out')
    a = ap.parse_args()
    al = lambda p: (cv2.imread(p, cv2.IMREAD_UNCHANGED)[..., 3].astype(np.float32) / 255) if p else None
    res = measure(load(a.reference), load(a.render), al(a.alpha_ref), al(a.alpha_out))
    res['reference'] = a.reference; res['render'] = a.render
    txt = json.dumps(res, indent=1)
    if a.json:
        open(a.json, 'w').write(txt + '\n')
    print(txt)
    sys.exit(0 if res['pass'] else 1)


if __name__ == '__main__':
    main()
