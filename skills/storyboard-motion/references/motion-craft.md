# Motion Craft Standards

Measured from the reference videos (`launch-film/references/reference-films.md`). These separate the reference videos from template work.

## Timing
- **One glide curve for everything.** Morphs and camera share one ease and usually one duration (0.8 s). The shared curve is why shape changes read as one motion.
- **Content dissolves in the back half of a glide.** A shape travels first, its old content fades out after the midpoint, the new content fades in as it lands. A handoff between two drawings starts only once the first has fully landed, or it pops.
- **Holds under 1 s.** Something is always moving, but only one thing is the focus.
- **Overlap.** The next gesture begins at 60 to 75% of the previous one.
- **No springs.** Settle comes from a strong ease-out, not overshoot. The one exception is a product's own documented overshoot (for example a stamp that lands with `back.out(2.2)` in the product's code).

## Camera
- Position plus zoom, with zoom interpolated in log space so a 1x to 8x dive feels even.
- Scenes live side by side in one world; a pan really travels past the space between them.
- Push-in means attention, pull-back means revelation, a dive means "enter this". Never zoom in and straight back out.
- Everything is vector, so any zoom stays sharp.

## Type
- 2 to 6 words per line, large (display 96 to 160 px at 1080p), tight tracking from the brand.
- Words enter one by one: rise from a mask about 30% of their height, blur 8 px to 0, 60 to 90 ms apart, on the glide curve.
- One accent word per line, marked with the product's own device (a marker, a colour). No italics.
- Words live in the world: attached to the shape they describe, on the grid, in the prompt box. No caption band at the bottom.
- Typing uses real rhythm: 35 to 55 ms per character with small irregular pauses, a caret that blinks in steps.

## Shapes
- Rounded rectangles morph by interpolating x, y, w, h and radius together.
- Paths morph point by point after resampling both to the same point count.
- Goo (splits, merges): blur the blob layer about 12 px, then threshold alpha (colour matrix alpha 18, -7).
- Floods: a circle from the cause to the farthest corner, about 0.4 s, colour switch underneath.
- Shadows grow with a shape's height: two or three layered soft shadows whose offset and blur scale together.

## Cursor
- The real macOS pointer (black arrow, white outline), drawn as a vector.
- Paths are curved with ease-in-out, a press is scale 0.9 for 80 ms, and the pointer stays locked to anything it drags, even while that thing stretches.

## Numbers
- Counters swap whole values (never a smear of changing digits under motion blur). Use the real steps from the product or data.

## Sound
- Music low-passed before the drop, open after. An SFX on every event (click, type tick, whoosh on a travel, thud on a stamp), placed by the sound's measured peak, not its file start.
- SFX 10 to 16 dB under the music. Master -14 LUFS integrated, -1 dBTP.

## Rendering
- 60 fps, 4 motion-blur subframes, 12 on fast pans.
- Scan every frame for single-frame jumps and fix each at the source.
