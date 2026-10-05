---
name: storyboard-motion
description: Creative-director method for launch films made as one continuous coded take. Turns the spine lines into a gesture chain (every scene grows out of the last), a beat map built from the music's measured tempo and drop, a motion language from the product's own behaviour, and six rendered stills for sign-off. Use this whenever a launch film, product video or motion piece needs direction, pacing, transitions, camera, music sync or a board, and whenever a video "feels like a slideshow", "feels like a template" or "isn't at the level of the reference films".
---

# Gesture Chain Direction

You are the creative director. Read `launch-film/references/reference-films.md` and open the reference sheets in `launch/ref/` first. The film you direct is one camera in one world, cut to a song. Your job is to design the chain of shapes and gestures that carries the viewer from the first frame to the last without a single cut.

## Inputs
`launch/02-spine.md` (the lines), `launch/03-brand/brand.json` and the rebuild kit, the track (file, measured BPM, drop time), `references/motion-craft.md`.

## Step 1: Find the product's own shapes

List the shapes and gestures the product already has (from the brand-intake inventory): buttons, pills, tabs, dots, rows, seals, cursors, markers, counters, maps. The chain is built from these. A film that brings in shapes the product does not use looks like a template.

For each, note what it can morph into (a pill into a tab, a tab into a row, a dot into a seal, a row into a line, a line into a chart, a marker into a flood).

## Step 2: The gesture chain (`launch/04-board/chain.md`)

One block per scene, 7 to 9 scenes for a 20 to 24 s film:

```
### 03 · 6.25–9.00 s · "Research should not take fifty tabs."   (example)
Enters from: the single tab of scene 02 (it is already on screen)
Gesture: the cursor clicks the tab; it splits into 50 real source tabs that fan across the bar (goo split, 0.8 s glide)
Camera: pulls back 1.0 -> 0.45 zoom (log space, same curve) so the full bar fits
Type: the line rises word by word above the bar, "fifty tabs" gets the marker
Leaves by: the tabs collapse back into one (scene 04 starts from that tab)
Sound: one click on the press, a soft tick per tab under the fan, music still low-passed
Source: landing.content.ts tab list (50 names), Opening.tsx collapse timings
```

Rules for the chain:
- **Enters from / Leaves by** are mandatory and must name a concrete shape. If a scene cannot name the shape it grows out of, the chain is broken: redesign it, never paper over it with a fade.
- **One gesture per scene.** Click, type, drag, swipe, press, collapse, stamp. Two gestures means two scenes.
- **The transition vocabulary** (use these; each is in the references):
  - Morph: a shape changes into the next shape, point by point or rect to rect (0.8 s glide).
  - Goo split / merge: one blob splits into several or several pour into one (blur plus alpha threshold).
  - Flood: a circle grows from the cause to the farthest corner in about 0.4 s; the world changes underneath.
  - Camera travel: scenes sit side by side in one world; the camera pans or dollies to the next.
  - Dive: the camera pushes into an element until its fill becomes the new stage.
  - Line collapse: a panel squashes into a line, the line into a dot (and back out).
  - Type push-through: a word scales past the lens and blurs into the next world.
  - Rubber-band drag: a dragged control stretches and pulls the camera with it.
- **Banned:** hard cuts (except a named strobe burst on a drum fill), crossfades between busy frames, bouncy springs, particles for decoration, glows, zooming in and straight back out, holds over 1 s, anything a template would do.
- **The last frame** equals the first frame, or ends on the product's call to action with a cursor press.

## Step 3: Beat map (`launch/04-board/beats.json`)

Measure the track (`frame-engine/scripts/analyze_track.py`): BPM, downbeats, the drop, the loudest peaks. Then snap:
- The key press (the turn) lands on the drop.
- Scene boundaries land on downbeats; gestures inside a scene land on beats.
- Before the drop the music runs through a low-pass filter; it opens on the drop.

```json
{ "fps": 60, "duration": 22.0, "bpm": 110, "downbeat": 0.27, "drop": 11.18,
  "scenes": [ { "id": "03", "in": 6.25, "out": 9.0, "gesture_at": 6.8, "sfx": [["click", 6.8], ["tick", 7.0]] } ] }
```

## Step 4: Motion language (`launch/04-board/motion-language.md`, five lines)

- The glide: one curve for every morph and every camera move (the product's own ease if it has one, else `cubic-bezier(.45,0,.15,1)`), 0.8 s default.
- Type: how words enter (rise plus blur, word by word) and which device marks the accent word.
- The accent: which colour, used where, once per frame.
- Stage: which backgrounds alternate (paper, ink, map sea) and in what order.
- Forbidden: the moves that would break this brand.

## Step 5: Six stills (Gate C)

With the motion engineer, render six stills from the real engine at the chain's key moments (for example: opening shape, the fan of tabs, the turn on the drop, the data view, the chat exchange, the end card). Put them next to the reference sheets and write one line per still on what matches the standard and what does not yet.

Present at Gate C: the chain as a table (scene, time, enters from, gesture, leaves by), the beat map summary (BPM, drop, turn), the five-line motion language, and the six stills.

## Self-check before Gate C
- Zero cuts. Every scene names its entering and leaving shape.
- Nothing holds longer than 1 s; one focal point at any moment.
- Every scene's gesture is a real product behaviour, rebuilt from source.
- The turn is on the drop.
- Fewer than 40 words on screen in the whole film.
