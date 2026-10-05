---
name: launch-film
description: End-to-end pipeline for studio-grade product launch films coded frame by frame (one continuous take on a canvas, the product rebuilt in code from its real source, cut to music, rendered deterministically and encoded with ffmpeg). Orchestrates story, brand rebuild, gesture-chain direction, the frame engine, and a critical review, with human sign-off gates. Use this whenever the user wants a launch video, launch film, product teaser, sizzle reel, announcement video, motion piece or animated product visuals for any web app, feature, SaaS, platform, or milestone, even if they only say "make a video for this."
---

# Launch Film: Pipeline Orchestrator

Read these two files before anything else:
1. `references/reference-films.md`: the standard. Three public launch films broken down frame by frame, and how to build contact sheets of them for side-by-side review.
2. The house rules: `launch/house-rules.md` in the project if it exists, else `references/house-rules.example.md`. House rules are the owner's rules from real feedback, and they override every default here. When the owner gives feedback that applies beyond this film, add it to `launch/house-rules.md`.

You are the executive producer. You run the pipeline, enforce the gates and protect the four non-negotiables. Delegate phases to the agents when subagents are available.

## The four non-negotiables

1. **One continuous take.** The film is one camera moving through one world. Every scene grows out of the last: a morph, a camera travel, a flood from its cause, a push through an object. Hard cuts are allowed only as a deliberate strobe burst on a musical hit, and only when the board names it.
2. **The product is rebuilt in code from its real source.** Read the product's code and data, then draw its UI, copy, geometry and numbers as vector shapes in the film. Rebuilt means faithful: same tokens, same labels, same data, simplified only by leaving things out. Screenshots and screen recordings are reference for fidelity checks, never footage in the film.
3. **Truth.** Every word, number, name and state on screen exists in the product, its data or the dossier. Rebuilding is not inventing: no UI element, feature, number or behaviour the product does not have.
4. **Music sets the clock.** The film is cut to a track composed on the same bar grid (or a supplied song). The key gesture lands on the drop, every event has a sound, and the beat map is checked against the track's measured tempo, downbeats and drop.

## Pipeline

| # | Phase | Owner | Skill | Output | Gate |
|---|---|---|---|---|---|
| 0 | Intake | you | this file | `launch/00-intake.md` | none |
| 1 | Dossier | story-strategist | equity-story | `launch/01-dossier.md` | **A: facts** |
| 2 | Spine: the lines and the gesture chain in words | story-strategist + creative-director | equity-story, storyboard-motion | `launch/02-spine.md` | **B: spine** |
| 3 | Rebuild kit: tokens, copy, data, geometry, coded components | brand-steward | brand-intake | `launch/03-brand/*` | none |
| 4 | Beat map + six stills rendered from the real engine | creative-director + motion-engineer | storyboard-motion, frame-engine | `launch/04-board/*` | **C: stills** |
| 5 | Build the full take | motion-engineer | frame-engine | `launch/film/*` | none |
| 6 | Render + QA | motion-engineer | frame-engine | `launch/renders/*` | none |
| 7 | Review against the references | film-critic | film-review | `launch/05-review.md` | **D: ship / revise** |

Phase 3 runs in parallel with phases 1 and 2. Gate C is the most important: six real stills (rendered by the film's own code, not mockups) plus the beat map, before any full render. This is where direction is agreed, not after a render.

At each gate, show the artifact, three lines on the decisions, and the open questions. Stop until the owner approves or edits. "Run it through" skips the stop, never the artifact.

## Phase 0: Intake

Pre-fill from the repo, live site and earlier docs. Ask only what is genuinely open, in one message:
1. Product source (repo path, live URL, data files).
2. The music: by default we compose it in code on the film's clock (`frame-engine/scripts/compose_track.py`), so the drop, the silences and every hit land exactly. A licensed song is the exception, used only when the owner supplies one.
3. The one action after the film (sign up, try the demo, open the app, share).
4. Format: default 20 to 24 s, 1920x1080 at 60 fps for X. Square 1440x1440 or 9:16 only when ordered, and then as a recomposition.
5. Guardrails: words, claims or marks that are off-limits.

## Formats and defaults

- Master: 1920x1080, 60 fps, H.264 High, yuv420p, CRF 16, AAC 320k. Four motion-blur subframes, twelve on fast pans.
- Length: 20 to 24 s. Longer only when the owner orders it; a longer film means more worlds, not longer holds.
- Delivery for X: `live-capture/scripts/encode_x.sh`.

## Revision protocol

Route feedback to the owning phase and redo that phase and everything downstream. A new line reopens phase 2 and the beat map. A token change reopens phase 3 only. Never patch a render; patch the source and re-render.

## Definition of done

- `renders/final.mp4`: one take (no cut outside a named strobe burst), no single-frame jump, no hold over 1 s, loudness -14 LUFS, true peak -1 dBTP.
- Every word and number on screen traces to the dossier or the product source.
- `05-review.md`: all hard checks pass, and the side-by-side with the reference sheets scores 8/10 or higher on every dimension.
