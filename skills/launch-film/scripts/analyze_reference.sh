#!/usr/bin/env bash
# Measures one reference film and builds its study sheets (phase R).
# Usage: analyze_reference.sh <video file or URL> <name> [outdir]
#   URL: a post on X, YouTube, Vimeo or any page yt-dlp supports. The download is a private study copy.
#   Writes <outdir>/<name>.mp4 (for URLs), <name>.facts.md, <name>_sheet1.jpg and <name>_dense_NN.jpg.
#   outdir defaults to launch/ref.
set -euo pipefail
src="${1:?video file or URL}"; name="${2:?short name, e.g. skydive}"; out="${3:-launch/ref}"
mkdir -p "$out"

if [[ "$src" =~ ^https?:// ]]; then
  command -v yt-dlp >/dev/null || { echo "yt-dlp not found: pip install yt-dlp (or download the video yourself and pass the file)"; exit 1; }
  yt-dlp -q --no-playlist -f "bv*+ba/b" --merge-output-format mp4 -o "$out/$name.%(ext)s" "$src"
  url="$src"; src="$out/$name.mp4"
else
  url=""
fi

dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$src")
IFS=, read -r w h rate < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$src")
fps=$(python3 -c "n,d='$rate'.split('/');print(round(int(n)/int(d),2))")

# hard cuts: scene score above 0.3 (the same threshold the reference breakdowns use)
cut_times=$(ffmpeg -hide_banner -i "$src" -vf "select='gt(scene,0.3)',showinfo" -an -f null - 2>&1 \
  | { grep -o 'pts_time:[0-9.]*' || true; } | cut -d: -f2 | awk '{printf "%.2f s, ", $1}' | sed 's/, $//')
cuts=$( [ -z "$cut_times" ] && echo 0 || echo "$cut_times" | tr ',' '\n' | wc -l )

# loudness (EBU R128): integrated and true peak
loud=$(ffmpeg -hide_banner -i "$src" -af ebur128=peak=true -f null - 2>&1 || true)
lufs=$(echo "$loud" | awk '/^ *I:/{v=$2} END{print v}')
tp=$(echo "$loud" | awk '/^ *Peak:/{v=$2} END{print v}')

# sheets: an overview at 4 fps and dense sheets at 12 fps for the fast passages
ffmpeg -v error -y -i "$src" -vf "fps=4,scale=480:-1,tile=6x8" -frames:v 1 "$out/${name}_sheet1.jpg"
ffmpeg -v error -y -i "$src" -vf "fps=12,scale=320:-1,tile=8x10" "$out/${name}_dense_%02d.jpg"

cat > "$out/$name.facts.md" <<EOF
# $name: measured facts

| Field | Value |
|---|---|
| Source | ${url:-$src} |
| Length | $(printf '%.1f' "$dur") s |
| Format | ${w}x${h}, $fps fps |
| Hard cuts (scene score > 0.3) | $cuts |
| Cut times | ${cut_times:-none} |
| Loudness | ${lufs:-n/a} LUFS integrated, true peak ${tp:-n/a} dBTP |

Sheets: ${name}_sheet1.jpg (4 fps), ${name}_dense_*.jpg (12 fps). Look at them before writing $name.md.
EOF
echo "wrote $out/$name.facts.md and sheets: ${dur%.*} s, ${w}x${h} @ $fps fps, $cuts cuts, ${lufs:-?} LUFS"
