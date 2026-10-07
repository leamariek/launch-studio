"""Shared helpers for the fitters: array backend (CuPy on an NVIDIA GPU, NumPy plus OpenCV on the CPU), color
conversion, image filters and image I/O. Only the fitters read reference images. The renderer never does."""
import os
import numpy as np
import cv2

try:
    if os.environ.get('HAND_DRAWN_CPU'):
        raise ImportError('CPU forced')
    import cupy as xp
    from cupyx.scipy import ndimage as _nd
    xp.zeros(1).sum()            # fails here if no usable GPU
    GPU = True
except Exception:                # no CuPy or no GPU: same code on NumPy and OpenCV
    xp = np
    _nd = None
    GPU = False


def backend():
    if GPU:
        return 'cupy on ' + xp.cuda.runtime.getDeviceProperties(0)['name'].decode()
    return 'numpy + opencv (CPU)'


def asnp(a):
    return xp.asnumpy(a) if GPU else np.asarray(a)


def asxp(a):
    return xp.asarray(a)


# ---------------------------------------------------------------- filters (same results on both backends, within float error)
def gauss(a, s):
    if s <= 0:
        return a
    if GPU:
        return _nd.gaussian_filter(a, s, mode='reflect')
    return cv2.GaussianBlur(np.ascontiguousarray(a, np.float32), (0, 0), s, borderType=cv2.BORDER_REFLECT)


def gauss_d(a, s, dy, dx):
    """Gaussian derivative of order (dy, dx)."""
    if GPU:
        return _nd.gaussian_filter(a, s, order=(dy, dx), mode='reflect')
    r = int(4 * s + 0.5)
    x = np.arange(-r, r + 1, dtype=np.float64)
    g = np.exp(-x * x / (2 * s * s)); g /= g.sum()
    ker = [g, -x / (s * s) * g, (x * x / s ** 4 - 1 / (s * s)) * g]
    k = lambda o: (ker[o][::-1] if o else ker[o]).astype(np.float32)
    return cv2.sepFilter2D(np.ascontiguousarray(a, np.float32), -1, k(dx), k(dy), borderType=cv2.BORDER_REFLECT)


def close(a, r):
    """Gray closing with a disk of radius r (upper envelope of dark marks)."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    if GPU:
        return _nd.grey_closing(a, footprint=xp.asarray(k > 0))
    return cv2.morphologyEx(np.ascontiguousarray(a, np.float32), cv2.MORPH_CLOSE, k)


def dilate_max(a, n):
    if GPU:
        return _nd.grey_dilation(a, size=(n, n))
    return cv2.dilate(np.ascontiguousarray(a, np.float32), np.ones((n, n), np.uint8))


def label(mask):
    """8-connected components. Returns (labels, count) on the active backend."""
    if GPU:
        lab, n = _nd.label(mask, structure=xp.ones((3, 3)))
        return lab, int(n)
    n, lab = cv2.connectedComponents(np.asarray(mask, np.uint8), connectivity=8)
    return lab, n - 1


def edt(mask):
    """Distance from each True pixel to the nearest False pixel."""
    if GPU:
        return _nd.distance_transform_edt(mask)
    return cv2.distanceTransform(np.asarray(mask, np.uint8), cv2.DIST_L2, 5)


def hysteresis(R, lo, hi, minsize):
    lab, n = label(R > lo)
    good = xp.zeros(n + 1, bool)
    good[xp.unique(lab[R > hi])] = True
    good[0] = False
    good &= xp.bincount(lab.ravel(), minlength=n + 1) >= minsize
    return good[lab]


# ---------------------------------------------------------------- thinning
_ZS = None


def skeletonize(mask):
    """Zhang-Suen thinning. A CUDA kernel on the GPU, vectorized NumPy on the CPU."""
    global _ZS
    m = xp.ascontiguousarray(mask.astype(xp.uint8))
    m[0, :] = m[-1, :] = 0; m[:, 0] = m[:, -1] = 0
    if GPU:
        if _ZS is None:
            _ZS = xp.RawKernel(r'''
extern "C" __global__ void zs(const unsigned char* a, unsigned char* b, int w, int h, int step, int* ch){
  int i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= w * h) return;
  int x = i % w, y = i / w; b[i] = a[i];
  if (!a[i] || x < 1 || y < 1 || x >= w - 1 || y >= h - 1) return;
  int n[8] = { a[i-w], a[i-w+1], a[i+1], a[i+w+1], a[i+w], a[i+w-1], a[i-1], a[i-w-1] };
  int B = 0, A = 0; for (int k = 0; k < 8; k++) { B += n[k] > 0; A += (!n[k]) && n[(k+1)&7]; }
  if (B < 2 || B > 6 || A != 1) return;
  if (step == 0 && ((n[0] && n[2] && n[4]) || (n[2] && n[4] && n[6]))) return;
  if (step == 1 && ((n[0] && n[2] && n[6]) || (n[0] && n[4] && n[6]))) return;
  b[i] = 0; atomicAdd(ch, 1);
}''', 'zs')
        h, w = m.shape; b = xp.empty_like(m); ch = xp.zeros(1, xp.int32); g = ((h * w + 255) // 256,)
        for _ in range(500):
            ch[0] = 0
            _ZS(g, (256,), (m, b, np.int32(w), np.int32(h), np.int32(0), ch))
            _ZS(g, (256,), (b, m, np.int32(w), np.int32(h), np.int32(1), ch))
            if int(ch[0]) == 0:
                break
        return m > 0
    a = m.astype(bool)
    for _ in range(500):
        changed = False
        for step in (0, 1):
            p = np.pad(a, 1)
            n = [p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:], p[2:, 2:], p[2:, 1:-1], p[2:, :-2], p[1:-1, :-2], p[:-2, :-2]]
            B = sum(x.astype(np.uint8) for x in n)
            A = sum(((~n[k]) & n[(k + 1) % 8]).astype(np.uint8) for k in range(8))
            if step == 0:
                c = ~(n[0] & n[2] & n[4]) & ~(n[2] & n[4] & n[6])
            else:
                c = ~(n[0] & n[2] & n[6]) & ~(n[0] & n[4] & n[6])
            rm = a & (B >= 2) & (B <= 6) & (A == 1) & c
            if rm.any():
                a = a & ~rm; changed = True
        if not changed:
            break
    return a


# ---------------------------------------------------------------- color
def _m(a):
    return np if isinstance(a, np.ndarray) else xp


def srgb_to_lin(x):
    return _m(x).where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(x):
    m = _m(x)
    x = m.clip(x, 0, 1)
    return m.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def lum(x):
    return 0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2]


def to_lab(srgb):
    """sRGB 0..1 to CIELAB (D65). Works on either backend (pass a NumPy or CuPy array)."""
    m = _m(srgb)
    lin = m.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    M = m.asarray([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], m.float32)
    xyz = (lin @ M.T) / m.asarray([0.95047, 1.0, 1.08883], m.float32)
    f = m.where(xyz > 0.008856, m.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return m.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


# ---------------------------------------------------------------- I/O
def read_rgb(path):
    """Reference image as sRGB float32 (H, W, 3) NumPy plus alpha (H, W)."""
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path)
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    a = im[..., 3].astype(np.float32) / 255 if im.shape[2] == 4 else np.ones(im.shape[:2], np.float32)
    return im[..., 2::-1].astype(np.float32) / 255, a


def write_rgb(path, srgb):
    a = np.clip(asnp(srgb), 0, 1)
    cv2.imwrite(path, (a[..., ::-1] * 255 + 0.5).astype(np.uint8))


def r(v, n=3):
    return round(float(v), n)
