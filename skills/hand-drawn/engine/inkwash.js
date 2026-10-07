// InkWash: a WebGL2 renderer for hand-drawn pictures made of fitted vector data (format: README.md, "Data format").
// Layers, bottom to top, all in linear light: toned paper with fitted grain, fibers, flecks and color mottling; a glaze
// (one pigment over a smooth strength field); watercolor wash regions with edge darkening, granulation, flow, backruns
// and soft wet-in-wet joins; ink: pencil strokes (width, pressure, graphite tooth, drawn on in fitted order), texture
// strokes, and residual ink as nested level shapes. Optional alpha: a cut-out silhouette, a straight soft alpha, or a
// field layer unmixed against a background texture. Every frame is a pure function of t. No image is loaded.
//
//   import { createInkWash } from './inkwash.js';
//   const ink = createInkWash(gl, drawing, { timing, look });   // drawing: parsed drawing.json
//   ink.draw(t);                  // frame at t into the bound framebuffer (or opts.target), drawing size
//   ink.tip(t)                    // { x, y, lift }: where the pencil is (see pencil.js)
//   ink.draw(t, { debug: 'ink' }) // fitting passes: 'ink', 'wash', 'paper', 'paperink', 'glaze', 'noWash'

const HEAD = '#version 300 es\nprecision highp float;\nprecision highp int;\n';

const NOISE = `
float h21(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float gnoise(vec2 p){
  vec2 i = floor(p), f = fract(p); vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  float a0 = 6.2831853 * h21(i), a1 = 6.2831853 * h21(i + vec2(1, 0)), a2 = 6.2831853 * h21(i + vec2(0, 1)), a3 = 6.2831853 * h21(i + vec2(1, 1));
  float a = dot(vec2(cos(a0), sin(a0)), f), b = dot(vec2(cos(a1), sin(a1)), f - vec2(1, 0));
  float c = dot(vec2(cos(a2), sin(a2)), f - vec2(0, 1)), d = dot(vec2(cos(a3), sin(a3)), f - vec2(1, 1));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y) * 1.41;
}
float fbm(vec2 p){ float s = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { s += a * gnoise(p); p = p * 2.03 + vec2(17.1, 9.7); a *= 0.5; } return s; }
uniform float u_pa[7]; uniform float u_fiber; uniform float u_fleck; uniform vec2 u_off;
// paper height: seven fitted octaves (frequencies and offsets shared with fit/paper.py), fibers, flecks
float paperH(vec2 x){
  x += u_off;
  float s = u_pa[0] * gnoise(x * 0.62 + vec2(3.1, 7.7)) + u_pa[1] * gnoise(x * 0.31 + vec2(11.3, 1.9))
          + u_pa[2] * gnoise(x * 0.155 + vec2(5.5, 21.1)) + u_pa[3] * gnoise(x * 0.078 + vec2(31.0, 2.2))
          + u_pa[4] * gnoise(x * 0.039 + vec2(8.8, 13.3)) + u_pa[5] * gnoise(x * 0.0195 + vec2(41.0, 4.4))
          + u_pa[6] * gnoise(x * 0.0098 + vec2(2.7, 55.5));
  vec2 r1 = mat2(0.94, 0.34, -0.34, 0.94) * x, r2 = mat2(0.80, -0.60, 0.60, 0.80) * x;
  s -= u_fiber * (smoothstep(0.55, 0.8, abs(gnoise(vec2(r1.x * 0.012, r1.y * 0.55) + 3.0)))
                + smoothstep(0.55, 0.8, abs(gnoise(vec2(r2.x * 0.012, r2.y * 0.55) + 9.0))));
  s -= u_fleck * smoothstep(0.32, 0.55, 0.6 * gnoise(x * 0.33 + vec2(71.0, 3.0)) + 0.4 * gnoise(x * 0.9 + vec2(5.0, 91.0)));
  return s;
}
uniform float u_chroma;
vec3 paperC(vec2 x){
  x += u_off;
  float a = gnoise(x * 0.16 + vec2(13.0, 37.0)) + 0.5 * gnoise(x * 0.05 + vec2(3.0, 8.0));
  float b = gnoise(x * 0.16 + vec2(61.0, 17.0)) + 0.5 * gnoise(x * 0.05 + vec2(29.0, 44.0));
  return vec3(1.0) + u_chroma * vec3(a, -0.4 * a + 0.3 * b, -b);
}
`;

const PX = `uniform vec2 u_size;
vec4 clip(vec2 p){ return vec4(p.x / u_size.x * 2.0 - 1.0, 1.0 - p.y / u_size.y * 2.0, 0.0, 1.0); }
`;

const VS_STROKE = HEAD + PX + `
in vec2 a_p; in vec2 a_n; in float a_side; in float a_hw; in float a_s; in float a_pr; in vec2 a_t; in vec3 a_c;
out float v_x; out float v_hw; out float v_s; out float v_pr; out vec3 v_c; out vec2 v_q; out float v_prog;
uniform float u_time;
void main(){
  float w = a_hw + 1.0;
  vec2 p = a_p + a_n * a_side * w;
  v_x = a_side * w; v_hw = a_hw; v_s = a_s; v_pr = a_pr; v_c = a_c; v_q = p;
  v_prog = clamp((u_time - a_t.x) / max(a_t.y - a_t.x, 1e-4), 0.0, 1.0);
  gl_Position = u_time < a_t.x ? vec4(2.0, 2.0, 2.0, 1.0) : clip(p);
}`;

