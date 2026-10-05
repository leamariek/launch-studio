#!/usr/bin/env python3
"""Launch track, composed in code on the film's own clock. A working example from a 24 s film:
copy it to film/audio/compose.py and set BPM, chords and the bar plan to your gesture chain.

Usage: compose.py out.wav
110 BPM, F major (vi-IV-I-V: Dm Bb F C), one bar per film bar (2.1818 s).
Form (bars):
  0-1  intro: pad and a plucked motif, heard "through a wall" (low-passed)
  2    build: soft 16th hats, pulsing bass, the filter starts to open
  3    collapse: riser and an accelerating clap roll; half a beat of silence before the drop
  4-8  the drop (the turn): full kit, bass, chord stabs, 16th pluck arpeggio, sidechained pad
  9-10 close: drums out, pad and motif resolve on F, final chord on the CTA click
Numpy only. Deterministic (seeded). You cannot hear it here: check it by meter and spectrum.
"""
import sys, wave
import numpy as np

SR = 48000
BPM = 110
BEAT = 60 / BPM
BAR = 4 * BEAT
DUR = 10 * BAR + 1.3 + 0.05         # film end: 1.3 s after the CTA click
DROP = 4 * BAR
CLICK_END = 10 * BAR               # CTA click on the bar-10 downbeat
N = int(DUR * SR)
rng = np.random.default_rng(11)
# Mix levels (linear). Tuned by measurement against the reference films: loudness range <= 4 LU,
# tonal balance close to shiri / twoclipping (less 60-150 Hz, more 1-6 kHz presence).
MIX = dict(pad=0.10, pluck_pre=0.34, pluck_post=0.34, bass=0.12, kick=0.32, clap=0.40, hat_open=0.26, hat=0.12, hat_pre=0.08,
           roll=0.22, riser=0.12, bell=0.30, stab=0.14, pre_gain_db=7.0)

def z(): return np.zeros(N)
def idx(t): return int(round(t * SR))
def midi(m): return 440.0 * 2 ** ((m - 69) / 12)

def add(buf, t, sig, gain=1.0):
    i = idx(t)
    if i >= N: return
    j = min(N, i + len(sig)); buf[i:j] += sig[:j - i] * gain

def adsr(n, a, d, s, r_len, sus_len):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r_len * SR)
    s_n = max(0, int(sus_len * SR) - a_n - d_n)
    e = np.concatenate([np.linspace(0, 1, max(a_n, 1)), np.linspace(1, s, max(d_n, 1)), np.full(s_n, s), np.linspace(s, 0, max(r_n, 1))])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))

# ---------- filters (FFT domain, static) ----------
def fft_filter(x, lo=None, hi=None, slope=2):
    n = 1 << int(np.ceil(np.log2(len(x) + 1)))
    X = np.fft.rfft(x, n); f = np.fft.rfftfreq(n, 1 / SR)
    H = np.ones_like(f)
    if hi: H /= np.sqrt(1 + (f / hi) ** (2 * slope))
    if lo: H *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1)) ** (2 * slope))
    return np.fft.irfft(X * H, n)[:len(x)]

def reverb(x, secs=2.2, damp=5000, mix=0.25, seed=3):
    r = np.random.default_rng(seed); n = int(secs * SR)
    ir = r.standard_normal(n) * np.exp(-np.arange(n) / SR * 6.9 / secs)
    ir = fft_filter(ir, hi=damp); ir[:int(0.012 * SR)] = 0; ir /= np.sqrt(np.sum(ir ** 2))
    m = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[:len(x)]
    return x * (1 - mix) + wet * mix * 0.9

# ---------- instruments ----------
def kick():
    n = int(0.45 * SR); t = np.arange(n) / SR
    f = 46 + 120 * np.exp(-t * 32); ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 7.5)
    click = rng.standard_normal(n) * np.exp(-t * 400) * 0.25
    return np.tanh(1.6 * (body + fft_filter(click, lo=1500)))

def clap():
    n = int(0.35 * SR); t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    env = sum(np.exp(-np.maximum(t - d, 0) * 90) * (t >= d) for d in (0, 0.011, 0.022)) + 0.6 * np.exp(-t * 16)
    return fft_filter(noise * env, lo=900, hi=6500) * 0.5

def hat(open_=False):
    n = int((0.22 if open_ else 0.06) * SR); t = np.arange(n) / SR
    return fft_filter(rng.standard_normal(n), lo=7000) * np.exp(-t * (18 if open_ else 70)) * 0.4

