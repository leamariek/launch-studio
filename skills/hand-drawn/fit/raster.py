"""GPU stroke rasterizer with analytic gradients (CUDA kernels through CuPy), the model the stroke optimizer fits.

The model is the renderer's pencil stroke (engine/inkwash.js, FS_STROKE without the paper tooth):
  half width hw and pressure p are interpolated along each segment, d = distance from the pixel center to the segment,
  coverage = clamp(hw + 0.5 - d, 0, 1), profile = 1 - 0.2 * d / (hw + 1),
  darkness of one segment = k * p * coverage * profile, k = 1 - lum(ink color) of its stroke,
  darkness of a pixel = MAX over all segments (graphite over graphite does not stack).
Coordinates follow the GL convention: pixel (i, j) has its center at (i + 0.5, j + 0.5).

Strokes are packed as one vertex array V (N, 4: x, y, width, pressure) plus a segment list (S, 2: vertex a, vertex b)
and a per-segment darkness factor k (S,). Forward returns the darkness image and, per pixel, the segment that owns the
maximum; backward sends the loss gradient of each pixel to its owner only (the subgradient of MAX)."""
import numpy as np
import cupy as cp

_SRC = r'''
extern "C" {
__device__ __forceinline__ void seg_eval(const float* V, int ia, int ib, float px, float py,
    float* t_, float* d_, float* nx_, float* ny_, float* hw_, float* p_) {
  float ax = V[4*ia], ay = V[4*ia+1], bx = V[4*ib], by = V[4*ib+1];
  float ex = bx - ax, ey = by - ay, L2 = ex*ex + ey*ey;
  float t = L2 > 1e-8f ? ((px - ax)*ex + (py - ay)*ey) / L2 : 0.f;
  t = fminf(fmaxf(t, 0.f), 1.f);
  float cx = ax + t*ex, cy = ay + t*ey, dx = px - cx, dy = py - cy;
  float d = sqrtf(dx*dx + dy*dy);
  *t_ = t; *d_ = d; *nx_ = d > 1e-6f ? dx/d : 0.f; *ny_ = d > 1e-6f ? dy/d : 0.f;
  *hw_ = 0.5f * ((1.f - t)*V[4*ia+2] + t*V[4*ib+2]);
  *p_ = (1.f - t)*V[4*ia+3] + t*V[4*ib+3];
}

__global__ void fwd(const float* V, const int* S, const float* K, int nseg, int W, int H, unsigned long long* best) {
  int s = blockIdx.x; if (s >= nseg) return;
  int ia = S[2*s], ib = S[2*s+1];
  float r = 0.5f * fmaxf(V[4*ia+2], V[4*ib+2]) + 1.5f;
  int x0 = max(0, (int)floorf(fminf(V[4*ia], V[4*ib]) - r)), x1 = min(W - 1, (int)ceilf(fmaxf(V[4*ia], V[4*ib]) + r));
  int y0 = max(0, (int)floorf(fminf(V[4*ia+1], V[4*ib+1]) - r)), y1 = min(H - 1, (int)ceilf(fmaxf(V[4*ia+1], V[4*ib+1]) + r));
  int bw = x1 - x0 + 1, bh = y1 - y0 + 1; if (bw <= 0 || bh <= 0) return;
  float k = K[s];
  for (int i = threadIdx.x; i < bw*bh; i += blockDim.x) {
    int x = x0 + i % bw, y = y0 + i / bw;
    float t, d, nx, ny, hw, p; seg_eval(V, ia, ib, x + 0.5f, y + 0.5f, &t, &d, &nx, &ny, &hw, &p);
    float cov = fminf(fmaxf(hw + 0.5f - d, 0.f), 1.f);
    if (cov <= 0.f) continue;
    float prof = 1.f - 0.2f * d / (hw + 1.f);
    float v = fminf(fmaxf(k * p * cov * prof, 0.f), 1.f);
    unsigned long long pk = ((unsigned long long)__float_as_uint(v) << 32) | (unsigned long long)(s + 1);
    atomicMax(&best[y*W + x], pk);
  }
}

__global__ void bwd(const float* V, const int* S, const float* K, int nseg, int W, int H, const unsigned long long* best,
                    const float* G, float* gV) {
  int s = blockIdx.x; if (s >= nseg) return;
  int ia = S[2*s], ib = S[2*s+1];
  float r = 0.5f * fmaxf(V[4*ia+2], V[4*ib+2]) + 1.5f;
  int x0 = max(0, (int)floorf(fminf(V[4*ia], V[4*ib]) - r)), x1 = min(W - 1, (int)ceilf(fmaxf(V[4*ia], V[4*ib]) + r));
  int y0 = max(0, (int)floorf(fminf(V[4*ia+1], V[4*ib+1]) - r)), y1 = min(H - 1, (int)ceilf(fmaxf(V[4*ia+1], V[4*ib+1]) + r));
  int bw = x1 - x0 + 1, bh = y1 - y0 + 1; if (bw <= 0 || bh <= 0) return;
  float k = K[s];
  for (int i = threadIdx.x; i < bw*bh; i += blockDim.x) {
    int x = x0 + i % bw, y = y0 + i / bw, q = y*W + x;
    if ((int)(best[q] & 0xffffffffULL) != s + 1) continue;
    float g = G[q]; if (g == 0.f) continue;
    float t, d, nx, ny, hw, p; seg_eval(V, ia, ib, x + 0.5f, y + 0.5f, &t, &d, &nx, &ny, &hw, &p);
    float e = hw + 0.5f - d;
    float cov = fminf(fmaxf(e, 0.f), 1.f), dcov = (e > 0.f && e < 1.f) ? 1.f : 0.f;
    float prof = 1.f - 0.2f * d / (hw + 1.f);
    float v = k * p * cov * prof; if (v <= 0.f || v >= 1.f) { if (v <= 0.f) continue; }
    float dv_dp = k * cov * prof;
    float dv_dd = k * p * (-dcov * prof + cov * (-0.2f / (hw + 1.f)));
    float dv_dhw = k * p * (dcov * prof + cov * 0.2f * d / ((hw + 1.f) * (hw + 1.f)));
    float wa = 1.f - t, wb = t;
    // d(distance)/d(endpoint) = -(weight) * n ; d(hw)/d(width) = 0.5 * weight
    atomicAdd(&gV[4*ia],   g * dv_dd * (-wa * nx)); atomicAdd(&gV[4*ia+1], g * dv_dd * (-wa * ny));
    atomicAdd(&gV[4*ib],   g * dv_dd * (-wb * nx)); atomicAdd(&gV[4*ib+1], g * dv_dd * (-wb * ny));
    atomicAdd(&gV[4*ia+2], g * dv_dhw * 0.5f * wa); atomicAdd(&gV[4*ib+2], g * dv_dhw * 0.5f * wb);
    atomicAdd(&gV[4*ia+3], g * dv_dp * wa);          atomicAdd(&gV[4*ib+3], g * dv_dp * wb);
  }
}

// colored forward: per channel MAX of darkness k_c * a (used for model renders of the ink, not for gradients)
__global__ void fwd_rgb(const float* V, const int* S, const float* K3, int nseg, int W, int H, unsigned int* D3) {
  int s = blockIdx.x; if (s >= nseg) return;
  int ia = S[2*s], ib = S[2*s+1];
  float r = 0.5f * fmaxf(V[4*ia+2], V[4*ib+2]) + 1.5f;
  int x0 = max(0, (int)floorf(fminf(V[4*ia], V[4*ib]) - r)), x1 = min(W - 1, (int)ceilf(fmaxf(V[4*ia], V[4*ib]) + r));
  int y0 = max(0, (int)floorf(fminf(V[4*ia+1], V[4*ib+1]) - r)), y1 = min(H - 1, (int)ceilf(fmaxf(V[4*ia+1], V[4*ib+1]) + r));
  int bw = x1 - x0 + 1, bh = y1 - y0 + 1; if (bw <= 0 || bh <= 0) return;
  for (int i = threadIdx.x; i < bw*bh; i += blockDim.x) {
    int x = x0 + i % bw, y = y0 + i / bw;
    float t, d, nx, ny, hw, p; seg_eval(V, ia, ib, x + 0.5f, y + 0.5f, &t, &d, &nx, &ny, &hw, &p);
    float cov = fminf(fmaxf(hw + 0.5f - d, 0.f), 1.f); if (cov <= 0.f) continue;
    float a = fminf(fmaxf(p * cov * (1.f - 0.2f * d / (hw + 1.f)), 0.f), 1.f);
    for (int c = 0; c < 3; c++) atomicMax(&D3[3*(y*W + x) + c], __float_as_uint(fminf(a * K3[3*s + c], 1.f)));
  }
}
}
'''
_mod = None


