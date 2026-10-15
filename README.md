# easyWrapper

A personal wrapped-style analytics project for CSV listening history. It reads a listening export, calculates top artists and tracks, and can output either a polished PDF or a browser-based dashboard with filterable ranges and popup details.

The repo is intentionally built to accept the common listening-export format that does not include a header row. Each row is expected to be: artist, album, track, timestamp.

## Why this project

The repo is intentionally small and opinionated:

- It is designed for personal listening-history exports.
- It accepts headerless CSVs like the attached sample, as well as headered exports when present.
- It avoids heavy ML dependencies.
- It produces a wrapped-style report without requiring a notebook workflow.
- It supports optional audio-feature enrichment, but defaults to a local/offline JSON path so it can run without live API calls.

## Project structure

- `main.py` – entry point for the wrapped workflow
- `src/easywrapper/loader.py` – CSV parsing and summary logic
- `src/easywrapper/html_report.py` – browser-based wrapped dashboard
- `src/easywrapper/report_generator.py` – PDF report generation
- `src/easywrapper/audio_enrichment.py` – local JSON provider + optional Spotify/Freqblog adapters
- `src/easywrapper/spotify_client.py` – optional Spotify enrichment
- `src/easywrapper/models.py` – data types
- `data/` – local JSON cache for audio-feature payloads when using the offline provider

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

## Offline by default

The project defaults to the local/offline data path to avoid live API requests. In practice, that means:

- If you have saved audio-feature JSON payloads in the `data/` folder, they are used automatically.
- No live requests are made unless you explicitly choose a provider such as Spotify or Freqblog.
- This makes the app safe for a personal budget and easy to run with a local cache.

## Optional live enrichment

If you want to enrich your own listening history with Spotify audio features, keep the credentials local and private. Add them to a `.env` file in the project root (or export them in your shell), then run:

```bash
python main.py coletoliva.csv --enrich --audio-provider spotify --output wrapped.pdf
```

This is intended for your own private use and should not be committed to source control. The project automatically reads a local `.env` file if present.

For a provider that is shaped similarly to Spotify but does not require a personal developer account, you can also use the `freqblog` adapter when configured.

## Example output

The PDF or HTML includes:

- your total listens
- top artist and top tracks
- most active day
- listening range
- optional audio-vibe cards when metadata is available

A JSON summary is still available with `--json` if you want the raw stats in the terminal.

## Generated files

Files like `tmp_wrapped_report.html`, `wrapped.pdf`, and `*_wrapped_report.*` are generated artifacts. They are useful for local viewing but are not part of the app source itself.

If you want a clean repo, you can delete these locally or keep them in a separate output folder; they should not be treated as source files.

## Notes on "melodic complexity"

Spotify does not expose a direct melodic complexity metric. This project uses a lightweight approximation based on available features, for example:

```text
melodic_complexity_estimate = (1 - acousticness) * 0.35 + (1 - instrumentalness) * 0.25 + valence * 0.2 + speechiness * 0.2
```

This is a useful heuristic, not a true music-theory measure.

## Next steps

Possible next enhancements:

1. Add a proper JSON export/import workflow for your personal audio cache.
2. Build charts by month/week/day.
3. Add a richer dashboard UI.
4. Add artist and track embeddings for more advanced recommendations.
5. Persist output to JSON/CSV for yearly wrapped reports.