def saw(freq, n, detune=0.0):
    t = np.arange(n) / SR; out = np.zeros(n)
    for d in (-detune, 0, detune):
        out += 2 * ((t * freq * (1 + d)) % 1) - 1
    return out / 3

def pluck(freq, dur=1.6, bright=0.5, seed=0):
    # Karplus-Strong, vectorised one period at a time
    r = np.random.default_rng(seed); p = max(2, int(SR / freq)); n = int(dur * SR)
    buf = r.uniform(-1, 1, p); buf = fft_filter(np.tile(buf, 4), hi=2500 + 7000 * bright)[:p]
    out = np.zeros(n); out[:p] = buf; decay = 0.996
    for i in range(p, n, p):
        prev = out[i - p:i]; nxt = 0.5 * (prev + np.roll(prev, 1)) * decay
        out[i:i + p] = nxt[:min(p, n - i)]
    return out * np.exp(-np.arange(n) / SR * 1.2)

def bell(freq, dur=2.5):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-t * 3) + 0.2 * np.sin(2 * np.pi * freq * 5.4 * t) * np.exp(-t * 6)
    return s * np.exp(-t * 1.6) * np.minimum(1, t / 0.003)

CHORDS = [[62, 65, 69], [58, 62, 65], [65, 69, 72], [60, 64, 67]]   # Dm Bb F C
ROOTS = [38, 34, 41, 36]                                             # D2 Bb1 F2 C2
def chord_at(bar): return CHORDS[bar % 4], ROOTS[bar % 4]

pad, plk, bass, stab, kik, clp, hh, fx = z(), z(), z(), z(), z(), z(), z(), z()

# pad: every bar, soft attack; the last one is the resolving F chord
for b in range(11):
    notes, _ = chord_at(b)
    if b >= 9: notes = [65, 69, 72, 77] if b == 10 else [58, 62, 65, 70]
    n = int(BAR * SR * (1.45 if b == 10 else 1.02))
    s = sum(saw(midi(m - 12), n, 0.004) for m in notes)
    add(pad, b * BAR, fft_filter(s, lo=160, hi=3200) * adsr(n, 0.35, 0.4, 0.8, 0.5, n / SR - 0.5), MIX['pad'])

# plucked motif: chord tones walking up; quarters in the intro, eighths in bar 2-3, sixteenths after the drop
MOTIF = [0, 1, 2, 1, 2, 0, 1, 2]
for b in range(11):
    notes, _ = chord_at(b)
    if b >= 9: notes = [65, 69, 72]
    step = BEAT if b in (0, 1, 9, 10) else BEAT / 2 if b in (2, 3) else BEAT / 4
    k = 0; t = b * BAR
    while t < (b + 1) * BAR - 1e-6 and t < DUR:
        if b == 3 and t > DROP - BEAT / 2: break          # half a beat of silence before the drop
        if b == 10 and t > CLICK_END: break
        m = notes[MOTIF[k % 8]] + (12 if b >= 4 and k % 8 in (3, 7) else 0)
        add(plk, t, pluck(midi(m + 12), 1.2, 0.55 + 0.15 * (b >= 4), seed=b * 31 + k), MIX['pluck_post'] if b >= 4 else MIX['pluck_pre'])
        k += 1; t += step

# bass: pulsing eighths from bar 2, sidechain-shaped after the drop
for b in range(2, 9):
    _, root = chord_at(b)
    for e in range(8):
        t = b * BAR + e * BEAT / 2
        if b == 3 and t > DROP - BEAT / 2: break
        n = int(BEAT / 2 * SR * 0.9)
        s = fft_filter(saw(midi(root + 12 * (e % 2 == 1 and b >= 4)), n, 0.002), lo=38, hi=420 if b < 4 else 650)
        add(bass, t, s * adsr(n, 0.004, 0.08, 0.7, 0.03, n / SR - 0.03), MIX['bass'])

# drums
for b in range(2, 9):
    for s16 in range(16):
        t = b * BAR + s16 * BEAT / 4
        if b == 3 and t > DROP - BEAT / 2: break
        if b >= 4:
            if s16 % 4 == 0: add(kik, t, kick(), MIX['kick'])
            if s16 in (4, 12) and not (b == 8 and s16 == 12): add(clp, t, clap(), MIX['clap'])
            add(hh, t, hat(open_=s16 % 4 == 2), MIX['hat_open'] if s16 % 4 == 2 else MIX['hat'])
            if s16 in (6, 14) and b < 8:   # offbeat chord stabs: the mids the mix was missing
                notes_, _ = chord_at(b); n_ = int(0.2 * SR)
                st_ = sum(saw(midi(m_), n_, 0.003) for m_ in notes_)
                add(stab, t, fft_filter(st_, lo=300, hi=3500) * np.exp(-np.arange(n_) / SR * 14), MIX['stab'])
        else:
            add(hh, t, hat(), MIX['hat_pre'] * (1 + 0.6 * (b == 3)))