def _k(name):
    global _mod
    if _mod is None:
        _mod = cp.RawModule(code=_SRC)
    return _mod.get_function(name)


class Pack:
    """Strokes as GPU arrays. strokes: list of dicts with p (n, 4) and col (3,) linear ink transmittance."""

    def __init__(self, strokes):
        self.counts = np.array([len(s['p']) for s in strokes], np.int64)
        self.offs = np.concatenate([[0], np.cumsum(self.counts)])[:-1]
        V = np.concatenate([np.asarray(s['p'], np.float32) for s in strokes]) if strokes else np.zeros((0, 4), np.float32)
        segs, kk, k3 = [], [], []
        for i, s in enumerate(strokes):
            n, o = self.counts[i], self.offs[i]
            col = np.asarray(s['col'], np.float32)
            if n < 2:
                continue
            a = np.arange(o, o + n - 1)
            segs.append(np.stack([a, a + 1], 1))
            kk.append(np.full(n - 1, 1 - float(col @ np.array([0.2126, 0.7152, 0.0722])), np.float32))
            k3.append(np.repeat((1 - col)[None], n - 1, 0))
        self.V = cp.asarray(V)
        self.S = cp.asarray(np.concatenate(segs).astype(np.int32) if segs else np.zeros((0, 2), np.int32))
        self.K = cp.asarray(np.concatenate(kk) if kk else np.zeros(0, np.float32))
        self.K3 = cp.asarray(np.concatenate(k3).astype(np.float32) if k3 else np.zeros((0, 3), np.float32))
        # neighbors inside a stroke (for smoothness); -1 at stroke ends
        prev = np.arange(len(V)) - 1; nxt = np.arange(len(V)) + 1
        for o, n in zip(self.offs, self.counts):
            prev[o] = -1; nxt[o + n - 1] = -1
        self.prev, self.next = cp.asarray(prev), cp.asarray(nxt)

    def strokes(self, like):
        V = cp.asnumpy(self.V)
        out = []
        for i, s in enumerate(like):
            q = dict(s); q['p'] = V[self.offs[i]:self.offs[i] + self.counts[i]].copy(); out.append(q)
        return out


def forward(P, H, W):
    best = cp.zeros(H * W, cp.uint64)
    n = int(P.S.shape[0])
    if n:
        _k('fwd')((n,), (64,), (P.V, P.S, P.K, np.int32(n), np.int32(W), np.int32(H), best))
    D = (best >> 32).astype(cp.uint32).view(cp.float32).reshape(H, W)
    return D, best


def backward(P, H, W, best, G):
    gV = cp.zeros_like(P.V)
    n = int(P.S.shape[0])
    if n:
        _k('bwd')((n,), (64,), (P.V, P.S, P.K, np.int32(n), np.int32(W), np.int32(H), best, cp.ascontiguousarray(G, cp.float32), gV))
    return gV


def render_rgb(P, H, W):
    """Ink transmittance (H, W, 3) of the model."""
    D3 = cp.zeros(H * W * 3, cp.uint32)
    n = int(P.S.shape[0])
    if n:
        _k('fwd_rgb')((n,), (64,), (P.V, P.S, P.K3, np.int32(n), np.int32(W), np.int32(H), D3))
    return 1 - D3.view(cp.float32).reshape(H, W, 3)
