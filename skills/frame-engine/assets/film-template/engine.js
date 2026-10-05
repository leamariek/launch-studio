// Launch Studio engine v2. One canvas, one camera, one world.
// Every pixel is a pure function of t: no timers, no state carried between frames.
(() => {
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, p) => a + (b - a) * p;

  // ---------- easing ----------
  function bezier(x1, y1, x2, y2) {
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const sx = t => ((ax * t + bx) * t + cx) * t, sy = t => ((ay * t + by) * t + cy) * t;
    const dx = t => (3 * ax * t + 2 * bx) * t + cx;
    return x => {
      if (x <= 0) return 0; if (x >= 1) return 1;
      let t = x;
      for (let i = 0; i < 8; i++) { const e = sx(t) - x; if (Math.abs(e) < 1e-6) return sy(t); const d = dx(t); if (Math.abs(d) < 1e-6) break; t -= e / d; }
      let lo = 0, hi = 1; t = x;
      for (let i = 0; i < 30; i++) { const v = sx(t); if (Math.abs(v - x) < 1e-6) break; v < x ? lo = t : hi = t; t = (lo + hi) / 2; }
      return sy(t);
    };
  }
  const ease = {
    linear: x => x,
    glide: bezier(0.45, 0, 0.15, 1),   // morphs and camera (reference default)
    out: bezier(0.16, 1, 0.3, 1),      // entrances
    in: bezier(0.7, 0, 0.84, 0),       // exits
    inOut: bezier(0.65, 0, 0.35, 1),
    backOut: (s = 1.70158) => x => 1 + (s + 1) * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2),
  };
  // progress of t in [a, a+d] with easing; tween between values
  const P = (t, a, d, e = ease.glide) => e(clamp((t - a) / d));
  const tw = (t, a, d, from, to, e = ease.glide) => lerp(from, to, P(t, a, d, e));

  // ---------- colour ----------
  const hex = h => { h = h.replace('#', ''); if (h.length === 3) h = [...h].map(c => c + c).join(''); return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), 1]; };
  const parse = c => Array.isArray(c) ? c : c.startsWith('#') ? hex(c) : (c.match(/[\d.]+/g) || [0, 0, 0, 1]).map(Number).concat(1).slice(0, 4);
  const mix = (a, b, p) => { const A = parse(a), B = parse(b); return `rgba(${lerp(A[0], B[0], p) | 0},${lerp(A[1], B[1], p) | 0},${lerp(A[2], B[2], p) | 0},${lerp(A[3], B[3], p)})`; };
  const alpha = (c, a) => { const A = parse(c); return `rgba(${A[0]},${A[1]},${A[2]},${A[3] * a})`; };

  // ---------- seeded random ----------
  const rand = seed => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let x = Math.imul(seed ^ seed >>> 15, 1 | seed); x = x + Math.imul(x ^ x >>> 7, 61 | x) ^ x; return ((x ^ x >>> 14) >>> 0) / 4294967296; };

  // ---------- camera ----------
  // keys: [{t, x, y, z, e?}] ; between keys the camera glides; zoom interpolates in log space.
  function camera(keys) {
    return t => {
      if (t <= keys[0].t) return { ...keys[0] };
      for (let i = 1; i < keys.length; i++) {
        const a = keys[i - 1], b = keys[i];
        if (t <= b.t) {
          const p = (b.e || ease.glide)(clamp((t - a.t) / (b.t - a.t)));
          return { x: lerp(a.x, b.x, p), y: lerp(a.y, b.y, p), z: Math.exp(lerp(Math.log(a.z), Math.log(b.z), p)) };
        }
      }
      return { ...keys[keys.length - 1] };
    };
  }
  let W = 1920, H = 1080;
  const view = (ctx, cam) => ctx.setTransform(cam.z, 0, 0, cam.z, W / 2 - cam.x * cam.z, H / 2 - cam.y * cam.z);
  const screen = ctx => ctx.setTransform(1, 0, 0, 1, 0, 0);
  const toScreen = (cam, x, y) => [W / 2 + (x - cam.x) * cam.z, H / 2 + (y - cam.y) * cam.z];

  // ---------- shapes ----------
  // rect as {x, y, w, h, r} with x, y = centre
  function rrect(ctx, R) {
    const r = Math.max(0, Math.min(R.r, R.w / 2, R.h / 2));
    const x = R.x - R.w / 2, y = R.y - R.h / 2;
    ctx.beginPath(); ctx.roundRect(x, y, R.w, R.h, r);
  }
  const lerpRect = (a, b, p) => ({ x: lerp(a.x, b.x, p), y: lerp(a.y, b.y, p), w: lerp(a.w, b.w, p), h: lerp(a.h, b.h, p), r: lerp(a.r, b.r, p) });
  // soft layered shadow that grows with height (0 = on the stage, 1 = lifted)
  function lift(ctx, height, drawPath, fill, scale = 1) {
    const layers = [[0.10, 2, 1], [0.08, 10, 4], [0.07, 36, 16]];
    ctx.save();
    for (const [a, blur, dy] of layers) {
      ctx.shadowColor = `rgba(58,40,12,${a * (0.4 + height)})`;
      ctx.shadowBlur = blur * (0.5 + height * 1.5) * scale; ctx.shadowOffsetY = dy * (0.5 + height * 1.5) * scale;
      drawPath(); ctx.fillStyle = fill; ctx.fill();
    }
    ctx.restore();
  }
  // polylines: resample to n points by arc length, then morph point by point
  function resample(pts, n, closed = true) {
    const P2 = closed ? [...pts, pts[0]] : pts;
    const seg = []; let L = 0;
    for (let i = 1; i < P2.length; i++) { const d = Math.hypot(P2[i][0] - P2[i - 1][0], P2[i][1] - P2[i - 1][1]); seg.push(d); L += d; }
    const out = []; let i = 0, acc = 0;
    for (let k = 0; k < n; k++) {
      const target = (k / (closed ? n : n - 1)) * L;
      while (i < seg.length - 1 && acc + seg[i] < target) { acc += seg[i]; i++; }
      const q = seg[i] ? (target - acc) / seg[i] : 0;
      out.push([lerp(P2[i][0], P2[i + 1][0], q), lerp(P2[i][1], P2[i + 1][1], q)]);
    }
    return out;
  }
  const morphPts = (A, B, p) => A.map((a, i) => [lerp(a[0], B[i][0], p), lerp(a[1], B[i][1], p)]);
  function poly(ctx, pts, closed = true) { ctx.beginPath(); pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); if (closed) ctx.closePath(); }
  const circlePts = (cx, cy, r, n = 96) => Array.from({ length: n }, (_, i) => [cx + r * Math.cos(-Math.PI / 2 + i / n * 2 * Math.PI), cy + r * Math.sin(-Math.PI / 2 + i / n * 2 * Math.PI)]);
  const rectPts = (R, n = 96) => { // rounded rect outline as points, starting top centre, clockwise
    const c = document.createElement('canvas').getContext('2d'); const pts = [];
    const r = Math.min(R.r, R.w / 2, R.h / 2), x0 = R.x - R.w / 2, y0 = R.y - R.h / 2, x1 = x0 + R.w, y1 = y0 + R.h;
    const arc = (cx, cy, a0) => { for (let k = 0; k <= 8; k++) { const a = a0 + k / 8 * Math.PI / 2; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); } };
    pts.push([R.x, y0]); arc(x1 - r, y0 + r, -Math.PI / 2); arc(x1 - r, y1 - r, 0); arc(x0 + r, y1 - r, Math.PI / 2); arc(x0 + r, y0 + r, Math.PI);
    return resample(pts, n);
  };

  // ---------- goo, flood ----------
  let gooCanvas = null;
  function ensureGooFilter() {
    if (document.getElementById('ls-goo')) return;
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('width', 0); s.setAttribute('height', 0); s.style.position = 'absolute';
    s.innerHTML = '<filter id="ls-goo" color-interpolation-filters="sRGB"><feGaussianBlur in="SourceGraphic" stdDeviation="12" result="b"/><feColorMatrix in="b" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -7" result="g"/><feComposite in="SourceGraphic" in2="g" operator="atop"/></filter>';
    document.body.appendChild(s);
  }
  // draw blobs with drawFn(offCtx) using the same transform as ctx; they merge where they touch
  function goo(ctx, drawFn) {
    ensureGooFilter();
    if (!gooCanvas) { gooCanvas = document.createElement('canvas'); }
    gooCanvas.width = ctx.canvas.width; gooCanvas.height = ctx.canvas.height;
    const g = gooCanvas.getContext('2d'); g.setTransform(ctx.getTransform()); drawFn(g);
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.filter = 'url(#ls-goo)'; ctx.drawImage(gooCanvas, 0, 0); ctx.restore();
  }
  // flood from a screen point to the farthest corner; p in [0,1]
  function flood(ctx, sx, sy, p, color) {
    const R = Math.max(Math.hypot(sx, sy), Math.hypot(W - sx, sy), Math.hypot(sx, H - sy), Math.hypot(W - sx, H - sy));
    ctx.save(); screen(ctx); ctx.beginPath(); ctx.arc(sx, sy, R * p, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill(); ctx.restore();
  }

  // ---------- cursor (macOS arrow, drawn in screen space) ----------
  const ARROW = [[0, 0], [0, 17.5], [4.2, 13.6], [7.1, 20.1], [9.9, 18.9], [7.1, 12.5], [12.6, 12.5]];
  function cursor(ctx, sx, sy, press = 0, size = 1.6) {
    const s = size * (1 - 0.1 * press);
    ctx.save(); screen(ctx); ctx.translate(sx, sy); ctx.scale(s, s);
    ctx.shadowColor = 'rgba(0,0,0,0.28)'; ctx.shadowBlur = 3; ctx.shadowOffsetY = 1;
    poly(ctx, ARROW); ctx.fillStyle = '#fff'; ctx.lineJoin = 'round'; ctx.lineWidth = 2.6; ctx.strokeStyle = '#fff'; ctx.stroke(); ctx.fill();
    ctx.shadowColor = 'transparent'; poly(ctx, ARROW); ctx.fillStyle = '#000'; ctx.fill();
    ctx.restore();
  }
  // cursor path through world keys [{t, x, y}], curved: the midpoint bows sideways by `bow`
  function cursorPath(keys, bow = 0.12) {
    return t => {
      if (t <= keys[0].t) return [keys[0].x, keys[0].y];
      for (let i = 1; i < keys.length; i++) {
        const a = keys[i - 1], b = keys[i];
        if (t <= b.t) {
          const p = ease.inOut(clamp((t - a.t) / (b.t - a.t)));
          const mx = (a.x + b.x) / 2 - (b.y - a.y) * bow, my = (a.y + b.y) / 2 + (b.x - a.x) * bow;
          const q = 1 - p;
          return [q * q * a.x + 2 * q * p * mx + p * p * b.x, q * q * a.y + 2 * q * p * my + p * p * b.y];
        }
      }
      const k = keys[keys.length - 1]; return [k.x, k.y];
    };
  }
  // press amount at time t for a click at tc (80 ms down, 120 ms up)
  const press = (t, tc) => t < tc - 0.08 || t > tc + 0.12 ? 0 : t < tc ? (t - tc + 0.08) / 0.08 : 1 - (t - tc) / 0.12;

  // ---------- type ----------
  const FONT = { display: 'system-ui', body: 'system-ui' };
  const font = (ctx, w, size, fam = 'display') => { ctx.font = `${w} ${size}px ${FONT[fam] || fam}`; };
  // Kinetic line: words rise from a mask with a blur, one by one.
  // opts: size, weight, family, color, tracking(em), stagger, dur, align('left'|'center'), accent: [word indices], marker: color, markerAt: time, out: exit time
  function line(ctx, text, x, y, t, t0, o = {}) {
    const size = o.size || 96, w = o.weight || 500, fam = o.family || 'display';
    font(ctx, w, size, fam); ctx.letterSpacing = `${(o.tracking ?? -0.03) * size}px`;
    const words = text.split(' '), space = ctx.measureText(' ').width;
    const widths = words.map(s => ctx.measureText(s).width);
    const total = widths.reduce((a, b) => a + b, 0) + space * (words.length - 1);
    let cx = o.align === 'center' ? x - total / 2 : o.align === 'right' ? x - total : x;
    const stagger = o.stagger ?? 0.07, dur = o.dur ?? 0.55;
    const boxes = [];
    words.forEach((s, i) => {
      const pin = P(t, t0 + i * stagger, dur, ease.out);
      const pout = o.out == null ? 0 : P(t, o.out + i * stagger * 0.5, 0.4, ease.in);
      const a = pin * (1 - pout);
      boxes.push([cx, widths[i]]);
      if (a > 0.001) {
        // marker under accent words, drawn before the word
        if (o.accent?.includes(i) && o.marker) {
          const pm = P(t, o.markerAt ?? (t0 + words.length * stagger + 0.2), 0.7, ease.out) * (1 - pout);
          ctx.save(); ctx.globalAlpha *= a; ctx.fillStyle = o.marker; ctx.beginPath();
          ctx.roundRect(cx - size * 0.06, y - size * 0.62, (widths[i] + size * 0.12) * pm, size * 0.78, size * 0.12); ctx.fill(); ctx.restore();
        }
        ctx.save();
        ctx.beginPath(); ctx.rect(cx - size, y - size * 1.05, widths[i] + size * 2, size * 1.35); ctx.clip();
        const blur = (1 - pin) * 10 + pout * 10;
        if (blur > 0.3) ctx.filter = `blur(${blur}px)`;
        ctx.globalAlpha *= a; ctx.fillStyle = o.color || '#17150f';
        ctx.fillText(s, cx, y + (1 - pin) * size * 0.32 - pout * size * 0.2);
        ctx.restore();
      }
      cx += widths[i] + space;
    });
    ctx.letterSpacing = '0px';
    return { width: total, boxes };
  }
  // deterministic human typing: substring visible at t
  function typed(text, t, t0, msPerChar = 45, seed = 7) {
    const r = rand(seed); let acc = t0, n = 0;
    for (let i = 0; i < text.length; i++) {
      acc += msPerChar * (0.6 + r() * 0.8) / 1000 + (text[i - 1] === ' ' && r() < 0.3 ? 0.08 + r() * 0.12 : 0);
      if (acc <= t) n = i + 1;
    }
    return text.slice(0, n);
  }
  // counter that swaps whole values at fixed steps (never smears)
  const counter = (values, t, t0, step) => values[clamp(Math.floor((t - t0) / step), 0, values.length - 1)];

  // ---------- frame + motion blur ----------
  // film.draw(ctx, t) draws the whole frame. frame(t, n) averages n subframes over a 180 degree shutter.
  let film = null, main = null, work = null, FPS = 60;
  function init({ canvas, width = 1920, height = 1080, fps = 60, draw, fonts = {} }) {
    W = width; H = height; FPS = fps; Object.assign(FONT, fonts);
    canvas.width = W; canvas.height = H; main = canvas.getContext('2d');
    work = document.createElement('canvas'); work.width = W; work.height = H;
    film = draw;
  }
  function frame(t, n = 1, shutter = 0.5) {
    if (n <= 1) { screen(main); main.clearRect(0, 0, W, H); film(main, t); return; }
    const wctx = work.getContext('2d');
    for (let i = 0; i < n; i++) {
      const ts = t - shutter / FPS * (1 - (i + 0.5) / n);
      screen(wctx); wctx.clearRect(0, 0, W, H); wctx.filter = 'none'; wctx.globalAlpha = 1;
      film(wctx, ts);
      screen(main); main.globalAlpha = 1 / (i + 1); main.drawImage(work, 0, 0); main.globalAlpha = 1;
    }
  }

  window.E = { clamp, lerp, bezier, ease, P, tw, mix, alpha, parse, rand, camera, view, screen, toScreen,
    rrect, lerpRect, lift, resample, morphPts, poly, circlePts, rectPts, goo, flood,
    cursor, cursorPath, press, FONT, font, line, typed, counter, init, frame,
    get W() { return W; }, get H() { return H; } };
})();
