#!/usr/bin/env python3
"""Automated frame and audio QA for rendered launch films.

Flags:
  POP     single frame that differs sharply from both neighbors while neighbors match
  CUT     hard cut anywhere (the film is one continuous take); allowed only inside --strobe ranges
  FREEZE  no visible change for longer than --freeze seconds (default 1.0: holds over 1 s break the standard)
  BLACK   near-black frames outside the first/last 0.5 s
  LOUD    integrated loudness or true peak out of spec
Usage: qa_frames.py film.mp4 [--strobe "23.0-24.0,59-60.2"] [--freeze 1.0] [--lufs -14]
"""
import argparse, json, subprocess, sys
import numpy as np

W, H = 160, 90

def frames(path):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={W}:{H}:flags=area,format=gray",
                          "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    size = W * H
    while True:
        b = p.stdout.read(size)
        if len(b) < size:
            break
        yield np.frombuffer(b, np.uint8).astype(np.float32)

def fps_of(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    n, d = r.split("/")
    return float(n) / float(d)

def loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = r.stderr
    if "input_i" not in txt:
        return None
    j = json.loads(txt[txt.rfind("{"):txt.rfind("}") + 1])
    return float(j["input_i"]), float(j["input_tp"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--beats"); ap.add_argument("--freeze", type=float, default=1.0)
    ap.add_argument("--strobe", default="", help="time ranges where hard cuts are intended, e.g. 23.0-24.0,59-60")
    ap.add_argument("--lufs", type=float, default=-14.0)
    a = ap.parse_args()
    fps = fps_of(a.video)
    fr = list(frames(a.video))
    n = len(fr)
    if n < 3:
        sys.exit("not enough frames")
    d = np.array([np.mean(np.abs(fr[i + 1] - fr[i])) for i in range(n - 1)])  # d[i] = diff(i, i+1)
    med = float(np.median(d)) + 1e-3
    issues = []

    strobe = [tuple(map(float, r.split("-"))) for r in a.strobe.split(",") if r]

    for i in range(1, n - 1):
        into, outof = d[i - 1], d[i]
        skip = np.mean(np.abs(fr[i + 1] - fr[i - 1]))
        if into > 6 * med and outof > 6 * med and skip < 0.35 * min(into, outof):
            issues.append(("POP", i, i / fps, f"frame differs {into:.1f}/{outof:.1f} vs neighbors {skip:.1f}"))
    thr = max(12.0, 8 * med)
    for i, v in enumerate(d):
        prev = d[i - 1] if i > 0 else 0.0
        nxt = d[i + 1] if i + 1 < len(d) else 0.0
        # a cut is an isolated spike; a fast flood or pan changes many frames in a row
        if v > thr and prev < 0.35 * v and nxt < 0.35 * v:
            t = (i + 1) / fps
            if not any(s0 <= t <= s1 for s0, s1 in strobe):
                issues.append(("CUT", i + 1, t, f"hard change {v:.1f}: the take is broken here"))
    run = 0
    for i, v in enumerate(d):
        run = run + 1 if v < 0.05 else 0
        if run == int(a.freeze * fps):
            issues.append(("FREEZE", i, i / fps, f">= {a.freeze}s without change (fine if it is a planned hold)"))
    for i, f in enumerate(fr):
        t = i / fps
        if 0.5 < t < n / fps - 0.5 and f.mean() < 3:
            issues.append(("BLACK", i, t, "near-black frame"))
            break
    L = loudness(a.video)
    if L:
        I, TP = L
        if abs(I - a.lufs) > 1.0 or TP > -0.9:
            issues.append(("LOUD", -1, 0, f"integrated {I:.1f} LUFS (target {a.lufs}), true peak {TP:.1f} dBTP"))

    print(f"# QA: {a.video}\n{n} frames @ {fps:g} fps, median frame delta {med:.2f}\n")
    if not issues:
        print("PASS: no issues found"); return
    print("| Type | Frame | Time (s) | Detail |\n|---|---|---|---|")
    for k, f, t, m in issues:
        print(f"| {k} | {f} | {t:.3f} | {m} |")
    hard = [x for x in issues if x[0] in ("POP", "CUT", "BLACK", "LOUD")]
    print(f"\n{'FAIL' if hard else 'REVIEW'}: {len(hard)} hard issue(s), {len(issues) - len(hard)} to review")
    sys.exit(1 if hard else 0)

if __name__ == "__main__":
    main()
