"""
render_short.py

Given a source video and the clap timestamps produced by detect_claps.py,
this script:
  1. Removes each "slaggish" segment bracketed by a pair of claps, plus a
     buffer (default 2s) before the first clap and after the second, so
     the clap sound itself never leaks into the final cut.
  2. Speeds up whatever remains so the total duration lands on your
     target (e.g. a YouTube Short).
  3. Optionally mixes in a background music track underneath the
     original audio.

Usage:
    python render_short.py input.mp4 claps.json \
        --buffer 2.0 --target-duration 60 --music music.mp3 \
        --out short.mp4
"""

import argparse
import json
import subprocess


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def build_keep_segments(claps, buffer, total_duration):
    if len(claps) % 2 != 0:
        raise ValueError(
            "Odd number of claps -- fix claps.json before rendering "
            "(claps must come in pairs bracketing a removed segment)."
        )

    removals = []
    for i in range(0, len(claps), 2):
        start = max(0.0, claps[i] - buffer)
        end = min(total_duration, claps[i + 1] + buffer)
        if end > start:
            removals.append((start, end))

    removals.sort()
    merged = []
    for start, end in removals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    keep = []
    cursor = 0.0
    for start, end in merged:
        if start > cursor:
            keep.append((cursor, start))
        cursor = end
    if cursor < total_duration:
        keep.append((cursor, total_duration))

    return keep


def atempo_chain(factor):
    """ffmpeg's atempo filter only accepts 0.5-2.0 per instance, so factors
    outside that range need to be chained across multiple instances."""
    filters = []
    remaining = factor
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.6f}")
    return ",".join(filters)


def build_filter_complex(keep_segments, speed_factor, has_music):
    parts = []
    v_labels, a_labels = [], []

    for i, (start, end) in enumerate(keep_segments):
        parts.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},"
            f"setpts=PTS-STARTPTS[v{i}]"
        )
        parts.append(
            f"[0:a]atrim=start={start:.3f}:end={end:.3f},"
            f"asetpts=PTS-STARTPTS[a{i}]"
        )
        v_labels.append(f"[v{i}]")
        a_labels.append(f"[a{i}]")

    n = len(keep_segments)
    concat_inputs = "".join(f"{v}{a}" for v, a in zip(v_labels, a_labels))
    parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[vcat][acat]")

    parts.append(f"[vcat]setpts=PTS/{speed_factor:.6f}[vfast]")
    parts.append(f"[acat]{atempo_chain(speed_factor)}[afast]")

    if has_music:
        # Input index 1 is the music track (see main()). Music sits well
        # under the original audio -- adjust weights to taste.
        parts.append("[afast][1:a]amix=inputs=2:duration=first:weights=1 0.25[aout]")
        video_out, audio_out = "[vfast]", "[aout]"
    else:
        video_out, audio_out = "[vfast]", "[afast]"

    return ";".join(parts), video_out, audio_out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("claps_json")
    parser.add_argument("--buffer", type=float, default=2.0)
    parser.add_argument("--target-duration", type=float, default=60.0)
    parser.add_argument("--music", default=None)
    parser.add_argument("--out", default="short.mp4")
    args = parser.parse_args()

    with open(args.claps_json) as f:
        claps = json.load(f)["claps"]

    total_duration = ffprobe_duration(args.input)
    keep_segments = build_keep_segments(claps, args.buffer, total_duration)
    if not keep_segments:
        raise RuntimeError("Nothing left to render -- check claps.json and --buffer.")

    kept_duration = sum(end - start for start, end in keep_segments)
    speed_factor = max(kept_duration / args.target_duration, 1.0)

    print(f"Original duration: {total_duration:.1f}s")
    print(f"Duration after cuts: {kept_duration:.1f}s")
    print(f"Speed factor applied: {speed_factor:.3f}x")
    print(f"Estimated final duration: {kept_duration / speed_factor:.1f}s")

    filter_complex, video_out, audio_out = build_filter_complex(
        keep_segments, speed_factor, has_music=bool(args.music)
    )

    cmd = ["ffmpeg", "-y", "-i", args.input]
    if args.music:
        cmd += ["-stream_loop", "-1", "-i", args.music]
    cmd += [
        "-filter_complex", filter_complex,
        "-map", video_out, "-map", audio_out,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        args.out,
    ]

    subprocess.run(cmd, check=True)
    print(f"Rendered: {args.out}")


if __name__ == "__main__":
    main()
