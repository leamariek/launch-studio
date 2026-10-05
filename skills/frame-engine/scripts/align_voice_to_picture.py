#!/usr/bin/env python3
"""Lay one continuous voice take onto an approved, locked picture without touching the picture.

Rules (learned from audible hiccups in a real voiceover edit):
- Cut ONLY inside real silence measured in the audio (at least MIN_SIL long), at the middle of that silence.
  Never cut on Whisper word boundaries inside flowing speech: they are imprecise, and tail+head padding
  plays the start of the next word twice.
- Chunks are consecutive, non-overlapping ranges of the take: no sample is ever used twice or dropped mid-word.
- If a key word has no real pause before it, it gets no cut; it rides in the previous chunk and lands a little
  off its picture beat. Approximate sync is fine; a broken sentence is not.
- The voice is never re-timed or re-pitched.
Checks at the end: every cut sits in silence, no overlap, and the report lists how far each key word landed
from its picture beat.

Usage: align_voice_to_picture.py take.mp3 take.words.json keys.json out.wav

take.words.json: Whisper word timings, a list of [word, start, end].
keys.json: the picture beats of the locked cut, for example
  {
    "duration": 22.0,
    "chunks": [
      {"start": "you",  "key": "you",  "at": 0.40},
      {"start": "then", "key": "drop", "at": 11.18}
    ],
    "skip": []
  }
  start: the first word of the chunk; key: the word inside it that must land on its beat; at: the picture time
  of the key word in seconds. Chunks whose key word is listed in "skip" are left out of the voice entirely
  (for example names the picture already shows as labels).
"""
import json, re, subprocess, sys
import numpy as np

SR = 48000
MIN_SIL, FLOOR_DB, FADE, MINGAP = 0.20, -40.0, 0.008, 0.08

def load(p):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()

def silences(a):
    hop = int(0.01 * SR)
    e = np.array([np.sqrt((a[i:i + hop] ** 2).mean()) for i in range(0, len(a) - hop, hop)])
    db = 20 * np.log10(e + 1e-9); quiet = db < db.max() + FLOOR_DB
    runs, i = [], 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]: j += 1
            if (j - i) * 0.01 >= MIN_SIL: runs.append((i * 0.01, j * 0.01))
            i = j
        else: i += 1
    return runs, db

def main(take, wpath, kpath, out):
    keys = json.load(open(kpath))
    CHUNKS = [(c['start'].lower(), c['key'].lower(), float(c['at'])) for c in keys['chunks']]
    SKIP = {w.lower() for w in keys.get('skip', [])}
    dur = float(keys['duration'])
    a = load(take)
    W = [(re.sub(r'[^a-z]', '', w.lower()), s, e) for w, s, e in json.load(open(wpath))]
    runs, db = silences(a)
    # locate chunk start words and key words
    found, i = [], 0
    for sw, kw, tk in CHUNKS:
        while i < len(W) and W[i][0] != sw: i += 1
        if i == len(W): sys.exit(f'chunk start "{sw}" not found')
        k = i
        while W[k][0] != kw: k += 1
        found.append((i, k, kw, tk)); i += 1
    # a chunk exists only where a real silence lies between the previous word and its start word
    chunks = []   # (cut time in take, key word time in take, key, picture time)
    for idx, k, kw, tk in found:
        if idx == 0:
            chunks.append((0.0, W[k][1], kw, tk)); continue
        lo, hi = W[idx - 1][2] - 0.1, W[idx][1] + 0.1   # the pause between the previous word and the start word
        cand = [(s, e) for s, e in runs if e > lo and s < hi]
        if not cand:
            print(f'  no pause before "{kw}": no cut, it rides in the previous chunk'); continue
        s, e = max(cand, key=lambda r: r[1] - r[0])
        chunks.append(((s + e) / 2, W[k][1], kw, tk))
    # a cut that would need pushing (stretching a pause) is dropped: that stretch stays in its original flow
    changed = True
    while changed:
        changed = False; prev_end = 0.0
        ends = [c[0] for c in chunks[1:]] + [len(a) / SR]
        for n, ((cut, kt, kw, tk), end) in enumerate(zip(chunks, ends)):
            if kw in SKIP: continue
            at = tk - (kt - cut)
            if n > 0 and at < prev_end + MINGAP - 0.02:
                print(f'  "{kw}" would need +{prev_end + MINGAP - at:.2f}s: no cut, it rides in the previous chunk')
                chunks.pop(n); changed = True; break
            prev_end = at + (end - cut)
    ends = [c[0] for c in chunks[1:]] + [len(a) / SR]
    buf = np.zeros(int(dur * SR)); prev_end = 0.0; out_ranges = []
    for (cut, kt, kw, tk), end in zip(chunks, ends):
        if kw in SKIP:
            continue
        at = tk - (kt - cut); push = max(0.0, prev_end + MINGAP - at); at += push
        seg = a[int(cut * SR):int(end * SR)].copy()
        n = int(FADE * SR); r = np.linspace(0, 1, n); seg[:n] *= r; seg[-n:] *= r[::-1]
        j = int(at * SR); buf[j:j + len(seg)] += seg[:len(buf) - j]
        out_ranges.append((at, at + len(seg) / SR)); prev_end = at + len(seg) / SR
        print(f'{kw:>9} lands {tk + push:6.2f}s (beat {tk:6.2f}s, off {push:+.2f}s)')
    # checks: every cut inside silence, no overlap in the output
    for cut, *_ in chunks[1:]:
        f = int(cut / 0.01)
        assert db[f] < db.max() + FLOOR_DB, f'cut at {cut:.2f}s is not in silence'
    for (a0, a1), (b0, b1) in zip(out_ranges, out_ranges[1:]):
        assert b0 >= a1 - 1e-6, f'overlap at {b0:.2f}s'
    print(f'checks ok: {len(chunks) - 1} cuts, all in silence, no overlap. voice ends {prev_end:.2f}s')
    st = np.repeat(buf[:, None], 2, axis=1).astype(np.float32)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-c:a', 'pcm_s24le', out], input=st.tobytes(), check=True)

if __name__ == '__main__':
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:5])