# collapse: accelerating clap roll (eighths, sixteenths, thirty-seconds) and a riser, both stop half a beat before the drop
t = 3 * BAR
for step, until in ((BEAT / 2, 3 * BAR + BEAT * 2), (BEAT / 4, 3 * BAR + BEAT * 3), (BEAT / 8, DROP - BEAT / 2)):
    while t < until - 1e-6:
        add(clp, t, clap(), MIX['roll'] * (0.35 + 0.65 * (t - 3 * BAR) / BAR)); t += step
rn = idx(DROP - BEAT / 2) - idx(3 * BAR)
riser = rng.standard_normal(rn) * np.linspace(0, 1, rn) ** 2
riser = fft_filter(riser, lo=600, hi=5000)
add(fx, 3 * BAR, riser, MIX['riser'])
# the turn: one clean note on the drop, and a bell on the final click
add(fx, DROP, bell(midi(77)), MIX['bell'])
add(fx, CLICK_END, bell(midi(72)), 0.3)
add(fx, CLICK_END + 0.02, bell(midi(77)), 0.2)

# sidechain pump on pad and bass after the drop (duck 0 to 1 over each beat)
duck = np.ones(N)
for b4 in range(int(DROP / BEAT), int(9 * BAR / BEAT)):
    i = idx(b4 * BEAT); n = idx(BEAT)
    env = 1 - 0.55 * np.exp(-np.arange(n) / SR * 9)
    duck[i:i + n] = np.minimum(duck[i:i + n], env[:max(0, min(n, N - i))])
pad *= duck; bass *= 0.6 + 0.4 * duck

music = reverb(pad + plk * 0.9 + stab, 2.4, 5200, 0.32) + bass + reverb(kik + clp + hh, 0.8, 7000, 0.12) + reverb(fx, 3.0, 6000, 0.35)

# "next room": low-passed until the drop, the filter opens across bar 2-3, fully open on the drop
music = fft_filter(music, lo=30)                                  # clean sub rumble
def bell_eq(x, f0, gain_db, q=1.0):
    n = 1 << int(np.ceil(np.log2(len(x) + 1))); X = np.fft.rfft(x, n); f = np.fft.rfftfreq(n, 1 / SR)
    g = 10 ** (gain_db / 20 * np.exp(-(np.log2(np.maximum(f, 1) / f0) * q * 2) ** 2)); return np.fft.irfft(X * g, n)[:len(x)]
music = bell_eq(music, 105, -3.5, 1.2)                            # the low-mid buildup the meter showed (60-150 Hz)
music = bell_eq(music, 3200, +1.5, 0.8)                           # a little presence, like the references
lp500, lp1800 = fft_filter(music, hi=1100, slope=3), fft_filter(music, hi=2800, slope=3)
t = np.arange(N) / SR
w_open = np.clip((t - 2 * BAR) / (2 * BAR - BEAT / 2), 0, 1)       # 0 at bar 2, 1 just before the drop
w_full = (t >= DROP).astype(float)
pre_gain = 10 ** (np.interp(t, [0, 2 * BAR, DROP], [MIX['pre_gain_db'] + 3.5, MIX['pre_gain_db'] + 0.5, MIX['pre_gain_db'] - 5]) / 20)
pre = (lp500 * (1 - w_open) + lp1800 * w_open) * pre_gain   # muffled but present; the build rises INTO the drop
out = pre * (1 - w_full) + music * w_full
# close: the track ends at the film's last frame; mix_audio.py master_fade_out shapes the decay
FILM_END = 10 * BAR + 1.3
fade = np.ones(N); fi = idx(CLICK_END + 0.15); fe = idx(FILM_END)
fade[fe:] = 0   # the decay itself is the mixer's master fade (music and SFX together)
out *= fade
# no saturation: clean peak normalisation, the mixer sets loudness and limits true peak
out = out / (np.max(np.abs(out)) + 1e-9) * 0.7

st = np.stack([out, np.roll(out, 12) * 0.98], 1)   # hint of width
pcm = (np.clip(st, -1, 1) * 32767).astype('<i2')
with wave.open(sys.argv[1] if len(sys.argv) > 1 else 'track.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print(f"wrote {DUR:.2f} s, drop at {DROP:.3f} s, final click {CLICK_END:.3f} s")