const FS_STROKE = HEAD + NOISE + `
in float v_x; in float v_hw; in float v_s; in float v_pr; in vec3 v_c; in vec2 v_q; in float v_prog;
uniform float u_gain; uniform float u_tooth; uniform float u_toothK; uniform int u_mode;
out vec4 o;
void main(){
  if (v_s > v_prog) discard;
  float d = abs(v_x);
  float cov = clamp(v_hw + 0.5 - d, 0.0, 1.0);
  float prof = 1.0 - 0.2 * d / (v_hw + 1.0);
  float tooth = clamp(0.5 + paperH(v_q) * u_toothK, 0.0, 1.0);
  float dep = 1.0 + u_tooth * 2.0 * (tooth - 0.5);                       // graphite catches the paper's peaks, mean 1
  if (u_mode == 1) {                                                     // texture strokes: crisp core, tooth at the edges
    float e = d / (v_hw + 0.5);
    prof = 1.0; cov = clamp((v_hw + 0.5 - d) * 1.6, 0.0, 1.0);
    dep = 1.0 + u_tooth * 2.0 * (tooth - 0.5) * smoothstep(0.35, 1.0, e);
  }
  float a = clamp(v_pr * u_gain * prof * dep, 0.0, 1.0) * cov;
  o = vec4(vec3(1.0) - a * (vec3(1.0) - v_c), 1.0);                     // transmittance, MIN-blended
}`;

const VS_POLY = HEAD + PX + `in vec2 a_p; void main(){ gl_Position = clip(a_p); }`;
const FS_ONE = HEAD + `out vec4 o; void main(){ o = vec4(1.0); }`;
const VS_RECT = HEAD + PX + `uniform vec4 u_rect; out vec2 v_q;
void main(){ vec2 c = vec2(gl_VertexID & 1, (gl_VertexID >> 1) & 1); v_q = u_rect.xy + c * u_rect.zw; gl_Position = clip(v_q); }`;
const VS_FULL = HEAD + `out vec2 v_uv;
void main(){ vec2 c = vec2(gl_VertexID & 1, (gl_VertexID >> 1) & 1); v_uv = c; gl_Position = vec4(c * 2.0 - 1.0, 0.0, 1.0); }`;

// residual ink level: a flat transmittance laid in as a quick scribble (noise decides which pixels it has reached)
const FS_LEVEL = HEAD + NOISE + `in vec2 v_q; uniform vec3 u_col; uniform vec2 u_tt; uniform float u_time; out vec4 o;
void main(){
  float al = clamp((u_time - u_tt.x) / max(u_tt.y - u_tt.x, 1e-4), 0.0, 1.0);
  float reach = 0.5 + 0.5 * gnoise(v_q * 0.35);
  al = al >= 1.0 ? 1.0 : al * smoothstep(reach - 0.15, reach + 0.15, al * 1.3);
  o = vec4(mix(vec3(1.0), u_col, al), 1.0);
}`;

// wash region: quadratic pigment transmittance in region coordinates
const FS_WASH = HEAD + `in vec2 v_q; uniform vec3 u_c; uniform vec3 u_k[6]; uniform float u_amax; out vec4 o;
void main(){
  vec2 uv = (v_q - u_c.xy) / u_c.z;
  vec3 A = u_k[0] + u_k[1] * uv.x + u_k[2] * uv.y + u_k[3] * uv.x * uv.x + u_k[4] * uv.x * uv.y + u_k[5] * uv.y * uv.y;
  o = vec4(clamp(A, 0.05, u_amax), 1.0);
}`;
// straight alpha region: quadratic alpha surface, never below the floor
const FS_AREG = HEAD + `in vec2 v_q; uniform vec3 u_c; uniform float u_k[6]; uniform float u_floor; out vec4 o;
void main(){
  vec2 uv = (v_q - u_c.xy) / u_c.z;
  float a = u_k[0] + u_k[1] * uv.x + u_k[2] * uv.y + u_k[3] * uv.x * uv.x + u_k[4] * uv.x * uv.y + u_k[5] * uv.y * uv.y;
  o = vec4(clamp(max(a, u_floor), 0.0, 1.0));
}`;
const FS_FLAT = HEAD + `uniform vec4 u_col; out vec4 o; void main(){ o = u_col; }`;

const FS_BLUR = HEAD + `in vec2 v_uv; uniform sampler2D u_tex; uniform vec2 u_dir; uniform float u_sigma; out vec4 o;
void main(){ vec4 s = vec4(0.0); float ws = 0.0;
  for (int i = -12; i <= 12; i++) { float w = exp(-float(i * i) / (2.0 * u_sigma * u_sigma)); s += w * texture(u_tex, v_uv + u_dir * float(i)); ws += w; }
  o = s / ws; }`;

