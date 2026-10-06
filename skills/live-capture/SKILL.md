---
name: live-capture
description: Records real product motion from a live website or web app as a frame-exact 60 fps image sequence on a virtual clock, as reference for rebuilding that motion in code (timings, states, fidelity checks), and provides synthetic UI sound effects and the final X/social encode. Use this whenever a coded launch video needs the real UI's motion measured or compared, when a screen recording stutters, when UI events need sound effects, or when a render must be delivered for X, LinkedIn or other social feeds.
---

# Live Capture

Launch videos in this pipeline are one continuous coded take (see `launch-film/references/reference-films.md`): the product is rebuilt in code, and recorded footage does not appear in the video (zoomed screen recordings are what this pipeline replaces). This skill records the real UI in motion as **reference**: to measure timings and states the code inventory cannot settle, to check that a rebuilt component moves like the real one (side by side, frame by frame), and to capture states for the fidelity sheet. It also provides the synthetic SFX and the X encode.

## Why a virtual clock

Screen recordings and CDP screencasts deliver 15 to 25 uneven fps, and heavy pages drop frames exactly where the animation matters. `scripts/capture.js` replaces the page's clocks (`performance.now`, `Date.now`, `requestAnimationFrame`, `setTimeout`, `setInterval`) and slows CSS animations through CDP, then advances time by exactly 1/60 s per screenshot. GSAP, ScrollTrigger, Framer Motion and CSS reveals all play perfectly smooth, however long each screenshot takes.

## Step 1: Plan the take

Write `launch/03-brand/kit/footage/<take>.plan.json`. One take is one continuous journey through the page, because two separate takes never cut together cleanly mid-animation.

```json
{
  "url": "https://example.com/index",
  "out": "03-brand/kit/footage/map",
  "dpr": 2,
  "hideText": ["example.com"],
  "steps": [
    {"hold": 150},
    {"scroll": 300, "frames": 70},
    {"hold": 90},
    {"cursor": [744, 605], "frames": 60},
    {"click": "[aria-label^='Pricing']"},
    {"hold": 170},
    {"clickText": "Get started"},
    {"hold": 150}
  ]
}
```

- `dpr: 2` whenever the board zooms into the footage (a 2x take allows a 2x push without softness). It costs about 2.5 s per frame, so budget 30 to 40 minutes for 900 frames.
- `hideText` hides any element containing the text, for unreleased URLs, emails or internal names.
- Clicks are dispatched on the element while the real mouse stays parked outside the page. The page never shows hover states the story didn't ask for. `cursor` steps only move a logged virtual cursor that the video draws later.
- Hold long enough after each interaction for the page's own transition to finish; trimming happens in the edit.

## Step 2: Capture and check

```bash
cd launch && node tools/capture.js 03-brand/kit/footage/map.plan.json
```

Output: `00000.jpg ...` plus `log.json` (scroll y, cursor position, click per frame). Before building on it, pull a contact sheet of every 16th frame and look: the page loaded, clicks landed, nothing unexpected (cookie banners, hover panels, stray URLs) is in frame. Recapture rather than patch.

## Step 3: Use it as reference

- **Timings.** Step through the frames to measure what the code leaves open (when a reveal really starts, how long a collapse takes at a given scroll speed). Write the measured values into the inventory with the frame numbers.
- **Side by side.** Render the rebuilt component over the same frames and stack both (`ffmpeg ... hstack`) into `kit/fidelity-<take>.mp4`. Differences in timing, ease or layout get fixed in the component.
- The footage itself never goes into the video.

## Sound effects

The video is cut to a real track (house rules). `scripts/synth_sfx.py events.json sfx.wav [bed_start bed_end]` generates the UI sound effects that sit on top of it from an event list: keys, clicks, pops, bot chirps and chatter, whooshes, bells, ticks, a soft pad. Build the event list from the same timing source as the picture (beats.json or the video's scene times) so sound and picture cannot drift. You cannot listen to the result, so say so and report levels by meter.

## Delivery for X and social feeds

For X, upload the master itself when it is under 512 MB (X re-encodes anyway; a second encode only loses grain detail). Otherwise `scripts/encode_x.sh final.mp4 mix.wav final_x.mp4` re-encodes the master for feeds without a second colour conversion: 1080p60, H.264 High 4.2, BT.709 TV range as rendered, CRF 14 with a 30 Mbit/s cap, keyframe every 2 s, AAC 256k, the mix kept exactly as delivered (no loudness normalisation; the level is set once in mix_audio.py, -14 LUFS by default). Feeds re-encode anyway; a lighter file uploads faster and plays without stutter. Video grain dominates the bitrate, which is why the cap matters.

## Setup

```bash
cp <skill>/scripts/capture.js <skill>/scripts/synth_sfx.py <skill>/scripts/encode_x.sh launch/tools/
```

Needs Playwright (`npm i -D playwright`, or set `PW_CORE` to a playwright-core path) and a Chrome binary (defaults to `/usr/bin/google-chrome`).
