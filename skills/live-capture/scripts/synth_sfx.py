"""Synthetic sound design for launch films. No samples, no music, no licensing.

Usage: synth_sfx.py events.json out.wav [bed_start_s bed_end_s]
events.json: {"fps": 60, "total": 1200, "events": [{"f": 30, "kind": "word", "p": 0}, ...]}
  or with seconds: {"duration": 20.0, "events": [{"t": 0.5, "kind": "click"}, ...]}
Kinds: key, enter, word, pop, send, reply, chatter, bubble, chime, whoosh, resolve, cut,
  toggle, count, land, check, done, approve, odo, mark, strike, click, final.
  p varies pitch or voice (chatter: 0 lead, 1 warm, 2 high).
The output is peak-normalized; film/audio mixing or encode_x.sh sets loudness.
"""
import json
import sys
import wave

import numpy as np

SR = 48000
rng = np.random.default_rng(7)
EV = sys.argv[1] if len(sys.argv) > 1 else 'events.json'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'sfx.wav'
BED = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else None
d = json.load(open(EV))
FPS = d.get('fps', 60)
TOTAL = d['total'] if 'total' in d else round(d['duration'] * FPS)
for e in d['events']:
    if 'f' not in e:
        e['f'] = e['t'] * FPS
N = int(TOTAL / FPS * SR) + SR
L = np.zeros(N)
R = np.zeros(N)


def t_(dur):
    return np.arange(int(dur * SR)) / SR


def env(n, a=0.002, dcy=0.05):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / dcy)
    return e


def lowpass(x, cutoff):
    # one-pole, cutoff may be an array
    cutoff = np.broadcast_to(cutoff, x.shape)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        a = 1 - np.exp(-2 * np.pi * cutoff[i] / SR)
        acc += a * (x[i] - acc)
        y[i] = acc
    return y


def add(sig, at_s, gain=1.0, pan=0.0):
    i = int(at_s * SR)
    sig = sig[: max(0, N - i)]
    l = np.cos((pan + 1) * np.pi / 4)
    r = np.sin((pan + 1) * np.pi / 4)
    L[i : i + len(sig)] += sig * gain * l
    R[i : i + len(sig)] += sig * gain * r


def key(var=0):
    n = int(0.05 * SR)
    noise = rng.standard_normal(n)
    click = np.diff(np.concatenate([[0], noise])) * env(n, 0.0005, 0.004)
    body = np.sin(2 * np.pi * (180 + 40 * var) * t_(0.05)) * env(n, 0.001, 0.012)
    return click * 0.5 + body * 0.6


def tick(p=0):
    n = int(0.09 * SR)
    t = t_(0.09)
    f0 = [1400, 1250, 1320, 1180, 1500][p % 5]
    s = np.sin(2 * np.pi * f0 * t) * env(n, 0.001, 0.018)
    s += np.sin(2 * np.pi * 220 * t) * env(n, 0.002, 0.03) * 0.7
    return s


def pop(p=0):
    dur = 0.14
    t = t_(dur)
    f = 260 + 60 * p + 520 * (t / dur) ** 0.6
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * env(len(t), 0.003, 0.045)


def blip(f0, f1, dur, shape=0.3):
    t = t_(dur)
    f = f0 + (f1 - f0) * (t / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) + shape * np.sin(2 * ph) + shape * 0.5 * np.sin(3 * ph)
    return s * env(len(t), 0.003, dur * 0.45)


VOICE = {  # bot voice base pitches (Hz)
    'lead': 740,
    'opus': 440,
    'scout': 1040,
}
BOT_PITCH = [980, 660, 830, 1180, 740, 1320, 590, 1100, 880]  # team order in Bots.tsx


def chatter(base, dur=0.36, warm=False):
    out = np.zeros(int(dur * SR) + SR // 4)
    pos = 0.0
    while pos < dur:
        seg = rng.uniform(0.035, 0.07)
        f0 = base * rng.choice([1, 1.125, 1.25, 1.5, 0.84])
        f1 = f0 * rng.uniform(0.85, 1.25)
        s = blip(f0, f1, seg, 0.08 if warm else 0.35)
        i = int(pos * SR)
        out[i : i + len(s)] += s
        pos += seg + rng.uniform(0.008, 0.03)
    return out


def bell(f):
    t = t_(1.8)
    m = np.sin(2 * np.pi * f * 1.4 * t) * 2.2 * np.exp(-t / 0.25)
    return np.sin(2 * np.pi * f * t + m) * env(len(t), 0.002, 0.55)


def whoosh(dur=0.7, up=True):
    n = int(dur * SR)
    x = rng.standard_normal(n)
    t = np.arange(n) / n
    cut = 300 + 3500 * (t if up else 1 - t) ** 1.5
    y = lowpass(x, cut)
    shape = np.sin(np.pi * t) ** 2
    return y * shape


def pad(freqs, dur, attack=0.4, release=1.6):
    t = t_(dur)
    s = sum(np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 2.003 * t) for f in freqs)
    e = np.minimum(1, t / attack) * np.minimum(1, np.maximum(0, (dur - t) / release))
    return s * e / len(freqs)


