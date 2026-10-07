# Changelog

## 2.2.0 (October 7, 2026)

- New `hand-drawn` skill: videos that look drawn with pencil, hatching and watercolor on toned paper, with every pixel drawn by code. A GPU fitter turns a reference drawing into strokes (with a stroke optimizer), residual ink levels, a glaze, wash regions, paper grain and an alpha model. A WebGL2 engine draws it on in stroke order and fails if any image is loaded. Includes the quality gate (CIEDE2000, SSIM, edge F1, silhouette IoU) and a demo of Schönbrunn Palace, Vienna.

## 2.1.0 (October 7, 2026)

- Gate C now includes a 2 to 3 second clip of the trickiest transition, rendered as a range at full frame rate and motion blur with its sound, next to the six stills. The stills show the direction, and the clip shows timing and continuity before the full export. Suggested by [@Kizuno18](https://x.com/Kizuno18).

## 2.0.0 (October 5 and 6, 2026)

- First public release: launch videos as one continuous coded take, five agents (story strategist, brand steward, creative director, motion engineer, critic), nine steps with five gates, a deterministic frame engine with motion blur, music composed in code, and a review against references.
- Phase R: the studio asks for two or three reference videos at intake, downloads them, measures them and breaks them down frame by frame. Everything after that is compared against them.
- `analyze_reference.sh` handles videos with no hard cuts.
- Docs and descriptions say "launch videos" throughout.
