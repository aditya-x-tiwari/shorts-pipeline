"""
detect_claps.py

Scans a video's audio track for clap-like acoustic transients and writes
their timestamps to a JSON file for review before rendering.

A clap is treated as a short, broadband, high-energy transient. It is
distinguished from speech and background noise by combining:
  - onset strength (a sudden change in the audio signal)
  - short-term energy (loudness at that instant)
  - spectral flatness (claps are close to broadband noise; speech and
    music are more tonal, so they score lower on this measure)

Run this FIRST and inspect claps.json before running render_short.py --
clap detection is a heuristic and will occasionally need threshold
tuning for your specific recording environment (room echo, mic
sensitivity, background noise).

Usage:
    python detect_claps.py input.mp4 --out claps.json
"""

import argparse
import json
import os
import subprocess
import tempfile

import librosa
import numpy as np


def extract_audio(video_path, sr=22050):
    """Extract mono audio from a video file into a temp wav via ffmpeg."""
    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-ac", "1", "-ar", str(sr),
        "-vn", tmp_wav,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return tmp_wav


def detect_claps(audio_path, sr=22050, energy_percentile=90,
                  flatness_threshold=0.35, min_gap_seconds=0.4):
    y, sr = librosa.load(audio_path, sr=sr, mono=True)

    hop_length = 512
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=hop_length, backtrack=False
    )

    if len(onset_frames) == 0:
        return []

    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    flatness = librosa.feature.spectral_flatness(y=y, hop_length=hop_length)[0]
    energy_cutoff = np.percentile(rms, energy_percentile)

    candidates = []
    for frame in onset_frames:
        if frame >= len(rms) or frame >= len(flatness):
            continue
        if rms[frame] >= energy_cutoff and flatness[frame] >= flatness_threshold:
            t = librosa.frames_to_time(frame, sr=sr, hop_length=hop_length)
            candidates.append(float(t))

    # Collapse clusters of detections that belong to the same physical clap
    # (reverb / a single clap can trigger more than one onset frame).
    claps = []
    for t in candidates:
        if not claps or t - claps[-1] > min_gap_seconds:
            claps.append(t)

    return claps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Path to source video file")
    parser.add_argument("--out", default="claps.json", help="Output JSON path")
    parser.add_argument("--energy-percentile", type=float, default=90,
                         help="Higher = stricter (fewer, louder-only detections)")
    parser.add_argument("--flatness-threshold", type=float, default=0.35,
                         help="Higher = requires more noise-like (less tonal) sound")
    parser.add_argument("--min-gap", type=float, default=0.4,
                         help="Minimum seconds between two distinct claps")
    args = parser.parse_args()

    wav_path = extract_audio(args.input)
    try:
        claps = detect_claps(
            wav_path,
            energy_percentile=args.energy_percentile,
            flatness_threshold=args.flatness_threshold,
            min_gap_seconds=args.min_gap,
        )
    finally:
        os.remove(wav_path)

    with open(args.out, "w") as f:
        json.dump({"claps": claps}, f, indent=2)

    print(f"Detected {len(claps)} clap(s):")
    for t in claps:
        print(f"  {t:.2f}s")

    if len(claps) % 2 != 0:
        print(
            "\nWARNING: odd number of claps detected. Claps are expected "
            "in pairs bracketing a segment to remove -- inspect claps.json "
            "before rendering, since this usually means one false positive "
            "or one missed detection."
        )


if __name__ == "__main__":
    main()
