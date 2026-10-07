"""Side-by-side review sheet: reference | code render on top, two 2x crops of the busiest areas below, gate numbers
at the bottom (from metrics.py).

usage: python side.py reference.png render.png sheet.jpg [--metrics metrics.json] [--crop 240x160]"""
import argparse, json
import numpy as np
import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('reference'); ap.add_argument('render'); ap.add_argument('out')
    ap.add_argument('--metrics'); ap.add_argument('--crop', default='240x160')
    a = ap.parse_args()
    ref = cv2.imread(a.reference, cv2.IMREAD_COLOR); out = cv2.imread(a.render, cv2.IMREAD_COLOR)
    H, W = ref.shape[:2]
    out = cv2.resize(out, (W, H)) if out.shape[:2] != (H, W) else out
    cw, ch = map(int, a.crop.split('x'))
    gap = lambda h, w: np.full((h, w, 3), 255, np.uint8)
    top = np.hstack([ref, gap(H, 12), out]); SW = top.shape[1]
    # crop centers: the two areas with the most edges, apart from each other
    e = cv2.boxFilter((cv2.Canny(cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY), 40, 90) > 0).astype(np.float32), -1, (cw, ch))
    centers = []
    for _ in range(2):
        y, x = np.unravel_index(np.argmax(e), e.shape); centers.append((y, x))
        e[max(0, y - ch):y + ch, max(0, x - cw):x + cw] = 0
    row = []
    for y, x in centers:
        y0, x0 = int(np.clip(y - ch // 2, 0, H - ch)), int(np.clip(x - cw // 2, 0, W - cw))
        z = lambda im: cv2.resize(im[y0:y0 + ch, x0:x0 + cw], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        row += [z(ref), gap(2 * ch, 12), z(out), gap(2 * ch, 36)]
    row = np.hstack(row)
    row = np.hstack([row, gap(2 * ch, SW - row.shape[1])]) if row.shape[1] < SW else row[:, :SW]

    def band(text):
        b = gap(48, SW); cv2.putText(b, text, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2, cv2.LINE_AA); return b
    parts = [band('reference | code render (no image loaded)'), top, band('2x crops: reference | code'), row]
    if a.metrics:
        m = json.load(open(a.metrics))
        parts.append(band('phone 480 px: CIEDE2000 %.2f  SSIM %.3f | edge F1 %.3f | silhouette IoU %.3f | %s' % (
            m['phone_480px']['ciede2000'], m['phone_480px']['ssim'], m['full']['edge_f1'], m['silhouette_iou'], 'PASS' if m['pass'] else 'FAIL')))
    cv2.imwrite(a.out, np.vstack(parts), [cv2.IMWRITE_JPEG_QUALITY, 90])
    print('wrote', a.out)


if __name__ == '__main__':
    main()
