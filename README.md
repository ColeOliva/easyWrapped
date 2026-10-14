# easyWrapper

A minimal wrapped-style analytics project for CSV listening history, inspired by Spotify and Last.fm. It reads a CSV like the sample at the repo root, calculates top artists/tracks, and can optionally enrich songs with Spotify Audio Features metadata such as tempo, danceability, energy, valence, and acousticness.

The repo is intentionally built to accept the sample export format that does not include a header row. Each row is expected to be: artist, album, track, timestamp.

## Why this project

The repo is intentionally small and opinionated:

- It is designed for personal listening-history exports.
- It accepts headerless CSVs like the attached sample, as well as headered exports when present.
- It avoids heavy ML dependencies.
- It gives a fast baseline wrapped summary without needing a full music recommendation stack.
- It supports optional metadata enrichment from Spotify when you have developer credentials.

## Research notes

For a bare-minimum API option, Spotify is the best fit:

- Spotify Search API can look up a track by artist + track name.
- Spotify Audio Features API exposes tempo, danceability, energy, valence, acousticness, speechiness, instrumentalness, and more.
- There is no official "melodic complexity" field in Spotify. The project approximates a simple heuristic from available feature values.

## Project structure

- `main.py` – entry point for the wrapped workflow
- `src/easywrapper/loader.py` – CSV parsing and summary logic
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

## Optional Spotify enrichment

Set these environment variables or copy `.env.example`:

```bash
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
```

Then run:

```bash
python main.py coletoliva.csv --enrich
```

This will try to match each song against the Spotify catalog and fetch audio features such as:

- tempo
- danceability
- energy
- valence
- acousticness
- speechiness
- instrumentalness

## Example output

```json
{
  "total_tracks": 120,
  "unique_artists": 32,
  "top_artists": [
    {"artist": "Laufey", "plays": 12},
    {"artist": "Faye Webster", "plays": 9}
  ],
  "top_tracks": [
    {"artist": "Laufey", "track": "Misty", "plays": 4}
  ],
  "listening_window": {
    "first": "2026-10-11T00:00:00",
    "last": "2026-10-14T22:49:00"
  }
}
```

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
