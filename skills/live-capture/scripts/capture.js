// Frame-exact capture of a live web page on a virtual clock.
// Every page timer, requestAnimationFrame and CSS animation advances exactly
// 1/60 s per captured frame, so scroll-linked and time-based animations play
// at a true 60 fps no matter how slow the screenshots are.
//
// Usage: node capture.js plan.json
// plan.json: {
//   "url": "https://example.com/", "out": "frames", "dpr": 1,
//   "hideText": ["example.com"],            // hide leaf elements containing this text (e.g. an unreleased URL)
//   "steps": [                              // run in order, one screenshot per frame
//     {"hold": 150},                        // stay still N frames (page load plays here)
//     {"scroll": 1300, "frames": 150},      // eased scroll to y
//     {"click": "[aria-label^='Pricing']"}, // element click (real mouse stays parked, no hover side effects)
//     {"clickText": "Get started"},         // click the button whose text matches
//     {"cursor": [744, 605], "frames": 60}  // move the logged virtual cursor (for a drawn cursor in the edit)
//   ]
// }
// Writes out/00000.jpg ... and out/log.json (scroll y, cursor, clicks per frame).
// Playwright: the project's own install, else PW_CORE (a playwright-core path).
const { chromium } = (() => {
  for (const id of ['playwright', process.env.PW_CORE]) {
    if (!id) continue;
    try { return require(id); } catch {}
  }
  throw new Error('playwright not found: npm i -D playwright, or set PW_CORE');
})();
const fs = require('fs');

const plan = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const DPR = plan.dpr || 1;
const FRAME_MS = 1000 / 60;
const REAL_MS = DPR > 1 ? 620 : 260; // real time per frame; CSS animations are slowed to match
const RATE = FRAME_MS / REAL_MS;
const OUT = plan.out || '03-brand/kit/footage/take';
fs.mkdirSync(OUT, { recursive: true });

const VT = `(() => {
  const rp = performance.now.bind(performance), rDate = Date.now;
  const vt = (window.__vt = { now: rp(), off: rDate() - rp(), cbs: [], timers: new Map(), id: 1 });
  performance.now = () => vt.now;
  Date.now = () => Math.round(vt.now + vt.off);
  window.requestAnimationFrame = (cb) => { const i = vt.id++; vt.cbs.push([i, cb]); return i; };
  window.cancelAnimationFrame = (i) => { vt.cbs = vt.cbs.filter((c) => c[0] !== i); };
  window.setTimeout = (fn, ms = 0, ...a) => { const i = vt.id++; vt.timers.set(i, { due: vt.now + (+ms || 0), fn, a, every: 0 }); return i; };
  window.setInterval = (fn, ms = 0, ...a) => { const i = vt.id++; vt.timers.set(i, { due: vt.now + Math.max(1, +ms || 0), fn, a, every: Math.max(1, +ms || 0) }); return i; };
  window.clearTimeout = window.clearInterval = (i) => { vt.timers.delete(i); };
  vt.step = (ms) => {
    const end = vt.now + ms;
    for (let guard = 0; guard < 500; guard++) {
      let next = null;
      for (const [i, t] of vt.timers) if (t.due <= end && (!next || t.due < next[1].due)) next = [i, t];
      if (!next) break;
      const [i, t] = next;
      vt.now = Math.max(vt.now, t.due);
      if (t.every) t.due += t.every; else vt.timers.delete(i);
      try { typeof t.fn === 'function' ? t.fn(...t.a) : eval(t.fn); } catch (e) {}
    }
    vt.now = end;
    const cbs = vt.cbs; vt.cbs = [];
    for (const [, cb] of cbs) { try { cb(vt.now); } catch (e) {} }
  };
})();`;

const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: DPR });
  await ctx.addInitScript(VT);
  const p = await ctx.newPage();
  const cdp = await ctx.newCDPSession(p);
  await cdp.send('Animation.enable');
  await cdp.send('Animation.setPlaybackRate', { playbackRate: RATE });
  await p.goto(plan.url, { waitUntil: 'load' });
  await cdp.send('Animation.setPlaybackRate', { playbackRate: RATE });

  const hide = plan.hideText || [];
  const log = { frames: [] };
  let f = 0, y = 0, cx = 1500, cy = 900;

  const shot = async (click) => {
    const t0 = Date.now();
    await p.evaluate((y) => window.scrollTo(0, y), y);
    await p.mouse.move(1919, 1079); // parked: no hover states leak into the capture
    if (click) {
      await p.evaluate((c) => {
        const el = c.sel ? document.querySelector(c.sel) : [...document.querySelectorAll('button,a,[role=button]')].find((e) => (e.innerText || e.textContent || '').trim() === c.text);
        if (!el) return;
        const r = el.getBoundingClientRect();
        const o = { bubbles: true, cancelable: true, clientX: r.x + r.width / 2, clientY: r.y + r.height / 2, view: window };
        for (const [T, n] of [[PointerEvent, 'pointerdown'], [MouseEvent, 'mousedown'], [PointerEvent, 'pointerup'], [MouseEvent, 'mouseup'], [MouseEvent, 'click']]) el.dispatchEvent(new T(n, o));
      }, click);
    }
    await p.waitForTimeout(12);
    await p.evaluate((ms) => window.__vt.step(ms), FRAME_MS);
    if (hide.length) {
      await p.evaluate((hide) => {
        for (const e of document.querySelectorAll('body *')) {
          if (e.childElementCount === 0 && hide.some((h) => (e.textContent || '').includes(h))) e.style.visibility = 'hidden';
        }
      }, hide);
    }
    await p.screenshot({ path: `${OUT}/${String(f).padStart(5, '0')}.jpg`, type: 'jpeg', quality: 92 });
    log.frames.push({ y, cx, cy, click: click ? click.sel || click.text : null });
    f++;
    const left = REAL_MS - (Date.now() - t0);
    if (left > 0) await p.waitForTimeout(left);
  };

  for (const s of plan.steps) {
    if (s.hold) for (let i = 0; i < s.hold; i++) await shot();
    else if (s.scroll !== undefined) {
      const y0 = y;
      for (let i = 1; i <= s.frames; i++) { y = Math.round(y0 + (s.scroll - y0) * ease(i / s.frames)); await shot(); }
    } else if (s.cursor) {
      const [x0, y0c] = [cx, cy];
      for (let i = 1; i <= s.frames; i++) { const e = ease(i / s.frames); cx = x0 + (s.cursor[0] - x0) * e; cy = y0c + (s.cursor[1] - y0c) * e; await shot(); }
    } else if (s.click) await shot({ sel: s.click });
    else if (s.clickText) await shot({ text: s.clickText });
  }
  fs.writeFileSync(`${OUT}/log.json`, JSON.stringify(log));
  await b.close();
})();
