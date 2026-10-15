# easyWrapper

A minimal wrapped-style analytics project for CSV listening history. It reads a CSV like the sample at the repo root, calculates top artists and tracks, and can output either a polished PDF report or an interactive HTML dashboard with filterable ranges and popup details.

The repo is intentionally built to accept the sample export format that does not include a header row. Each row is expected to be: artist, album, track, timestamp.

## Why this project

The repo is intentionally small and opinionated:

- It is designed for personal listening-history exports.
- It accepts headerless CSVs like the attached sample, as well as headered exports when present.
- It avoids heavy ML dependencies.
- It produces a wrapped-style PDF report rather than a notebook-first workflow.
- It supports optional metadata enrichment from Spotify when you have developer credentials.

## Project structure

- `main.py` – entry point for the wrapped workflow
- `src/easywrapper/loader.py` – CSV parsing and summary logic
- `src/easywrapper/report_generator.py` – creates the Spotify-like PDF report
- `src/easywrapper/spotify_client.py` – optional Spotify enrichment
- `src/easywrapper/models.py` – data types

## Quick start

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python main.py coletoliva.csv
```

This generates a PDF file next to the CSV, such as `coletoliva_wrapped_report.pdf`.

To generate an interactive browser report instead:

```bash
python main.py coletoliva.csv --html --open-browser
```

This opens a browser-based wrapped dashboard where you can:

- change the reporting window by month range
- compare top artists and tracks across different periods
- view the most active times of day and weekly behavior
- inspect individual artists/tracks in a popup panel

## Personal-use Spotify enrichment

If you want to enrich your own listening history with Spotify audio features, keep the credentials local and private. Add them to a `.env` file in the project root (or export them in your shell), then run:

```bash
python main.py coletoliva.csv --enrich --output wrapped.pdf
```

This is intended for your own private use and should not be committed to source control. The project automatically reads a local `.env` file if present.

The Spotify enrichment is optional and works as a private improvement layer for your personal wrapped report.

## Example output

The PDF includes:

- your total listens
- top artist and top tracks
- most active day
- listening range
- optional Spotify audio-vibe cards

A JSON summary is still available with `--json` if you want the raw stats in the terminal.

## Notes on "melodic complexity"

Spotify does not expose a direct melodic complexity metric. This project uses a lightweight approximation based on available features, for example:

```text
melodic_complexity_estimate = (1 - acousticness) * 0.35 + (1 - instrumentalness) * 0.25 + valence * 0.2 + speechiness * 0.2
```

This is a useful heuristic, not a true music-theory measure.

## Next steps

Possible next enhancements:

1. Add a proper Last.fm API integration.
2. Build charts by month/week/day.
3. Add a dashboard or web UI.
4. Add artist and track embeddings for more advanced recommendations.
5. Persist output to JSON/CSV for yearly wrapped reports.
