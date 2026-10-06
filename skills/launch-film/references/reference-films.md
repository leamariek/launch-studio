# Reference Films: The Standard

These three public posts on X are the default bar, used when the owner names no references of their own. Their breakdowns also show the format every breakdown in phase R follows. The films belong to their authors; watch them on X and keep your own study copies local.

| Film | Post | Length | Format | Hard cuts | Loudness |
|---|---|---|---|---|---|
| Skydive launch (shiri) | x.com/shiri_shh/status/2103882024620847348 | 20.0 s | 1920x1080, 60 fps | 1 | -12.1 LUFS |
| Motion template (twoclipping) | x.com/twoclipping/status/2104674464868762046 | 22.1 s | 1440x1440, 60 fps | 0 | -14.0 LUFS |
| AI lyric film (mexicat) | x.com/_mexicat/status/2103108369569726802 | 156.7 s | 1280x720, 60 fps | 62, all inside four strobe bursts | -15.5 LUFS |

Cut counts: ffmpeg scene score above 0.3. Everything else in all three films is continuous motion.

## Reference sheets

Directors and reviewers compare our frames with the references side by side. `scripts/analyze_reference.sh <url or file> <name>` downloads a reference, measures it and builds its sheets in `launch/ref/`:

```bash
skills/launch-film/scripts/analyze_reference.sh https://x.com/shiri_shh/status/2103882024620847348 skydive
```

Open them before any creative decision.

## What all three do (the approach)

1. **One continuous take.** Nothing cuts. Every scene grows out of the last one: a shape morphs, a camera travels, a colour floods out from the thing that caused it, a word scales through the lens. A viewer never sees a "next slide".
2. **The product is rebuilt in code, not screen-recorded.** Chat bubbles, a player, a ticket list, a terminal: clean vector UI drawn from the product's real design, at any zoom, in any state. No screenshots, no browser chrome, no scroll recordings.
3. **One gesture per scene, driven by a cursor or by the previous shape.** Click, type, drag, swipe, press. The gesture physically carries the camera into the next world.
4. **Type is picture, not subtitle.** Few words (2 to 6 per line), large, entering word by word with a rise and a blur. One word per line carries the accent. Text sits inside the world (on a grid, around an object, typed into a prompt box), never in a caption band.
5. **The music sets the clock.** Beats are the song's. The big gesture lands on the drop. Sound effects sit on every event. Before the drop the song is muffled (low-pass), then opens up.
6. **Short and dense.** 20 to 22 s for a launch. 7 to 9 ideas, about 2.5 s each. Holds never longer than about 1 s: something always moves, but there is only one focal point.
7. **A system that repeats.** A recurring motif (the prompt box, the tab, the dot), one accent colour, one type family, the same easing everywhere. The repetition is what makes it feel designed rather than assembled.

## Film 1: Skydive (shiri_shh), 20 s

Story in lines, about 2.5 s each:
1. A short line in a dark window. The window collapses into a glowing horizontal line (CRT-off), the line shrinks to a dot, black.
2. The answering line on a light stage. Character portraits pop in around the line one by one (staggered, slight scale overshoot). Then the camera pushes through the headline: the words scale up past the lens and blur out into clouds.
3. Clouds: coloured dots fly in and assemble into the logo; the wordmark slides out of the logo.
4. The product line types in word by word; the accent word is set apart (colour and style). The camera drifts down through the clouds to a light stage.
5. A rebuilt chat window. The channel name in the line swaps in place while the window content morphs to match.
6. The window flies back and tilts into perspective; a terminal slides in front. The terminal types a command, the app window beside it updates, a cursor clicks.
7. Black stage, a field of integration cards in steep perspective, and a counter that runs up in whole steps.
8. Light stage: portraits arrange into a ring with thin connecting lines.
9. The ring dissolves into haze; a character stands on a mountain at sunset. Closing line, logo, a call-to-action button, a cursor clicks it.

Craft details:
- Words enter by rising 20 to 30% of their height from a mask with a short blur, 60 to 90 ms apart.
- Transitions are blur dissolves, push-throughs and object morphs, 0.4 to 0.6 s each.
- UI is simplified but exact: avatar, name, status line, bubble colours, file chips. Everything readable at 1080p.
- Backgrounds alternate dark, paper, sky, paper, sunset, black, paper, sunset: a rhythm of worlds.

