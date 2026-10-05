#!/usr/bin/env python3
"""Colour fidelity of an encode against the renderer's own frames.

Usage: color_check.py video.mp4 --stills renders/stills [--max 2.0]
For every still_16x9_<t>.png rendered with the same --blur, decodes the video frame at t the way browsers
and X do (BT.709, range from the file's tags) and compares: mean abs diff per pixel and the mean brightness
shift. FAIL if the mean abs diff exceeds --max or the brightness shifts by more than 1.5 levels.
A double range conversion shows up as a shift of about -18 levels; an untagged BT.601 encode as a few levels.
"""
import argparse, glob, os, re, subprocess, json
import numpy as np

def rgb(p, t=None, vf=None):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{t:.4f}"] if t is not None else []) + ["-i", p]
    if vf: cmd += ["-vf", vf]
    cmd += ["-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    b = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(b, np.uint8)[:1920 * 1080 * 3].reshape(1080, 1920, 3).astype(float)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--stills", default="renders/stills"); ap.add_argument("--max", type=float, default=2.0)
    a = ap.parse_args()
    tags = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_range,color_space", "-of", "json", a.video], capture_output=True, text=True).stdout)["streams"][0]
    rng = "pc" if tags.get("color_range") == "pc" else "tv"
    vf = f"scale=in_color_matrix=bt709:in_range={rng}:flags=accurate_rnd+full_chroma_int"
    print(f"# colour check: {a.video}  (tags: range {tags.get('color_range')}, matrix {tags.get('color_space')})")
    worst = 0; fail = False
    if tags.get("color_space") != "bt709": print("WARN: no BT.709 tag; players may decode with BT.601"); fail = True
    for s in sorted(glob.glob(os.path.join(a.stills, "still_16x9_*.png"))):
        t = float(re.search(r"_([\d.]+)\.png$", s).group(1))
        src, enc = rgb(s), rgb(a.video, t, vf)
        d = np.abs(enc - src).mean(); shift = enc.mean() - src.mean(); worst = max(worst, d)
        bad = d > a.max or abs(shift) > 1.5; fail |= bad
        print(f"t {t:6.2f}s  mean abs diff {d:5.2f}  brightness shift {shift:+5.2f}  {'FAIL' if bad else 'ok'}")
    print("FAIL" if fail else "PASS", f"(worst {worst:.2f})")
    raise SystemExit(1 if fail else 0)

if __name__ == "__main__":
    main()
