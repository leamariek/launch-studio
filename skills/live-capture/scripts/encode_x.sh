#!/usr/bin/env bash
# Share-ready X file from the film master and the mix.
# Usage: encode_x.sh master.mp4 mix.wav final_x.mp4
# The master from render.mjs is already BT.709, TV range, tagged. This step does NOT convert colours again
# (an earlier version converted full->TV range a second time and made the X file 18 levels darker) and does
# NOT touch loudness (the level is set once in mix_audio.py; the house standard is -14 LUFS).
# 1080p60, H.264 High 4.2, CRF 14 with a 30 Mbit/s cap (X re-encodes; give it a clean source), keyframe
# every 2 s, AAC 256k.
set -euo pipefail
ffmpeg -v error -y -i "$1" -i "$2" -map 0:v -map 1:a \
  -c:v libx264 -preset slower -tune grain -crf 14 -maxrate 30M -bufsize 60M \
  -profile:v high -level 4.2 -g 120 -keyint_min 60 -r 60 -pix_fmt yuv420p \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
  -ar 48000 -c:a aac -b:a 256k -movflags +faststart -shortest "$3"
ffprobe -v error -show_entries format=duration,size,bit_rate -of compact "$3"