## Film 2: Motion template (twoclipping), 22 s, one take

The author published the full prompt with the post; read it there, it is the clearest statement of the method. In short: a square 22 s loop at 60 fps, 2D only, one continuous take where every scene grows out of the last and every gesture carries the camera into the next world. Every morph glides for 0.8 s on `cubic-bezier(.45,0,.15,1)` and the camera zoom rides the same curve; content dissolves in the back half of each glide; one gesture per scene. Hard cuts, bouncy springs, particles, glows, zooming in and straight back out, and holds over 1 s are banned. The press lands on the song's drop.

The chain: a `Generate` pill is clicked, glides into a spinner, then a check. The check splits into three typing dots (goo). The outer dots fly up and become a question bubble and its reply, then contract back and pour into the middle dot. The middle dot bends into a play triangle point by point. The cursor presses it on the drop; the dark app floods out around it and the leftover white becomes the play button. The camera pulls back to the full player. A cover swipe retints the whole app. The volume knob is dragged past max, rubber-bands, and drags the camera out of the app onto a dotted canvas. The line bends up into a chart while the number counts up; the knob becomes its last point. The cursor clicks the point and the camera dives into it until the light stage fills the frame. A closing line grows out of the light, thins into a line, fans into the logo, folds back and thickens into `Generate`. Last frame equals first frame.

Build rules that follow from it:
1. One canvas. Everything is a pure function of time inside `seek(t)`. No timers, no state between frames.
2. A camera with position and log-space zoom. Scenes live side by side in one world, so a pan really travels.
3. Goo: blur plus alpha threshold on an offscreen layer for splits and merges.
4. Floods are circles that grow from whatever caused them to the farthest corner in about 0.4 s; the colour switch happens underneath them.
5. Sound: before the press the song plays through a low-pass filter and opens to full on the drop. One SFX per event, placed by its measured peak. Loudness to -14 LUFS.
6. Render at 60 fps with 4 motion-blur subframes (12 on the fast pan), then scan every frame for single-frame jumps and fix each one.

Gotchas: a handoff between two drawings only works once the first has fully landed, or it pops. The cursor must stay on whatever it drags, even while it stretches. A counter that changes every frame smears under motion blur, so swap whole values.

Look: warm light stage (`#f3f3f0` to `#e3e3de`), black UI, one accent, the real macOS pointer, soft layered shadows that grow with the shape's height.

## Film 3: Lyric film (mexicat), 157 s

A music video: each sung line gets its own visual world, and the words of the line are the hero of that world.
- Words live in space: typed into a recurring prompt box, bent around a black hole, laid on a warped grid, stamped onto a form, running on an odometer counter.
- One system holds 60+ worlds together: black, one orange, off-white; a condensed display face, a mono for HUD, an occasional serif; thin frame corner ticks and tiny HUD labels (frame numbers, parameters, coordinates) on every frame.
- Worlds hand over through the camera (dive into a pupil, fly along a fuse, pull back from a grid) and through type (a word grows into the next scene).
- Hard cuts appear only as strobe bursts on drum fills (around 23 s, 59 s, 124 s, 155 s). Between them, 30 to 60 s of unbroken motion.
- Numbers are theatre: counters, probability gauges, orders of magnitude spilling off screen.

## Mapping the standard to your product

Before the spine, list what the product already has that these films build on. Everything comes from its code and data (the brand-intake inventory in `launch/03-brand/inventory/`):
- **The motif.** A shape the product itself uses that can carry the chain: a tab, a pill, a prompt box, a card, a dot. It plays the role of the generate button, the dots and the play triangle in film 2.
- **The accent.** The product's own emphasis device (a marker, a colour, a weight) as the single accent.
- **The signature motion.** An ease, an overshoot or a stamp the product documents in its code.
- **The exchange.** A real input and result (a query and its answer, a form and its outcome) as a ready-made chat gesture.
- **The data.** Lists, maps and charts with real geometry and records to rebuild in code.
- **The system.** Stage colour, ink, type families and the brand curve, from the tokens.
