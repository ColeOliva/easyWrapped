from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from .models import ListeningEvent


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None

    formats = [
        "%d %b %Y, %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_listening_history(csv_path: str | Path) -> List[ListeningEvent]:
    csv_path = Path(csv_path)
    events: List[ListeningEvent] = []

    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.reader(handle) if row and any(cell.strip() for cell in row)]

    if not rows:
        return []

    header_names = {str(cell).strip().lower() for cell in rows[0]}
    header_like = {
        "artist",
        "album",
        "track",
        "timestamp",
        "date",
        "listened_at",
        "time",
    }

    if header_names and header_names.issuperset(header_like):
        data_rows = rows[1:]
    else:
        data_rows = rows

    for row in data_rows:
        if len(row) < 4:
            continue

        artist = row[0].strip()
        album = row[1].strip()
        track = row[2].strip()
        timestamp_value = row[3].strip()

        timestamp = _parse_datetime(timestamp_value)
        if not artist or not track or timestamp is None:
            continue

        events.append(ListeningEvent(artist=artist, album=album, track=track, listened_at=timestamp))

    return events


def _top_counter(counter: Counter, limit: int = 5):
    return [{"label": label, "count": count} for label, count in counter.most_common(limit)]


def build_wrapped_summary(events: Iterable[ListeningEvent], spotify_client=None):
    events = list(events)

    if not events:
        return {
            "total_tracks": 0,
            "unique_artists": 0,
            "top_artists": [],
            "top_tracks": [],
            "listening_window": {"first": None, "last": None},
            "most_active_day": None,
            "audio_features": [],
        }

    artist_counter = Counter(event.artist for event in events)
    track_counter = Counter((event.artist, event.track) for event in events)
    day_counter = Counter(event.listened_at.strftime("%A") for event in events)

    summary = {
        "total_tracks": len(events),
        "unique_artists": len(artist_counter),
        "top_artists": [
            {"artist": artist, "plays": count}
            for artist, count in artist_counter.most_common(5)
        ],
        "top_tracks": [
            {"artist": artist, "track": track, "plays": count}
            for (artist, track), count in track_counter.most_common(5)
        ],
        "listening_window": {
            "first": min(event.listened_at.isoformat() for event in events),
            "last": max(event.listened_at.isoformat() for event in events),
        },
        "most_active_day": day_counter.most_common(1)[0][0] if day_counter else None,
        "audio_features": [],
    }

    if spotify_client is not None:
        summary["audio_features"] = spotify_client.enrich_tracks(events)

    return summary
