// Pencil: an on-screen pencil drawn in code (flat-shaded polygons plus a soft cast shadow) that follows the tip
// position from InkWash.tip(t). The pencil lifts between strokes: its shadow moves away and the tip rises.
//
//   import { createPencil } from './pencil.js';
//   const pencil = createPencil(gl, [W, H], { angle: -62, colors });
//   pencil.draw(ink.tip(t));   // after ink.draw(t), into the same framebuffer

const VS = `#version 300 es
in vec2 a_p; in vec4 a_c; uniform vec2 u_size; out vec4 v_c;
void main(){ v_c = a_c; gl_Position = vec4(a_p.x / u_size.x * 2.0 - 1.0, 1.0 - a_p.y / u_size.y * 2.0, 0.0, 1.0); }`;
const FS = `#version 300 es
precision highp float; in vec4 v_c; out vec4 o; void main(){ o = vec4(v_c.rgb * v_c.a, v_c.a); }`;

const DEFAULT_COLORS = {
  body: [0.33, 0.42, 0.50], light: [0.45, 0.55, 0.63], dark: [0.24, 0.31, 0.38],
  wood: [0.86, 0.72, 0.55], woodDark: [0.74, 0.58, 0.42], lead: [0.18, 0.18, 0.2],
  ferrule: [0.74, 0.74, 0.71], ferruleDark: [0.56, 0.56, 0.54], eraser: [0.84, 0.62, 0.58],
};

export function createPencil(gl, size, opts = {}) {
  const [W, H] = size;
  const col = Object.assign({}, DEFAULT_COLORS, opts.colors || {});
  const ang = ((opts.angle ?? -62) * Math.PI) / 180;            // direction from tip to eraser, y down
  const scale = opts.scale ?? 1.0;
  const sh = (t, s) => { const x = gl.createShader(t); gl.shaderSource(x, s); gl.compileShader(x); if (!gl.getShaderParameter(x, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(x)); return x; };
  const p = gl.createProgram(); gl.attachShader(p, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(p);
  const vao = gl.createVertexArray(), vb = gl.createBuffer();
  gl.bindVertexArray(vao); gl.bindBuffer(gl.ARRAY_BUFFER, vb);
  const la = gl.getAttribLocation(p, 'a_p'), lc = gl.getAttribLocation(p, 'a_c');
  gl.enableVertexAttribArray(la); gl.vertexAttribPointer(la, 2, gl.FLOAT, false, 24, 0);
  gl.enableVertexAttribArray(lc); gl.vertexAttribPointer(lc, 4, gl.FLOAT, false, 24, 8);
  gl.bindVertexArray(null);

  // pencil in its own frame: u along the pencil from the tip, v across; lengths in px
  const LEAD = 9, CONE = 34, BODY = 330, FERR = 352, END = 376, R = 9;
  function shape() {
    const q = [];   // [u0, v0, u1, v1, u2, v2, color, alpha]
    const quad = (u0, v0, u1, v1, c, a = 1) => { q.push([u0, v0, u1, v0, u1, v1, c, a], [u0, v0, u1, v1, u0, v1, c, a]); };
    q.push([0, 0, LEAD, -R * LEAD / CONE, LEAD, R * LEAD / CONE, col.lead, 1]);                   // graphite point
    q.push([LEAD, -R * LEAD / CONE, CONE, -R, CONE, R / 3, col.wood, 1]);                           // sharpened wood
    q.push([LEAD, -R * LEAD / CONE, CONE, R / 3, LEAD, R * LEAD / CONE, col.woodDark, 1]);
    q.push([LEAD, R * LEAD / CONE, CONE, R / 3, CONE, R, col.woodDark, 1]);
    quad(CONE, -R, BODY, -R / 3, col.light); quad(CONE, -R / 3, BODY, R / 3, col.body); quad(CONE, R / 3, BODY, R, col.dark);   // three facets
    quad(BODY, -R, FERR, R, col.ferrule); quad(BODY + 6, -R, BODY + 9, R, col.ferruleDark); quad(BODY + 14, -R, BODY + 17, R, col.ferruleDark);
    quad(FERR, -R * 0.95, END, R * 0.95, col.eraser);
    return q;
  }
  const parts = shape();

  function draw(tip) {
    const lift = Math.max(0, Math.min(1, tip.lift || 0));
    const du = [Math.cos(ang), Math.sin(ang)], dv = [-du[1], du[0]];
    const out = [];
    const put = (ox, oy, k, rgb, a) => {
      for (const P of parts) {
        for (let i = 0; i < 3; i++) {
          const u = P[2 * i] * scale * k, v = P[2 * i + 1] * scale;
          out.push(ox + du[0] * u + dv[0] * v, oy + du[1] * u + dv[1] * v, ...(rgb || P[6]), a ?? P[7]);
        }
      }
    };
    // soft shadow: the pencil's footprint on the paper, offset from the tip by the height above the page
    const sx = tip.x + (10 + 22 * lift) * scale, sy = tip.y + (6 + 12 * lift) * scale;
    for (const [dx, dy, a] of [[0, 0, 0.10], [2, 2, 0.06], [-2, 1, 0.05]]) put(sx + dx, sy + dy, 0.92, [0.15, 0.13, 0.12], a);
    put(tip.x, tip.y - 8 * lift * scale, 1, null, null);
    gl.useProgram(p); gl.uniform2f(gl.getUniformLocation(p, 'u_size'), W, H);
    gl.bindVertexArray(vao); gl.bindBuffer(gl.ARRAY_BUFFER, vb); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(out), gl.DYNAMIC_DRAW);
    gl.enable(gl.BLEND); gl.blendEquation(gl.FUNC_ADD); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.drawArrays(gl.TRIANGLES, 0, out.length / 6);
    gl.disable(gl.BLEND); gl.bindVertexArray(null);
  }
  return { draw };
}
