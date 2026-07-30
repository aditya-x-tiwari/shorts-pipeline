# Shorts pipeline

Turns a long-form clip into a YouTube Short: removes segments bracketed
by two claps (plus a buffer), speeds up what remains to hit a target
duration, mixes in optional background music, and generates a title and
description with the Claude API.

## Setup

1. Create a new GitHub repository and copy this entire folder structure
   into it (including the `.github/workflows/` folder — it must sit at
   the repo root for GitHub to detect the workflow).
2. In the repo's **Settings → Secrets and variables → Actions**, add a
   secret named `ANTHROPIC_API_KEY` with your Anthropic API key.
3. Push. GitHub will pick up the workflow automatically.

## Running it

1. Get a direct download link to your raw video (e.g. a shareable link
   from Google Drive or a DigitalOcean Space — it needs to resolve to
   the raw file with `curl -L`, not an HTML preview page).
2. Go to the repo's **Actions** tab → **Shorts Pipeline** → **Run
   workflow**.
3. Fill in `video_url` (required) and, optionally, `music_url`,
   `target_duration` (seconds, default 60), and `buffer_seconds`
   (default 2.0).
4. Click **Run workflow**. You can close the browser tab immediately —
   the job runs on GitHub's servers independently of your session.
5. If a step fails, GitHub emails the account owner automatically — no
   extra setup needed.
6. When it finishes, open the run and download the `rendered-short`
   artifact, which contains `short.mp4`, `metadata.json` (title +
   description), and `claps.json` (the detected clap timestamps, kept
   for your reference).

## Tuning clap detection

Clap detection is a heuristic (energy + spectral flatness threshold),
not a trained model, so it may need adjustment for your specific
recording setup. If `claps.json` looks wrong after a run:

- Too many false positives → raise `--energy-percentile` and/or
  `--flatness-threshold` in the `detect_claps.py` step.
- Missed claps → lower them.
- Odd number of claps in the output is flagged with a warning — claps
  must come in pairs (start of a removed segment, end of it).

You can also run `detect_claps.py` locally against a downloaded copy of
your video to iterate faster before triggering the full workflow.

## Notes

- The runner's disk is scratch space only — nothing persists after the
  job finishes except the artifact GitHub stores for you (7-day
  retention here; adjust in the workflow's `retention-days`).
- If you'd rather have the finished Short land somewhere more permanent
  than a workflow artifact, swap the final step for a `gh release
  upload` call (GitHub Releases: up to 2 GiB per file, no bandwidth
  limit) or a push to object storage (e.g. a DigitalOcean Space).
