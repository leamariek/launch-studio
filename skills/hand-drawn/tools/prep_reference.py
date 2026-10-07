"""Prepare a reference image for fitting: center-crop to the target aspect (16:9 by default), scale to the target size
with area filtering, save as a high-quality JPEG close to a size budget, so the reference can ship with the project.

usage: python prep_reference.py in.png out.jpg [--size 1920x1080] [--kb 1000]"""
import argparse, os
import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--size', default='1920x1080'); ap.add_argument('--kb', type=int, default=1000)
    a = ap.parse_args()
    W, H = map(int, a.size.split('x'))
    im = cv2.imread(a.src, cv2.IMREAD_COLOR)
    h, w = im.shape[:2]
    if w * H > h * W:                                   # too wide: crop the sides equally
        cw = round(h * W / H); x0 = (w - cw) // 2; im = im[:, x0:x0 + cw]
    else:                                               # too tall: crop top and bottom equally
        ch = round(w * H / W); y0 = (h - ch) // 2; im = im[y0:y0 + ch]
    im = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
    best = None
    for q in range(97, 79, -1):                          # highest quality that fits the budget
        ok, buf = cv2.imencode('.jpg', im, [cv2.IMWRITE_JPEG_QUALITY, q, cv2.IMWRITE_JPEG_OPTIMIZE, 1])
        best = (q, buf)
        if len(buf) <= a.kb * 1024:
            break
    open(a.out, 'wb').write(best[1].tobytes())
    print(f'wrote {a.out}: {W}x{H}, crop from {w}x{h}, JPEG quality {best[0]}, {os.path.getsize(a.out) / 1024:.0f} KB')


if __name__ == '__main__':
    main()
