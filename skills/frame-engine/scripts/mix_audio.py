#!/usr/bin/env python3
"""Mix music, voiceover, and SFX by timestamp into a mastered WAV.

cues.json:
{
  "duration": 45.0,
  "music": {"file": "music.wav", "start": 0.0, "offset": 0.0, "gain_db": 0, "fade_out": 1.5,
            "lowpass_until": 11.18, "lowpass_hz": 700},
  (lowpass_until: the music plays through a low-pass filter, "in the next room", until the drop)
  "vo":    [{"file": "vo_01.wav", "t": 3.0, "gain_db": 0}],
  "sfx":   [{"file": "click.wav", "t": 6.2, "gain_db": -14, "align": "peak"}],
  (align "peak": the SFX is shifted so its loudest sample lands on t, not its file start)
  "duck_db": -5,
  "master_fade_out": [21.97, 1.15],   (start, dur: the whole mix decays dB-linearly to -60 dB, last 20 ms to zero)
  "target_lufs": -14, "true_peak": -1
}
Paths are relative to cues.json.
"""
import json, subprocess, sys, os

def main(cues_path, out_path):
    base = os.path.dirname(os.path.abspath(cues_path))
    c = json.load(open(cues_path))
    dur = float(c["duration"])
    inputs, chains, labels = [], [], []

    def add(entry, t, kind, idx):
        inputs.extend(["-i", os.path.join(base, entry["file"])])
        if entry.get("align") == "peak":
            t = max(0.0, t - peak_time(os.path.join(base, entry["file"])))
        n = len(inputs) // 2 - 1
        g = entry.get("gain_db", 0)
        ms = int(round(t * 1000))
        f = f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo"
        if entry.get("offset"):
            f += f",atrim=start={entry['offset']},asetpts=PTS-STARTPTS"
        f += f",volume={g}dB,adelay={ms}|{ms}"
        lab = f"{kind}{idx}"
        chains.append(f + f"[{lab}]")
        return lab

    vo = c.get("vo", [])
    music = c.get("music")
    if music:
        lab = add(music, music.get("start", 0.0), "m", 0)
        post = []
        if music.get("lowpass_until"):
            u = float(music["lowpass_until"]) - float(music.get("start", 0.0))
            post.append(f"lowpass=f={music.get('lowpass_hz', 700)}:enable='lt(t,{u:.3f})'")
        if music.get("fade_out"):
            post.append(f"afade=t=out:st={dur - music['fade_out']}:d={music['fade_out']}")
        if vo:
            duck = c.get("duck_db", -5)
            # Duck music during each VO region (region lengths probed from files).
            for v in vo:
                L = probe(os.path.join(base, v["file"]))
                s, e = v["t"] - 0.15, v["t"] + L + 0.25
                post.append(f"volume=enable='between(t,{s:.3f},{e:.3f})':volume={duck}dB")
        if post:
            chains.append(f"[{lab}]" + ",".join(post) + "[mD]")
            lab = "mD"
        labels.append(lab)
    for i, v in enumerate(vo):
        labels.append(add(v, v["t"], "v", i))
    for i, s in enumerate(c.get("sfx", [])):
        labels.append(add(s, s["t"], "s", i))

    tl, tp = c.get("target_lufs", -14), c.get("true_peak", -1)
    mix = "".join(f"[{l}]" for l in labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest"
    mix += f",atrim=0:{dur}"
    mix += ",aresample=48000[out]"
    chains.append(mix)
    raw = out_path + ".raw.wav"
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(chains), "-map", "[out]",
           "-c:a", "pcm_s24le", raw]
    subprocess.run(cmd, check=True)
    # two-pass loudness: measure, then apply a linear gain and a true-peak limiter
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", raw, "-af", f"loudnorm=I={tl}:TP={tp}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    m = json.loads(r[r.rfind("{"):r.rfind("}") + 1])
    gain = tl - float(m["input_i"])
    lim = 10 ** ((tp - 1.2) / 20)   # AAC adds inter-sample peaks: leave 1.2 dB headroom under the target
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af",
                    f"volume={gain:.2f}dB,alimiter=limit={lim:.4f}:attack=1:release=60:level=disabled,aresample=48000",
                    "-c:a", "pcm_s24le", out_path], check=True)
    os.remove(raw)
    if c.get("master_fade_out"):
        master_fade(out_path, *c["master_fade_out"])
    print(f"wrote {out_path} (measured {float(m['input_i']):.1f} LUFS, gain {gain:+.1f} dB, limiter {tp - 1.2:.1f} dBFS)")

def master_fade(path, start, dur, depth_db=-60.0):
    """Natural ending: the whole mix (music and SFX) decays dB-linearly from `start` to `depth_db` at
    start + dur (a room-like decay, not an amplitude ramp), then the last 20 ms go to exact zero."""
    import numpy as np, wave
    with wave.open(path, "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(); raw = w.readframes(n)
    if sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        v = np.where(v & 0x800000, v - 0x1000000, v).astype(np.float64) / 8388608
    else:
        v = np.frombuffer(raw, "<i2").astype(np.float64) / 32768
    x = v.reshape(-1, ch)
    t = np.arange(len(x)) / sr
    g = np.ones(len(x)); m = t >= start
    g[m] = 10 ** (np.clip((t[m] - start) / dur, 0, 1) * depth_db / 20)
    z = t >= start + dur - 0.02; g[z] *= np.clip((start + dur - t[z]) / 0.02, 0, 1)
    x = x * g[:, None]
    q = np.clip(np.round(x * 8388607), -8388608, 8388607).astype(np.int32).reshape(-1)
    out = np.stack([(q & 0xFF), (q >> 8) & 0xFF, (q >> 16) & 0xFF], 1).astype(np.uint8).tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(ch); w.setsampwidth(3); w.setframerate(sr); w.writeframes(out)

def peak_time(p):
    """Seconds from file start to the loudest sample (for peak-aligned SFX)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", "48000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.abs(np.frombuffer(raw, np.float32))
    return float(np.argmax(x)) / 48000 if len(x) else 0.0

def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: mix_audio.py cues.json out.wav")
    main(sys.argv[1], sys.argv[2])