def thump():
    t = t_(0.2)
    f = 90 * np.exp(-t / 0.05) + 45
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.002, 0.07)


for e in d['events']:
    at = e['f'] / FPS
    k, p = e['kind'], e.get('p', 0)
    if k == 'key':
        add(key(rng.uniform(-1, 1)), at, 0.32, rng.uniform(0.1, 0.3))
    elif k == 'enter':
        add(key(-1.5) * 1.3, at, 0.45, 0.2)
    elif k == 'word':
        add(tick(p), at, 0.16)
    elif k == 'pop':
        pan = [0, -0.5, 0.6, -0.7, 0.75, -0.3, 0.35, -0.2, 0.25, -0.45][p % 10]
        add(pop(p % 8), at, 0.26, pan)
    elif k == 'send':
        add(blip(VOICE['lead'], VOICE['lead'] * 1.26, 0.06, 0.35), at, 0.13, 0.2)
    elif k == 'reply':
        f0 = BOT_PITCH[p]
        s = np.concatenate([blip(f0, f0 * 1.1, 0.045), np.zeros(int(0.02 * SR)), blip(f0 * 1.33, f0 * 1.2, 0.05)])
        add(s, at, 0.09, [0.0, 0.5, 0.6, 0.3, 0.0, -0.3, -0.6, -0.5, -0.2][p])
    elif k == 'chatter':
        who = ['lead', 'opus', 'scout'][p]
        add(chatter(VOICE[who], 0.34, warm=(who == 'opus')), at, 0.12, -0.35)
    elif k == 'bubble':
        add(pop(2) * 0.8, at, 0.2, -0.3)
    elif k == 'chime':
        add(bell(659.25), at, 0.09, 0.25)
        add(bell(987.77), at + 0.11, 0.065, 0.3)
    elif k == 'whoosh':
        add(whoosh(0.75, up=True), at - 0.2, 0.22 if p == 0 else 0.3)
    elif k == 'resolve':
        add(pad([220.0, 277.18, 329.63, 440.0], 3.2, 0.25, 2.2), at, 0.22)
        add(bell(880.0), at, 0.06)
    elif k == 'toggle':
        add(key(-2) * 1.2, at, 0.5)
        add(blip(1200, 1600, 0.05, 0.1), at + 0.03, 0.12)
    elif k == 'count':
        add(tick(p % 5) * 0.8, at, 0.07 + 0.004 * p, 0.0)
    elif k == 'land':
        add(thump(), at, 0.3)
        add(bell(1318.5), at, 0.05)
    elif k == 'check':
        add(blip(1560, 1980, 0.05, 0.05), at, 0.08, 0.3)
    elif k == 'done':
        add(bell(1046.5), at, 0.07, 0.3)
    elif k == 'approve':
        add(pop(4), at, 0.22, -0.2)
        add(blip(880, 1320, 0.07, 0.05), at + 0.06, 0.09, -0.2)
    elif k == 'odo':
        add(tick(4 - p) * 0.9, at, 0.12, 0.0)
        add(blip(700 - 90 * p, 620 - 90 * p, 0.05, 0.05), at, 0.05)
    elif k == 'mark':
        sw = whoosh(0.32, up=True)
        add(sw, at, 0.12, 0.1)
        add(bell(1567.98), at + 0.18, 0.05, 0.1)
    elif k == 'strike':
        add(whoosh(0.28, up=False) * 0.9, at, 0.16, 0.0)
        add(key(-1.8), at + 0.24, 0.3)
    elif k == 'click':
        add(key(1.2) * 0.9, at, 0.4, 0.1)
        add(key(0.4) * 0.6, at + 0.07, 0.25, 0.1)
    elif k == 'cut':
        add(thump(), at, 0.35)
    elif k == 'final':
        add(pad([293.66, 369.99, 440.0, 587.33], 2.6, 0.05, 2.0), at, 0.2)
        add(bell(1174.66), at, 0.07, 0.1)

# Soft bed from the paper scenes to the punchline, so the gaps breathe.
if BED:
    bed_from, bed_to = BED
    bed = pad([110.0, 164.81, 220.0], bed_to - bed_from, 1.5, 1.0)
    lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 0.15 * t_(bed_to - bed_from))
    add(bed * lfo, bed_from, 0.05)

mix = np.stack([L, R], 1)[: int(TOTAL / FPS * SR)]
mix /= max(1e-9, np.abs(mix).max()) / 0.89
with wave.open(OUT, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
print('ok', mix.shape[0] / SR, 's')
