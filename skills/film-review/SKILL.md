---
name: film-review
description: Independent critical review of a coded launch film against the reference standard (one continuous take, product rebuilt from source, type as picture, cut to music), plus truth, brand fidelity and technical specs, producing a scored report with frame-accurate notes and a ship or revise verdict. Use this whenever a rendered video, gesture chain or set of stills needs a quality check, an "is this at the level of the reference films?" assessment, or notes before shipping, and always as the last step of the launch-film pipeline.
---

# Film Review

You are the toughest person in the screening room, and on the team's side. You judge against the owner's references in `launch/ref/references.md` and their sheets in `launch/ref/` (the defaults in `launch-film/references/reference-films.md` only when the project has none), not against "good enough". Every note is specific (timestamp), says what it does to the viewer, and proposes a fix with an owner.

## Inputs
`renders/final.mp4` (or draft, or Gate C stills), `02-spine.md`, `01-dossier.md`, `03-brand/brand.json` and kit, `04-board/*`.

## Step 1: Hard checks (pass/fail)

```bash
python3 tools/qa_frames.py renders/final.mp4 [--strobe "<named burst ranges>"]
```
- **One take:** zero CUT flags outside a strobe burst the board names. Zero POP flags.
- **Holds:** no FREEZE flag (nothing static for more than 1 s).
- **Truth:** every word, number, name and state on screen is in `02-spine.md` with a source, or in `kit/copy.json` / `kit/data/`. Any unsourced claim or invented UI element is a FAIL.
- **Rebuilt, not recorded:** no screenshot or footage pixels in the film. Any is a FAIL.
- **Fidelity:** extract five stills and compare with `kit/fidelity.png` and brand.json (hex values, radii, glyph shapes).
- **House rules:** every rule in `launch/house-rules.md` (or the example file) holds; by default no italics, no em dashes on screen, cleared marks only.
- **Colour fidelity:** `python3 tools/color_check.py renders/final.mp4` and the same for the X file: each encode matches the renderer's own stills (mean abs diff at most 2, brightness shift under 1.5 levels, BT.709 tagged). An X file once came out 18 levels darker from a double range conversion; this check exists so nobody has to catch that by eye again.
- **Single generation:** the delivered master is rendered in one pass from source. No splicing or re-encoding of an earlier encode.
- **Spec:** resolution, 60 fps, codec, -14 LUFS (±1), true peak at or below -1 dBTP.
- **Words:** fewer than 40 words on screen in total.

## Step 2: Side by side with the references

```bash
ffmpeg -i renders/final.mp4 -vf "fps=4,scale=480:-1,tile=6x8" renders/contact.jpg
```
Put `renders/contact.jpg` next to each reference's `ref/<name>_sheet1.jpg`, and compare the film's measured facts with `ref/<name>.facts.md` (length, cuts, loudness). Look at them side by side. Answer in writing:
1. Could this sit in the same feed as the references without looking like a different league? Where does it fall short, in frames?
2. For each scene: which shape does it grow out of? Where would a viewer feel a "next slide"?
3. Is type part of the picture, or a caption over it?
4. Do the key gestures land on the music (turn on the drop)?
5. What is the one frame someone would screenshot?

## Step 3: Score (1 to 10, one sentence of justification each)

| Dimension | Asks |
|---|---|
| Continuity | One camera, one world; every scene grows out of the last |
| Gesture | One clear gesture per scene; each is a real product behaviour |
| Type | Few words, large, word-by-word, one accent; lives in the world |
| Music | Beats are the song's; the turn is on the drop; every event has a sound |
| Fidelity | Looks built by the product's own design team; tokens, fonts, copy exact |
| Story | A real tension and turn in 20 to 24 s; a competitor's logo would not fit |
| Craft | One glide curve, content dissolves in the back half, no pops, no holds over 1 s |

Ship: every hard check passes and every score is 8 or higher. Otherwise REVISE.

## Step 4: Notes (`launch/05-review.md`)

1. Verdict and scores.
2. Hard-check results, pasted.
3. **Top 3 notes**, each routed to its phase (spine, kit, chain, build).
4. Frame notes: `mm:ss.ff | observation | effect on viewer | fix | owner`.
5. What works and must be protected.

"0:08.40: the tab bar pops from 50 tabs to 1 in two frames; the collapse the whole film builds to reads as a glitch. Fix: run the product's own collapse (tabs close from the right, with the stagger from its code) over 0.8 s on the glide. Owner: build." is a note. "Could be smoother" is not.
