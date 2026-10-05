# Spine Format

`launch/02-spine.md` has a header and one row per scene. Times are rough here; the beat map in phase 4 sets them from the track.

Header: runtime target, words on screen (total, under 40), the one-liner, the end line, audience.

| # | Line (on screen) | Accent word | Gesture that proves it | Grows out of | Source |
|---|---|---|---|---|---|
| 1 | Research should not take fifty tabs. | fifty | fifty real source tabs open across the bar | the first tab | landing hero; landing.content.ts |
| 2 | TURN | | the tabs collapse into one, on the drop | the tab bar | Opening.tsx collapse timeline |

Rules:
- The line is verbatim product copy wherever the product already says it; mark new lines as new.
- The gesture is a real behaviour of the product, rebuilt in code. Name the source file or data.
- Mark the turn scene with TURN; it has no line or a single word.
- "Grows out of" names the shape from the previous scene. If you cannot name it, the chain is broken.