const FS_COMP = HEAD + NOISE + `in vec2 v_uv;
uniform sampler2D u_wash, u_washB, u_ink, u_mask, u_bg;
uniform vec2 u_size; uniform float u_time; uniform int u_dbg; uniform int u_amode;
uniform vec3 u_tone; uniform vec3 u_tint;
uniform vec3 u_gpig; uniform float u_gbase; uniform float u_gsig; uniform vec3 u_gc[64]; uniform int u_gn;
uniform vec4 u_wbloom; uniform vec4 u_gbloom; uniform float u_maxd;
uniform float u_edge, u_gran, u_flow, u_back, u_wob, u_grK, u_vig; uniform vec2 u_soft; uniform vec3 u_inkF; uniform vec4 u_bgRect;
out vec4 o;
vec3 enc(vec3 c){ c = clamp(c, 0.0, 1.0); return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c)); }
float reveal(vec2 x, vec4 b, float k){   // wet front from a seed: arrival time grows with distance, broken by flow noise
  float dn = length(x - b.xy) / u_maxd;
  float tr = b.z + b.w * (0.78 * dn + 0.22 * (0.5 + 0.5 * fbm(x * 0.006 + k)));
  return smoothstep(0.0, 0.32, u_time - tr);
}
void main(){
  // textures drawn by this renderer hold the drawing upright in clip space: texel row 0 is the drawing's bottom row
  vec2 tuv = v_uv;
  vec2 x = vec2(v_uv.x, 1.0 - v_uv.y) * u_size;           // drawing px, y down
  float ph = paperH(x);
  vec3 paper = u_tone * (vec3(1.0) + u_tint * ph) * paperC(x);
  // glaze: one pigment over a smooth strength field
  float g = u_gbase;
  for (int i = 0; i < 64; i++) { if (i >= u_gn) break; vec2 d = x - u_gc[i].xy; g += u_gc[i].z * exp(-dot(d, d) / (2.0 * u_gsig * u_gsig)); }
  g = clamp(g, 0.0, 1.0) * reveal(x, u_gbloom, 9.0);
  vec3 G = vec3(1.0) - g * (vec3(1.0) - u_gpig);
  // washes, sampled through a small flow displacement so edges wander like wet paint
  vec2 wob = vec2(fbm(x * 0.045 + 1.3), fbm(x * 0.045 + 7.9)) * u_wob;
  vec2 wuv = vec2((x.x + wob.x) / u_size.x, 1.0 - (x.y + wob.y) / u_size.y);
  vec3 Wc = texture(u_wash, wuv).rgb, Wb = texture(u_washB, wuv).rgb;
  vec3 C = mix(Wb, Wc, smoothstep(u_soft.x, u_soft.y, length(Wc - Wb)));   // weak steps melt, strong steps stay hard
  float lc = dot(C, vec3(0.2126, 0.7152, 0.0722)), lb = dot(Wb, vec3(0.2126, 0.7152, 0.0722));
  float pig = clamp(1.0 - lc, 0.0, 1.0);
  float dens = 1.0 + u_edge * max(0.0, lb - lc) * 6.0;                         // edge darkening
  dens += u_gran * (0.5 - clamp(0.5 + ph * u_grK, 0.0, 1.0)) * smoothstep(0.02, 0.3, pig);   // granulation in valleys
  dens += u_flow * fbm(x * 0.008 + 2.0) * smoothstep(0.02, 0.2, pig);
  float br = fbm(x * 0.011 + 31.0);
  dens += u_back * (smoothstep(0.035, 0.0, abs(br - 0.18)) - 0.35 * smoothstep(0.18, 0.3, br)) * smoothstep(0.05, 0.25, pig);   // backruns
  vec3 Cd = clamp(C - (C - C * C) * (dens - 1.0), 0.0, 1.6);
  Cd = mix(vec3(1.0), Cd, reveal(x, u_wbloom, 4.0));
  vec3 ink = texture(u_ink, tuv).rgb;
  vec3 col = paper * G * Cd * ink;
  if (u_dbg == 1) col = ink; else if (u_dbg == 2) col = Cd; else if (u_dbg == 3) col = paper;
  else if (u_dbg == 4) col = paper * ink; else if (u_dbg == 5) col = G; else if (u_dbg == 6) col = paper * G * ink;
  vec2 vq = tuv * 2.0 - 1.0;                                             // optional vignette (look.vignette, default 0)
  col *= 1.0 - u_vig * smoothstep(0.55, 1.45, length(vq * vec2(1.0, 0.8)));
  vec3 c = enc(col);
  if (u_dbg == 0) c += (h21(gl_FragCoord.xy) - 0.5) / 255.0;          // dither against banding
  float m = 1.0;
  if (u_amode == 1 || u_amode == 2) m = texture(u_mask, tuv).r;
  if (u_amode == 3) {                                                     // field: unmix against the background
    vec2 bq = (u_bgRect.xy + x) / u_bgRect.zw;
    vec3 bg = texture(u_bg, vec2(bq.x, 1.0 - bq.y)).rgb;               // same convention: texel row 0 = bottom
    vec3 dk = u_inkF - bg;
    float al = max(clamp(dot(c - bg, dk) / max(dot(dk, dk), 1e-4), 0.0, 1.0), 0.04) * texture(u_mask, tuv).r;
    o = vec4(clamp(c - bg * (1.0 - al), 0.0, al), al); return;
  }
  o = vec4(clamp(c, 0.0, 1.0) * m, m);                                   // premultiplied
}`;

