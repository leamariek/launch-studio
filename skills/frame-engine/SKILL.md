---
name: frame-engine
description: Builds and renders launch videos as one continuous coded take. A single canvas with a camera (position plus log-space zoom) draws the whole world as a pure function of t; the toolkit covers shape morphs, goo splits and merges, floods, the macOS pointer, kinetic word-by-word type with a marker accent, whole-value counters, and in-browser motion blur with more subframes on fast pans. Includes track analysis (tempo, downbeats, drop), a mixer with pre-drop low-pass and peak-aligned SFX, a headless renderer, and frame QA. Use this whenever you need to build, animate, render, export or fix a launch video, product video, motion graphic or kinetic-type piece in code, or when a render has pops, stutter, cuts or sync issues.
---

# Frame Engine

The video is a program that draws one world through one camera. `video/index.html` must draw the exact frame for any `t`, in any order, any number of times, with identical output. Read `launch-film/references/reference-films.md` first: the engine exists to make those videos.

## Setup (once per project)

```bash
cp -r <skill>/assets/film-template launch/film
mkdir -p launch/tools && cp <skill>/scripts/* launch/tools/
# Playwright: the project's own install, else PW_CORE; Chrome at /usr/bin/google-chrome
```

## The contract

`window.__film = { duration, fps, width, height, ready, seek(t), frame(t, n) }`
- `ready`: resolves once every font weight and image the video uses is loaded.
- `frame(t, n)`: draws the frame at `t` averaged over `n` motion-blur subframes (180 degree shutter). The renderer calls it once per output frame.
- `seek(t)`: `frame(t, 1)`.

## How a video is built

1. **One world, one camera.** All scenes live side by side in world coordinates. `E.camera(keys)` returns `{x, y, z}` for any `t`; zoom interpolates in log space; every key glides on the video's one curve. A pan travels through real space; a dive is a zoom toward a point.
2. **draw(ctx, t) paints everything.** Opaque stage first, then the world under `E.view(ctx, cam)`, then screen-space layers (floods, cursor, grain). No DOM animation, no CSS transitions, no state kept between calls.
3. **Scenes are functions of t, not visibility toggles.** A scene draws whatever of its shapes exist at `t`. Two scenes overlap during a handoff; the second starts from the exact shape the first ended in.
4. **Everything is vector.** Product UI is rebuilt from the rebuild kit (`03-brand/kit/components.js` and data files) with the product's tokens, copy and data. No screenshots or footage in the video.

## Toolkit (`E.*` in engine.js)

| Need | Call |
|---|---|
| Progress / tween on the glide | `E.P(t, start, dur, ease)`, `E.tw(t, start, dur, from, to, ease)`; `E.ease.glide` = `cubic-bezier(.45,0,.15,1)`, also `out`, `in`, `inOut`, `backOut(s)`, `E.bezier(...)` for the brand curve |
| Camera | `E.camera([{t,x,y,z}, ...])`, `E.view(ctx, cam)`, `E.screen(ctx)`, `E.toScreen(cam, x, y)` |
| Rounded rect and rect morph | `E.rrect(ctx, {x,y,w,h,r})` (x, y = centre), `E.lerpRect(a, b, p)` |
| Height shadow | `E.lift(ctx, height, pathFn, fill)` |
| Path morph | `E.rectPts(R)`, `E.circlePts(x, y, r)`, `E.resample(pts, n)`, `E.morphPts(A, B, p)`, `E.poly(ctx, pts)` |
| Goo split / merge | `E.goo(ctx, g => { ...draw blobs on g... })` |
| Flood from a cause | `E.flood(ctx, screenX, screenY, p, color)` |
| Pointer | `E.cursorPath(keys)(t)` (curved), `E.cursor(ctx, sx, sy, E.press(t, clickT))` |
| Kinetic line | `E.line(ctx, text, x, y, t, t0, {size, weight, family, color, align, stagger, dur, accent:[i], marker, markerAt, out})` |
| Typing | `E.typed(text, t, t0, msPerChar, seed)` |
| Counter | `E.counter(values, t, t0, step)` (whole values only) |
| Colour | `E.mix(a, b, p)`, `E.alpha(c, a)` |
| Randomness | `E.rand(seed)` only; never `Math.random` |

