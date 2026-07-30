"""
generate_metadata.py

Generates a YouTube Short title and description using the Claude API.
If faster-whisper is available, it first transcribes the rendered clip
so Claude has real content to work from; otherwise it falls back to a
generic prompt built from the filename.

Requires the ANTHROPIC_API_KEY environment variable (set as a repo
secret and passed in via the workflow).

Usage:
    python generate_metadata.py short.mp4 --out metadata.json
"""

import argparse
import json
import os

import anthropic

MODEL = "claude-haiku-4-5-20251001"  # fast and inexpensive for short metadata


def transcribe(path):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(path)
    text = " ".join(seg.text.strip() for seg in segments)
    return text.strip() or None


def generate(transcript, filename_hint):
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    context = transcript or (
        f"No transcript available. The clip's source filename is "
        f"'{filename_hint}'. Write a generic but energetic calisthenics "
        f"short title and description."
    )

    prompt = f"""You are writing metadata for a YouTube Short about calisthenics
and home-made training equipment. Based on the following context, write:
1. A title under 60 characters -- punchy, no clickbait exaggeration.
2. A description of 2-3 sentences plus 3 relevant hashtags.

Context:
{context}

Respond only as JSON with keys "title" and "description". No other text.
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Path to rendered short.mp4")
    parser.add_argument("--out", default="metadata.json")
    parser.add_argument("--skip-transcript", action="store_true")
    args = parser.parse_args()

    transcript = None if args.skip_transcript else transcribe(args.input)
    metadata = generate(transcript, os.path.basename(args.input))

    with open(args.out, "w") as f:
        json.dump(metadata, f, indent=2)

    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
