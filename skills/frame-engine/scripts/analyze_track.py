#!/usr/bin/env python3
"""Measure a music track for the beat map: tempo, beat phase, downbeats, the drop, loud peaks.

Usage: analyze_track.py track.mp3 [--from 0] [--to 40] [--json beats-track.json]
Needs ffmpeg and numpy. Prints a summary and optionally writes JSON.

Method: onset envelope from spectral flux (hop 512 at 22050 Hz), tempo by autocorrelation
between 70 and 180 BPM, beat phase by comb scoring, drop = largest rise of the 2 s RMS envelope.
Check the drop by ear-proxy: the energy table printed below shows RMS per second.
"""
import argparse, json, subprocess
import numpy as np

SR, HOP, N = 22050, 512, 2048

def decode(path, t0, t1):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(t0)] + (["-to", str(t1)] if t1 else []) + ["-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("track"); ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=None); ap.add_argument("--json")
    a = ap.parse_args()
    x = decode(a.track, a.t0, a.t1)
    frames = 1 + (len(x) - N) // HOP
    win = np.hanning(N)
    spec = np.abs(np.fft.rfft(np.stack([x[i * HOP:i * HOP + N] * win for i in range(frames)]), axis=1))
    logspec = np.log1p(spec * 10)
    flux = np.maximum(0, np.diff(logspec, axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux]); flux -= flux.mean(); flux[flux < 0] = 0
    fr = SR / HOP
    # tempo
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    lags = np.arange(len(ac)); bpm = 60 * fr / np.maximum(lags, 1)
    ok = (bpm >= 70) & (bpm <= 180)
    lag = lags[ok][np.argmax(ac[ok])]
    tempo = 60 * fr / lag
    # octave / triplet errors: test tempo x 1.5, x 2, / 1.5, / 2 with a comb score over the onset envelope
    def comb(bpm_):
        per = 60 / bpm_; best = 0.0
        for o in np.linspace(0, per, 32, endpoint=False):
            ii = np.clip(((np.arange(o, len(flux) / fr, per)) * fr).round().astype(int), 0, len(flux) - 1)
            best = max(best, flux[ii].mean())
        return best
    cands = [tempo * k for k in (1, 1.5, 2, 2 / 3, 0.5, 4 / 3, 0.75) if 70 <= tempo * k <= 180]
    scores = [comb(c) * (1.1 if 95 <= c <= 135 else 1.0) for c in cands]
    tempo = cands[int(np.argmax(scores))]
    lag = 60 * fr / tempo
    # refine with parabolic fit
    li = int(round(lag))
    if 1 < li < len(ac) - 1 and abs(lag - li) < 1e-6:
        y0, y1, y2 = ac[li - 1], ac[li], ac[li + 1]; d = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-9); tempo = 60 * fr / (li + d)
    period = 60 / tempo
    # beat phase: comb score over candidate offsets
    offs = np.linspace(0, period, 64, endpoint=False)
    t_frames = np.arange(len(flux)) / fr
    def score(o):
        beats = np.arange(o, t_frames[-1], period)
        idx = np.clip((beats * fr).round().astype(int), 0, len(flux) - 1)
        return flux[idx].sum()
    phase = offs[np.argmax([score(o) for o in offs])]
    beats = np.arange(phase, len(x) / SR, period)
    # downbeat: which of 4 beat positions carries the most onset energy
    idx = np.clip((beats * fr).round().astype(int), 0, len(flux) - 1)
    bar_pos = np.argmax([flux[idx[k::4]].sum() for k in range(4)])
    downbeats = beats[bar_pos::4]
    # energy per 0.5 s and the drop
    hop_s = int(SR * 0.5); rms = np.array([np.sqrt(np.mean(x[i:i + hop_s] ** 2) + 1e-12) for i in range(0, len(x) - hop_s, hop_s)])
    db = 20 * np.log10(rms + 1e-9)
    # drop: the largest step up between the 2 s before and the 2 s after a point (valid windows only)
    k = 4
    # a drop is the step INTO the loudest sustained section: earliest point whose next 2 s sit within
    # 2 dB of the loudest 2 s and that rises at least 3 dB over the 2 s before it
    after = np.array([db[i:i + k].mean() for i in range(k, len(db) - k)])
    rise = np.array([db[i:i + k].mean() - db[i - k:i].mean() for i in range(k, len(db) - k)])
    loud = np.percentile(db, 90)
    first_loud = np.array([db[i:i + 2].min() for i in range(k, len(db) - k)])   # the point itself is already loud
    ok_ = np.where((first_loud >= loud - 3) & (after >= after.max() - 2) & (rise >= 3))[0]
    j = int(ok_[0]) if len(ok_) else int(np.argmax(rise))
    # refine inside the window to the strongest onset, then snap to the beat grid
    lo_f, hi_f = int((j + k - 2) * 0.5 * fr), int((j + k + 1) * 0.5 * fr)
    drop_t = (lo_f + int(np.argmax(flux[lo_f:hi_f]))) / fr if hi_f > lo_f else (j + k) * 0.5
    drop_t = float(beats[np.argmin(np.abs(beats - drop_t))])
    # downbeats: the drop lands on a downbeat
    downbeats = beats[(np.round((beats - drop_t) / period).astype(int)) % 4 == 0]
    peaks = [float(t) for t in (np.argsort(flux)[::-1][:24] / fr)]
    out = {"file": a.track, "offset": a.t0, "bpm": round(float(tempo), 2), "beat": round(period, 4),
           "first_beat": round(float(phase), 3), "downbeats": [round(float(t), 3) for t in downbeats[:64]],
           "drop": round(drop_t, 3), "energy_db_per_half_second": [round(float(v), 1) for v in db],
           "strongest_onsets": sorted(round(p, 3) for p in peaks)}
    print(f"bpm {out['bpm']}  beat {out['beat']} s  first beat {out['first_beat']} s  drop ~{out['drop']} s")
    print("downbeats:", " ".join(f"{t:.2f}" for t in out["downbeats"][:24]))
    print("energy dB per 0.5 s:", " ".join(f"{v:.0f}" for v in db[:80]))
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1); print("wrote", a.json)

if __name__ == "__main__":
    main()