## Determinism rules (violations cause pops and flicker)

1. State is a pure function of `t`. `frame(10)` then `frame(3)` equals a fresh `frame(3)`.
2. No `Date.now()`, `performance.now()`, `requestAnimationFrame`, timers or `Math.random()`.
3. Paint the full opaque stage every frame (motion blur averages frames; a transparent pixel keeps an old one).
4. Reset `ctx.filter`, `globalAlpha`, `letterSpacing` and shadows after you change them (use `save/restore`).
5. A handoff between two drawings starts only after the first has fully landed; otherwise it pops.

## Music and the beat map

Default: compose the track in code (`scripts/compose_track.py`, numpy only): kick, clap, hats, bass, pad, a Karplus-Strong pluck motif and a bell, written on the video's bars. Copy it to `video/audio/compose.py`, set BPM, chords and the section plan to the chain, then `python3 video/audio/compose.py video/audio/track.wav`. Verify, never assume:

```bash
python3 tools/analyze_track.py video/audio/track.mp3 --json 04-board/track.json
```
Prints BPM, beat phase, downbeats, the drop and energy per 0.5 s. Put the scene boundaries on downbeats and the turn on the drop. Keep the times as constants at the top of `index.html` (one `BEATS` object), so a new track only moves those numbers.

## Rendering

```bash
# stills for Gate C (six key moments)
node tools/render.mjs --stills 1.2,4.8,8.9,11.2,15.5,20.4 --blur 4
# transition clip for Gate C: the trickiest handoff as a range, at final quality
node tools/render.mjs --out renders/gate-c-transition.mp4 --from 8.4 --to 10.6 --fps 60 --blur 4 --blurmap "8.9-9.7:12" --audio video/audio/mix.wav
# draft
node tools/render.mjs --out renders/draft.mp4 --fps 30 --scale 0.5
# final: 4 subframes, 12 on fast pans, with the mix
node tools/render.mjs --out renders/final.mp4 --fps 60 --blur 4 --blurmap "8.9-9.7:12,15.1-15.8:12" --audio video/audio/mix.wav
```
Render a range with `--from` / `--to` while iterating.

## Audio

`video/audio/cues.json`: the track with `lowpass_until` = the drop, and one SFX per event with `"align": "peak"` so the sound's loudest sample lands on the event. Then:
```bash
python3 tools/mix_audio.py video/audio/cues.json video/audio/mix.wav
```
Master fade: `"master_fade_out": [start, dur]` decays music and SFX together, dB-linearly, to exact zero. Check the result with `python3 tools/audio_profile.py video/audio/mix.wav ref.mp4` (loudness, LRA, tonal bands) against the references before muxing. Use only audio the user has the rights to; synthetic SFX come from `live-capture/scripts/synth_sfx.py`.

## QA (before review)

Colour: `python3 tools/color_check.py renders/final.mp4` (render stills at a few times with the same --blur first). The renderer encodes BT.709 TV range with tags, CRF 12; never convert range again later.

```bash
python3 tools/qa_frames.py renders/final.mp4
```
It flags single-frame pops, hard cuts, frozen stretches over 1 s and loudness out of spec. A video for this pipeline passes with zero CUT flags (outside a named strobe burst) and zero POP flags. Fix at the source and re-render; never patch the MP4.

## Common failures and fixes

| Symptom | Cause | Fix |
|---|---|---|
| One-frame flash at a handoff | Second drawing starts before the first lands | Start the handoff at the first shape's final value |
| Smeared digits | Counter changes every frame under blur | `E.counter` with whole-value steps |
| Ghost of an old frame | Stage not painted opaque | Fill the stage first in `draw` |
| Pan stutters | Too few subframes for the speed | Add the range to `--blurmap` with 12 |
| Cursor slides off what it drags | Cursor and object on separate curves | Derive the object position from the cursor (or the reverse) |
| Text flickers on one frame | Font weight not loaded | Add the weight to the font list awaited before `ready` |
