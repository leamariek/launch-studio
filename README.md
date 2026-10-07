# Launch Studio

A Claude Code plugin that turns a product into a launch video. One continuous coded take, the product rebuilt in code from its real source, cut to a track that is also composed in code.

No screen recordings and no video editor. The video is a program: one HTML canvas draws the whole world through one camera as a pure function of `t`. A headless browser captures every frame with in-browser motion blur, and ffmpeg muxes the frames with the mix.

Made with it: the [EU Grant Guide launch video](https://x.com/leakorsawe/status/2105281033503424725) on X.

## Install

In Claude Code:

```
/plugin marketplace add leamariek/launch-studio
/plugin install launch-studio@launch-studio
```

Then point it at a product: "Make a launch video for this app."

## The team

Five agents, each with one job:

| Agent | Role | Owns |
|---|---|---|
| `story-strategist` | Copywriter and brand strategist | Dossier, equity story, the spine (7 to 9 short lines paired with gestures) |
| `brand-steward` | Design-system guardian | `brand.json`, the component and motion inventory, the rebuild kit, the fidelity check |
| `creative-director` | Video direction | Gesture chain, beat map from the track, motion language, Gate C stills |
| `motion-engineer` | Motion designer who codes | `video/index.html`, render, mix, QA |
| `film-critic` | Independent reviewer | Side-by-side review against the references, ship or revise |

Seven skills: `launch-film` (orchestrator, references, house rules), `equity-story`, `brand-intake`, `storyboard-motion`, `frame-engine`, `film-review` and `live-capture` (reference recordings, SFX, the X encode).

## The pipeline

```
0 Intake -> R References -> 1 Dossier -> 2 Spine -> 3 Rebuild kit -> 4 Beat map + 6 stills -> 5 Build -> 6 Render + QA -> 7 Review
            [GATE R]        [GATE A]     [GATE B]                    [GATE C]                                          [GATE D]
```

You sign off at five gates: your references, the facts, the spine, six stills rendered by the video's own code, and the final review. Gate C is the one that matters most. Direction gets agreed on real frames before anything is rendered in full.

## The rules it holds to

1. **One continuous take.** Every scene grows out of the last: a morph, a camera travel, a flood, a dive. No hard cuts.
2. **Rebuilt, not recorded.** The product's UI, copy, data and geometry are drawn as vectors from its real source. Screenshots are only used to check fidelity.
3. **Truth.** Every word and number on screen traces to the product or a cited source.
4. **Music sets the clock.** The track is composed on the video's bars, and the key gesture lands on the drop.

The bar is your own references. Before any copy is written, the studio asks for two or three launch videos you want to stand next to, as links to posts on X or as video files. It downloads each one, measures length, format, hard cuts and loudness, builds contact sheets and writes a frame-by-frame breakdown. Every later decision and the final review are judged against them. If you have none, it uses three public launch videos broken down in [`reference-films.md`](skills/launch-film/references/reference-films.md).

## House rules

Every team has its own taste. Copy [`house-rules.example.md`](skills/launch-film/references/house-rules.example.md) to `launch/house-rules.md` in your project and edit it. The pipeline reads it before every video, and every rule in it overrides the defaults. The example holds the rules from the videos this plugin was built on, each one learned from a real draft that missed.

## Hand-drawn videos

`skills/hand-drawn/` makes videos that look drawn with pencil, hatching and watercolor on toned paper, while every pixel is drawn by code. It fits a reference drawing into strokes, ink, washes and paper on the GPU and renders the draw-on in WebGL2. The fitter needs an NVIDIA GPU. The demo draws Schönbrunn Palace in Vienna.

## Requirements

Node 18+, Playwright (project install or `PW_CORE`), Chrome, ffmpeg, Python 3 with numpy, and yt-dlp to download reference videos from links.

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
  video/      index.html, engine.js, audio/ (track, sfx, cues.json, mix.wav)
  ref/       references.md, a breakdown and a facts file per reference video, contact sheets, local study copies
  renders/   draft.mp4, final.mp4, contact.jpg
  05-review.md
```

## License

MIT. The reference videos belong to their authors and aren't part of this repo.
