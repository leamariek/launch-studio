# Launch Studio

A Claude Code plugin that turns a product into a launch film. One continuous coded take, the product rebuilt in code from its real source, cut to a track that is also composed in code.

No screen recordings and no video editor. The film is a program: one HTML canvas draws the whole world through one camera as a pure function of `t`. A headless browser captures every frame with in-browser motion blur, and ffmpeg muxes the frames with the mix.

Made with it: the [EU Grant Guide launch film](https://x.com/leakorsawe/status/2105281033503424725) on X.

## Install

In Claude Code:

```
/plugin marketplace add leamariek/launch-studio
/plugin install launch-studio@launch-studio
```

Then point it at a product: "Make a launch film for this app."

## The team

Five agents, each with one job:

| Agent | Role | Owns |
|---|---|---|
| `story-strategist` | Copywriter and brand strategist | Dossier, equity story, the spine (7 to 9 short lines paired with gestures) |
| `brand-steward` | Design-system guardian | `brand.json`, the component and motion inventory, the rebuild kit, the fidelity check |
| `creative-director` | Film direction | Gesture chain, beat map from the track, motion language, Gate C stills |
| `motion-engineer` | Motion designer who codes | `film/index.html`, render, mix, QA |
| `film-critic` | Independent reviewer | Side-by-side review against the references, ship or revise |

Seven skills: `launch-film` (orchestrator, references, house rules), `equity-story`, `brand-intake`, `storyboard-motion`, `frame-engine`, `film-review` and `live-capture` (reference recordings, SFX, the X encode).

## The pipeline

```
0 Intake -> 1 Dossier -> 2 Spine -> 3 Rebuild kit -> 4 Beat map + 6 stills -> 5 Build -> 6 Render + QA -> 7 Review
            [GATE A]     [GATE B]                    [GATE C]                                          [GATE D]
```

You sign off at four gates: the facts, the spine, six stills rendered by the film's own code, and the final review. Gate C is the one that matters most. Direction gets agreed on real frames before anything is rendered in full.

## The rules it holds to

1. **One continuous take.** Every scene grows out of the last: a morph, a camera travel, a flood, a dive. No hard cuts.
2. **Rebuilt, not recorded.** The product's UI, copy, data and geometry are drawn as vectors from its real source. Screenshots are only used to check fidelity.
3. **Truth.** Every word and number on screen traces to the product or a cited source.
4. **Music sets the clock.** The track is composed on the film's bars, and the key gesture lands on the drop.

The bar is three public launch films on X, broken down frame by frame in [`reference-films.md`](skills/launch-film/references/reference-films.md).

## House rules

Every team has its own taste. Copy [`house-rules.example.md`](skills/launch-film/references/house-rules.example.md) to `launch/house-rules.md` in your project and edit it. The pipeline reads it before every film, and every rule in it overrides the defaults. The example holds the rules from the films this plugin was built on, each one learned from a real draft that missed.

## Requirements

Node 18+, Playwright (project install or `PW_CORE`), Chrome, ffmpeg, and Python 3 with numpy.

## Project layout

The pipeline writes everything into `launch/` in your project:

```
launch/
  house-rules.md
  00-intake.md
  01-dossier.md
  02-spine.md
  03-brand/  brand.json, inventory/, kit/ (fonts, copy.json, data/, geo/, components.js, fidelity.png, specimen.png)
  04-board/  chain.md, beats.json, track.json, motion-language.md, stills/
  film/      index.html, engine.js, audio/ (track, sfx, cues.json, mix.wav)
  ref/       your local study copies and contact sheets of the reference films
  renders/   draft.mp4, final.mp4, contact.jpg
  05-review.md
```

## License

MIT. The reference films belong to their authors and aren't part of this repo.