function rng(seed) {
  let s = (seed >>> 0) || 1;
  return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
}

function compile(gl, vs, fs) {
  const sh = (type, src) => {
    const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  };
  const p = gl.createProgram();
  gl.attachShader(p, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  const U = {}; const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < n; i++) { const nm = gl.getActiveUniform(p, i).name; U[nm.replace(/\[0\]$/, '')] = gl.getUniformLocation(p, nm); }
  return { p, U, a: (name) => gl.getAttribLocation(p, name) };
}

function target(gl, W, H, fmt, stencil) {
  const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex);
  if (fmt === 'f16') gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, W, H, 0, gl.RGBA, gl.HALF_FLOAT, null);
  else gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, W, H, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
  for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
  const fb = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
  let rb = null;
  if (stencil) {
    rb = gl.createRenderbuffer(); gl.bindRenderbuffer(gl.RENDERBUFFER, rb);
    gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH24_STENCIL8, W, H);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_STENCIL_ATTACHMENT, gl.RENDERBUFFER, rb);
  }
  return { tex, fb, rb, w: W, h: H };
}

// ---------- draw-on schedule: strokes in fitted order, duration from length, a short travel between strokes
export function makeSchedule(strokes, window, travelPx = 12) {
  const [a, b] = window;
  let total = 0; for (let i = 0; i < strokes.length; i++) total += strokes[i].L + (i ? travelPx : 0);
  const k = (b - a) / (total || 1); let t = a;
  return strokes.map((s, i) => { if (i) t += travelPx * k; const t0 = t; t += s.L * k; return { t0, t1: t }; });
}

// hatch field -> fresh hatch strokes (seeded), for drawings fitted with regenerated hatching
export function regenerateHatch(hatch, seed = 11, look = {}) {
  if (!hatch || !hatch.cells || !hatch.cells.length) return [];
  const R = rng(seed), C = hatch.cell, out = [];
  for (const [cy, cx, ang, total, mean, press, r, g, b, w] of hatch.cells) {
    let budget = total * (look.hatchDensity ?? 1.0);
    while (budget > 0) {
      const l = mean * (0.8 + 0.4 * R());
      if (budget < l && R() > budget / l) break;
      budget -= l;
      const a = ang + (R() - 0.5) * 0.1, dx = Math.cos(a), dy = Math.sin(a);
      const x = (cx + R()) * C, y = (cy + R()) * C, bow = (R() - 0.5) * 0.05 * l, n = Math.max(2, Math.round(l / 2.5) + 1);
      const p = new Float32Array(n * 4), pr = press * (0.85 + 0.3 * R());
      for (let i = 0; i < n; i++) { const u = i / (n - 1) - 0.5, bw = bow * (1 - 4 * u * u); p.set([x + dx * l * u - dy * bw, y + dy * l * u + dx * bw, w || 2.0, pr], 4 * i); }
      out.push({ p, col: [r, g, b], L: l, cls: 4 });
    }
  }
  return out.sort((s, t) => s.p[0] - t.p[0]);
}

