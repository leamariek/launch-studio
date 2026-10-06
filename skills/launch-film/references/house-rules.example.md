# House Rules (example)

House rules are the owner's standing decisions, each learned from feedback on a real draft. They override the plugin defaults. Copy this file to `launch/house-rules.md` in your project and make it yours: keep the rules you agree with, change the numbers, and add a line every time feedback on one video should apply to every video after it.

The rules below come from the videos this plugin was built on.

## The standard
- **The bar is the three reference videos** in `reference-films.md`. Before directing anything, open their contact sheets and say which reference move each of our beats borrows. A video that reads as supers over screen recordings has missed the standard, however clean it is.
- **Approach before polish.** A 45 s script of fifteen captioned beats over screen captures was rejected outright. The fix is never a tweak of that shape; it is one continuous coded take cut to music.

## Story and framing
- **Build in public, not a vendor ad.** The owner posts as a builder. Vendor marks (AI labs, tools, platforms) appear only where the owner has cleared them for that video, and never as the hero.
- **Real things only.** Every rebuilt element traces to the product's code, data or copy. A feature the product does not ship yet stays out of the video until it ships. Get the real image or data before drawing anything.
- **Maps and data views get a designed treatment.** Rebuild map geometry and data from the source (SVG paths, projection, counts, status colours) as a full-bleed piece with a centred camera. A zoomed screen recording of a map with its UI panel was rejected.
- **Copy is the site's own.** Use the product's wording verbatim where it exists. No "free", no hype words, no promises the product cannot keep.

## Look
- The product's own design on every frame: tokens, fonts and eases from its source.
- No italics. The product's emphasis device replaces them (for example a highlighter marker in the brand's accent colour under the key words).
- Few words, big. Two to six words per line; the picture carries the rest.

## Language (on screen, in scripts and in reports)
- No em dashes. Use a comma, colon, parentheses or a period. En dashes stay allowed for numeric ranges.
- A label that introduces its explanation ends with a colon.

## Format and sound
- X launch videos: 20 to 24 s, 16:9, 1920x1080 at 60 fps. Square or 9:16 only when asked.
- **Compose the track in code, on the video's clock.** Start from `frame-engine/scripts/compose_track.py`: the bars are the video's bars, the intro plays low-passed, the collapse builds, half a beat of silence, the drop is the turn, the close resolves on the CTA click. Synthetic SFX (`live-capture/scripts/synth_sfx.py`) sit on top. The model cannot listen: verify with `analyze_track.py` (tempo, drop, energy per 0.5 s) and the loudness meter, and say so.
- **Audio standard.** A quiet studio level (-27 LUFS) was ruled far too quiet for X; the standard is now -14. Verify every mix with `frame-engine/scripts/audio_profile.py`:
  - Loudness: **-14 LUFS integrated, true peak at or below -1 dBTP.** Master to this level once; `encode_x.sh` keeps the mix as delivered.
  - Voiceover videos: the voice leads, music and SFX stay light underneath (about 12 to 18 dB under the voice).
  - Even level: short-term loudness stays within about 3 dB from intro to body (the references hold within 2 to 3 dB). A whisper-quiet intro makes the drop feel too loud.
  - Tone: no low-mid buildup (60 to 150 Hz no hotter than about -5 dB share) and real presence (1 to 2.5 kHz around -17 dB share). No saturation on the master.
  - Ending: the last gesture lands on a downbeat, then about 1.3 s of one dB-linear master fade over music and SFX together (`master_fade_out` in cues.json) to exact zero on the last frame. Never stack two fades; never let a sustained SFX outlive the fade.

## Working with the owner
- Show the beat map and six rendered stills before a full render (Gate C).
- Terse, decisive recommendations with tradeoffs. Ask only what is genuinely open.
- The owner publishes. Never post or push on their behalf.

## Voiceover editing
- **An approved cut is locked.** A new voice take is laid onto its beats; the picture is never re-timed, shortened or re-rendered to fit a voice. Fix only the defects the owner names and keep every other part byte-identical.
- **One voice, one generation.** Never splice lines from separate text-to-speech generations into one voiceover: the voice drifts between generations. Regenerate the whole script in one take instead.
- **Cut only in real silence.** Use `frame-engine/scripts/align_voice_to_picture.py`: it cuts only inside measured pauses of at least 0.2 s, never on Whisper word boundaries, never overlaps or duplicates audio, never stretches a pause and never changes tempo or pitch. A key word without a real pause before it rides in the previous chunk; approximate sync (within about 0.3 s) is fine, a broken sentence is not.
- **Check before delivery:** the script asserts every cut sits in silence and no ranges overlap; then transcribe the voice track and scan for repeated words and mid-sentence gaps over 0.35 s.
- **The preview image is metadata, not picture.** Never alter the video's frames for a thumbnail. Embed the chosen image as MP4 cover art (`-disposition:v:1 attached_pic`, never with `-shortest`), and on X choose the thumbnail in the upload editor.