export function createInkWash(gl, D, opts = {}) {
  gl.getExtension('EXT_color_buffer_float'); gl.getExtension('EXT_float_blend');
  const [W, H] = D.size;
  const off = opts.offset || [0, 0];
  const look = Object.assign({ lineGain: 1.0, tooth: 0.25, edge: 0.15, gran: 0.4, flow: 0.06, back: 0.05, wob: 0.8, soft0: 0.02, soft1: 0.08, amax: 1.6 },
    D.look || {}, opts.look || {});
  const T = Object.assign({ lines: [0.3, 2.6], hatchStrokes: null, texture: null, hatch: null, residual: null, wash: [3.0, 1.2], glaze: null, travel: 12 }, opts.timing || {});
  const paper = D.paper;
  const pa = paper.amps, paStd = Math.max(1e-4, Math.sqrt(pa.reduce((a, b) => a + b * b, 0)) * 0.45);

  const P = {
    stroke: compile(gl, VS_STROKE, FS_STROKE), poly: compile(gl, VS_POLY, FS_ONE), level: compile(gl, VS_RECT, FS_LEVEL),
    wash: compile(gl, VS_RECT, FS_WASH), areg: compile(gl, VS_RECT, FS_AREG), flat: compile(gl, VS_RECT, FS_FLAT),
    blur: compile(gl, VS_FULL, FS_BLUR), comp: compile(gl, VS_FULL, FS_COMP),
  };
  const ink = target(gl, W, H, 'f16', true);
  const wash = target(gl, W, H, 'f16', true);
  const washB1 = target(gl, Math.ceil(W / 2), Math.ceil(H / 2), 'f16', false), washB2 = target(gl, Math.ceil(W / 2), Math.ceil(H / 2), 'f16', false);
  const evao = gl.createVertexArray();

  // ---- strokes: fitted lines in order, then regenerated hatching (if any), texture strokes drawn in their own pass
  const lines = [], tex = [];
  for (const s of D.strokes || []) {
    const p = s.p instanceof Float32Array ? s.p : new Float32Array(s.p); let L = 0;
    for (let i = 4; i < p.length; i += 4) L += Math.hypot(p[i] - p[i - 4], p[i + 1] - p[i - 3]);
    (s.c === 5 ? tex : lines).push({ p, col: s.t, L, cls: s.c });
  }
  const hatches = regenerateHatch(D.hatch, opts.seed ?? 11, look);
  const hatchWin = T.hatch || [T.lines[1], T.lines[1] + 0.4];
  const texWin = T.texture || T.lines;
  // optional: traced hatching (class 4) builds up in its own window after the structure is drawn
  const struct = T.hatchStrokes ? lines.filter(s => s.cls !== 4) : lines, hstr = T.hatchStrokes ? lines.filter(s => s.cls === 4) : [];
  const sched = makeSchedule(struct, T.lines, T.travel).concat(makeSchedule(hstr, T.hatchStrokes || [0, 0], T.travel * 0.25),
    makeSchedule(hatches, hatchWin, T.travel * 0.3), makeSchedule(tex, texWin, 0));
  const all = struct.concat(hstr, hatches, tex);
  const nTexFrom = lines.length + hatches.length;
  let nv = 0, ni = 0; for (const s of all) { const n = s.p.length / 4; nv += 2 * n; ni += 6 * Math.max(0, n - 1); }
  const FL = 14, V = new Float32Array(nv * FL), I = new Uint32Array(ni);
  let v = 0, ii = 0, texIdx = -1;
  all.forEach((s, k) => {
    if (k === nTexFrom) texIdx = ii;
    const p = s.p, n = p.length / 4, { t0, t1 } = sched[k], base = v; let acc = 0;
    for (let i = 0; i < n; i++) {
      const j0 = Math.max(0, i - 1), j1 = Math.min(n - 1, i + 1);
      let tx = p[4 * j1] - p[4 * j0], ty = p[4 * j1 + 1] - p[4 * j0 + 1]; const tl = Math.hypot(tx, ty) || 1; tx /= tl; ty /= tl;
      if (i) acc += Math.hypot(p[4 * i] - p[4 * i - 4], p[4 * i + 1] - p[4 * i - 3]);
      for (const side of [-1, 1]) { V.set([p[4 * i], p[4 * i + 1], -ty, tx, side, 0.5 * p[4 * i + 2], s.L > 0 ? acc / s.L : 0, p[4 * i + 3], t0, t1, s.col[0], s.col[1], s.col[2], 0], v * FL); v++; }
      if (i < n - 1) { const q = base + 2 * i; I.set([q, q + 1, q + 2, q + 1, q + 3, q + 2], ii); ii += 6; }
    }
  });
  if (texIdx < 0) texIdx = ii;
  const svao = gl.createVertexArray(); gl.bindVertexArray(svao);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer()); gl.bufferData(gl.ARRAY_BUFFER, V, gl.STATIC_DRAW);
  const att = (name, size, o) => { const l = P.stroke.a(name); if (l < 0) return; gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, size, gl.FLOAT, false, FL * 4, o * 4); };
  att('a_p', 2, 0); att('a_n', 2, 2); att('a_side', 1, 4); att('a_hw', 1, 5); att('a_s', 1, 6); att('a_pr', 1, 7); att('a_t', 2, 8); att('a_c', 3, 10);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, gl.createBuffer()); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, I, gl.STATIC_DRAW);
  gl.bindVertexArray(null);

  // ---- polygons: every ring set (residual levels, wash regions, alpha) in one buffer, drawn as fans into the stencil
  const polyData = [];
  const ringsOf = (rings) => rings.map(r => { const o = polyData.length / 2; for (const q of r) polyData.push(q); return [o, r.length / 2]; });
  const bbox = (rings) => { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (const r of rings) for (let i = 0; i < r.length; i += 2) { x0 = Math.min(x0, r[i]); x1 = Math.max(x1, r[i]); y0 = Math.min(y0, r[i + 1]); y1 = Math.max(y1, r[i + 1]); }
    return [x0 - 1, y0 - 1, x1 - x0 + 2, y1 - y0 + 2]; };
  const lvl = ((D.residual && D.residual.levels) || []).filter(l => l.rings.length);
  const levels = lvl.map((l, i) => {
    const win = T.residual || [T.lines[0] + 0.5 * (T.lines[1] - T.lines[0]), T.lines[1]];
    const u = lvl.length > 1 ? i / (lvl.length - 1) : 0, d = (win[1] - win[0]) * 0.5;
    return { col: l.t, fans: ringsOf(l.rings), rect: bbox(l.rings), tt: [win[0] + u * d, win[0] + u * d + d] };
  });
  const regions = ((D.wash && D.wash.regions) || []).map(R => ({ R, fans: ringsOf(R.rings), rect: R.bb ? [R.bb[0] - 1, R.bb[1] - 1, R.bb[2] - R.bb[0] + 2, R.bb[3] - R.bb[1] + 2] : bbox(R.rings), k: new Float32Array(R.k.flat()) }));
  const AL = D.alpha || { mode: 'opaque' };
  const amode = { opaque: 0, mask: 1, straight: 2, field: 3 }[AL.mode] || 0;
  const silFans = AL.rings ? ringsOf(AL.rings) : [];
  const aregs = AL.mode === 'straight' ? (AL.regions || []).map(r => ({ r, fans: ringsOf(r.rings), rect: [r.bb[0] - 1, r.bb[1] - 1, r.bb[2] - r.bb[0] + 2, r.bb[3] - r.bb[1] + 2] })) : [];
  const pvao = gl.createVertexArray(); gl.bindVertexArray(pvao);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer()); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(polyData.length ? polyData : [0, 0]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(P.poly.a('a_p')); gl.vertexAttribPointer(P.poly.a('a_p'), 2, gl.FLOAT, false, 0, 0);
  gl.bindVertexArray(null);

  // stencil fill: even-odd of the fans into stencil bit `bit`, then one rect through `prog` where the stencil equals
  // `test` (default: the bit); the bit is reset on the way
  function stencilFill(fans, rect, prog, setU, bit = 1, test = null) {
    gl.enable(gl.STENCIL_TEST);
    gl.colorMask(false, false, false, false); gl.stencilMask(bit);
    gl.stencilFunc(gl.ALWAYS, 0, 0xff); gl.stencilOp(gl.KEEP, gl.KEEP, gl.INVERT);
    gl.useProgram(P.poly.p); gl.uniform2f(P.poly.U.u_size, W, H); gl.bindVertexArray(pvao);
    for (const [o, n] of fans) gl.drawArrays(gl.TRIANGLE_FAN, o, n);
    gl.colorMask(true, true, true, true);
    const tv = test ?? bit;
    gl.stencilFunc(gl.EQUAL, tv, tv); gl.stencilOp(gl.ZERO, gl.ZERO, gl.ZERO);
    gl.useProgram(prog.p); gl.uniform2f(prog.U.u_size, W, H); gl.uniform4f(prog.U.u_rect, ...rect);
    if (setU) setU(prog.U);
    gl.bindVertexArray(evao); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.stencilMask(0xff); gl.disable(gl.STENCIL_TEST);
  }
  function blur(src, dst, mid, sigma, step) {
    gl.disable(gl.BLEND);
    gl.useProgram(P.blur.p); gl.uniform1i(P.blur.U.u_tex, 0); gl.uniform1f(P.blur.U.u_sigma, sigma / step); gl.activeTexture(gl.TEXTURE0);
    gl.bindVertexArray(evao); gl.viewport(0, 0, dst.w, dst.h);
    gl.bindFramebuffer(gl.FRAMEBUFFER, mid.fb); gl.bindTexture(gl.TEXTURE_2D, src.tex); gl.uniform2f(P.blur.U.u_dir, step / src.w, 0); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.bindFramebuffer(gl.FRAMEBUFFER, dst.fb); gl.bindTexture(gl.TEXTURE_2D, mid.tex); gl.uniform2f(P.blur.U.u_dir, 0, step / src.h); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.bindTexture(gl.TEXTURE_2D, null);
  }

  // ---- washes and alpha do not depend on t: drawn once (the bloom is a reveal in the composite)
  gl.disable(gl.BLEND); gl.disable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE);
  gl.bindFramebuffer(gl.FRAMEBUFFER, wash.fb); gl.viewport(0, 0, W, H);
  gl.clearColor(1, 1, 1, 1); gl.clearStencil(0); gl.clear(gl.COLOR_BUFFER_BIT | gl.STENCIL_BUFFER_BIT);
  for (const g of regions) stencilFill(g.fans, g.rect, P.wash, (U) => { gl.uniform3fv(U.u_c, g.R.c); gl.uniform3fv(U.u_k, g.k); gl.uniform1f(U.u_amax, look.amax); });
  blur(wash, washB2, washB1, 6.0, 2.0);
  let mask = null;
  if (amode) {
    mask = target(gl, W, H, 'u8', true); const m2 = target(gl, W, H, 'u8', false);
    gl.bindFramebuffer(gl.FRAMEBUFFER, mask.fb); gl.viewport(0, 0, W, H);
    gl.clearColor(0, 0, 0, 0); gl.clearStencil(0); gl.clear(gl.COLOR_BUFFER_BIT | gl.STENCIL_BUFFER_BIT);
    const fl = AL.mode === 'straight' ? (AL.floor || 0) : 1;
    stencilFill(silFans, [0, 0, W, H], P.flat, (U) => gl.uniform4f(U.u_col, fl, fl, fl, fl));
    if (aregs.length) {
      // regions write their alpha surface inside the silhouette only: silhouette in stencil bit 2, each region in bit 1
      gl.enable(gl.STENCIL_TEST); gl.colorMask(false, false, false, false); gl.stencilMask(2);
      gl.stencilFunc(gl.ALWAYS, 0, 0xff); gl.stencilOp(gl.KEEP, gl.KEEP, gl.INVERT);
      gl.useProgram(P.poly.p); gl.uniform2f(P.poly.U.u_size, W, H); gl.bindVertexArray(pvao);
      for (const [o, n] of silFans) gl.drawArrays(gl.TRIANGLE_FAN, o, n);
      gl.colorMask(true, true, true, true); gl.stencilMask(0xff); gl.disable(gl.STENCIL_TEST);
      for (const a of aregs) stencilFill(a.fans, a.rect, P.areg, (U) => { gl.uniform3fv(U.u_c, a.r.c); gl.uniform1fv(U.u_k, a.r.p); gl.uniform1f(U.u_floor, AL.floor || 0); }, 1, 3);
    }
    if ((AL.feather || 0) > 0.25) blur(mask, mask, m2, AL.feather, 1.0);
    gl.deleteTexture(m2.tex); gl.deleteFramebuffer(m2.fb);
  }

  // ---- glaze and bloom
  const gz = (D.wash && D.wash.glaze) || { pigment: [1, 1, 1], base: 0, sigma: 200, centers: [] };
  const gc = new Float32Array(64 * 3); gz.centers.slice(0, 64).forEach((c, i) => gc.set(c, 3 * i));
  const maxd = Math.hypot(W, H);
  const wseed = T.washSeed || D.washSeed || [W * 0.5, H * 0.4];
  const gwin = T.glaze || [T.wash[0] + T.wash[1] * 0.6, T.wash[1]];

  function draw(t, o = {}) {
    const dbg = { ink: 1, wash: 2, paper: 3, paperink: 4, glaze: 5, noWash: 6 }[o.debug] || 0;
    const outFb = o.target !== undefined ? o.target : (opts.target ?? null);
    // ink: strokes (MIN), texture strokes (MIN), then residual levels (multiply)
    gl.bindFramebuffer(gl.FRAMEBUFFER, ink.fb); gl.viewport(0, 0, W, H);
    gl.clearColor(1, 1, 1, 1); gl.clearStencil(0); gl.clear(gl.COLOR_BUFFER_BIT | gl.STENCIL_BUFFER_BIT);
    if (dbg !== 2 && dbg !== 3 && dbg !== 5) {
      gl.enable(gl.BLEND); gl.blendEquation(gl.MIN);
      const S = P.stroke, U = S.U; gl.useProgram(S.p);
      gl.uniform2f(U.u_size, W, H); gl.uniform1f(U.u_time, t); gl.uniform1f(U.u_gain, look.lineGain);
      gl.uniform1fv(U.u_pa, pa); gl.uniform1f(U.u_fiber, paper.fiber || 0); gl.uniform1f(U.u_fleck, paper.fleck || 0); gl.uniform2f(U.u_off, off[0], off[1]);
      gl.uniform1f(U.u_toothK, 0.3 / paStd);
      gl.bindVertexArray(svao);
      if (texIdx > 0) { gl.uniform1i(U.u_mode, 0); gl.uniform1f(U.u_tooth, look.tooth); gl.drawElements(gl.TRIANGLES, texIdx, gl.UNSIGNED_INT, 0); }
      if (ii > texIdx) { gl.uniform1i(U.u_mode, 1); gl.uniform1f(U.u_tooth, look.texTooth ?? 0.6); gl.drawElements(gl.TRIANGLES, ii - texIdx, gl.UNSIGNED_INT, texIdx * 4); }
      gl.blendEquation(gl.FUNC_ADD); gl.blendFunc(gl.DST_COLOR, gl.ZERO);
      for (const L of levels) {
        if (t < L.tt[0]) continue;
        stencilFill(L.fans, L.rect, P.level, (LU) => { gl.uniform3fv(LU.u_col, L.col); gl.uniform2fv(LU.u_tt, L.tt); gl.uniform1f(LU.u_time, t); });
      }
      gl.disable(gl.BLEND);
    }
    // composite
    gl.bindFramebuffer(gl.FRAMEBUFFER, outFb); gl.viewport(0, 0, W, H);
    const C = P.comp, U = C.U; gl.useProgram(C.p);
    const texs = [[wash.tex, 'u_wash'], [washB2.tex, 'u_washB'], [ink.tex, 'u_ink'], [mask ? mask.tex : ink.tex, 'u_mask'], [opts.bg ? opts.bg.tex : ink.tex, 'u_bg']];
    texs.forEach(([tx, nm], i) => { gl.activeTexture(gl.TEXTURE0 + i); gl.bindTexture(gl.TEXTURE_2D, tx); gl.uniform1i(U[nm], i); });
    gl.uniform2f(U.u_size, W, H); gl.uniform1f(U.u_time, o.debug ? 1e6 : t); gl.uniform1i(U.u_dbg, dbg);
    gl.uniform1i(U.u_amode, o.debug ? 0 : amode);
    gl.uniform3fv(U.u_tone, paper.tone); gl.uniform3fv(U.u_tint, paper.tint || [1, 1, 1]);
    gl.uniform1fv(U.u_pa, pa); gl.uniform1f(U.u_fiber, paper.fiber || 0); gl.uniform1f(U.u_fleck, paper.fleck || 0);
    gl.uniform1f(U.u_chroma, paper.chroma || 0); gl.uniform2f(U.u_off, off[0], off[1]);
    gl.uniform3fv(U.u_gpig, gz.pigment); gl.uniform1f(U.u_gbase, gz.base); gl.uniform1f(U.u_gsig, gz.sigma); gl.uniform3fv(U.u_gc, gc); gl.uniform1i(U.u_gn, Math.min(64, gz.centers.length));
    gl.uniform4f(U.u_wbloom, wseed[0], wseed[1], T.wash[0], T.wash[1]); gl.uniform4f(U.u_gbloom, wseed[0], wseed[1], gwin[0], gwin[1]); gl.uniform1f(U.u_maxd, maxd);
    const fx = o.debug ? 0 : 1;   // fitting passes see the plain washes
    gl.uniform1f(U.u_edge, look.edge * fx); gl.uniform1f(U.u_gran, look.gran * fx); gl.uniform1f(U.u_flow, look.flow * fx); gl.uniform1f(U.u_back, look.back * fx);
    gl.uniform1f(U.u_wob, look.wob * fx); gl.uniform1f(U.u_vig, (look.vignette || 0) * fx); gl.uniform1f(U.u_grK, 0.3 / paStd); gl.uniform2f(U.u_soft, fx ? look.soft0 : -1, fx ? look.soft1 : -0.5);
    if (amode === 3 && !o.debug) {
      const bg = opts.bg; if (!bg) throw new Error('field alpha needs opts.bg: { tex, x, y, w, h } (the background drawn by code)');
      gl.uniform4f(U.u_bgRect, off[0] - (bg.x || 0), off[1] - (bg.y || 0), bg.w, bg.h); gl.uniform3fv(U.u_inkF, AL.ink);
    }
    gl.disable(gl.BLEND);
    gl.bindVertexArray(evao); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    for (let i = 4; i >= 0; i--) { gl.activeTexture(gl.TEXTURE0 + i); gl.bindTexture(gl.TEXTURE_2D, null); }
    gl.bindVertexArray(null);
  }

  // ---- pencil tip: on the stroke being drawn, gliding between strokes, resting before and after
  const rest = opts.rest || [W * 0.86, H * 0.82];
  const order = all.map((s, k) => k).sort((a, b) => sched[a].t0 - sched[b].t0);
  function at(s, u) { const p = s.p, n = p.length / 4, tg = u * s.L; let acc = 0;
    for (let i = 1; i < n; i++) { const l = Math.hypot(p[4 * i] - p[4 * i - 4], p[4 * i + 1] - p[4 * i - 3]);
      if (acc + l >= tg) { const f = l ? (tg - acc) / l : 0; return [p[4 * i - 4] + f * (p[4 * i] - p[4 * i - 4]), p[4 * i - 3] + f * (p[4 * i + 1] - p[4 * i - 3])]; } acc += l; }
    return [p[4 * n - 4], p[4 * n - 3]]; }
  const ease = u => u * u * (3 - 2 * u);
  function tip(t) {
    if (!order.length) return { x: rest[0], y: rest[1], lift: 1 };
    const first = order[0], last = order[order.length - 1];
    if (t < sched[first].t0) { const u = ease(Math.max(0, Math.min(1, (t - (sched[first].t0 - 0.6)) / 0.6))); const s = at(all[first], 0);
      return { x: rest[0] + (s[0] - rest[0]) * u, y: rest[1] + (s[1] - rest[1]) * u, lift: 1 - u }; }
    if (t >= sched[last].t1) { const u = ease(Math.max(0, Math.min(1, (t - sched[last].t1) / 0.6))); const e = at(all[last], 1);
      return { x: e[0] + (rest[0] - e[0]) * u, y: e[1] + (rest[1] - e[1]) * u, lift: u }; }
    let lo = 0, hi = order.length - 1;                       // last stroke that started by t
    while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (sched[order[mid]].t0 <= t) lo = mid; else hi = mid - 1; }
    const k = order[lo], s = sched[k];
    if (t < s.t1 || lo === order.length - 1) { const q = at(all[k], Math.min(1, (t - s.t0) / Math.max(s.t1 - s.t0, 1e-6))); return { x: q[0], y: q[1], lift: 0 }; }
    const nx = order[lo + 1]; const a = at(all[k], 1), b = at(all[nx], 0);
    const u = ease(Math.min(1, (t - s.t1) / Math.max(sched[nx].t0 - s.t1, 1e-4)));
    return { x: a[0] + (b[0] - a[0]) * u, y: a[1] + (b[1] - a[1]) * u, lift: Math.min(1, Math.hypot(b[0] - a[0], b[1] - a[1]) / 60) * Math.sin(Math.PI * u) };
  }

  return {
    size: [W, H], draw, tip, schedule: sched, strokes: all,
    stats: { lines: lines.length, hatch: hatches.length, texture: tex.length, vertices: nv / 2, levels: levels.length, regions: regions.length, alpha: AL.mode },
    dispose() { for (const x of [ink, wash, washB1, washB2, mask].filter(Boolean)) { gl.deleteTexture(x.tex); gl.deleteFramebuffer(x.fb); if (x.rb) gl.deleteRenderbuffer(x.rb); } },
  };
}
