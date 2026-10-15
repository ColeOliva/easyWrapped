from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from .models import ListeningEvent


def _format_hour(hour: int) -> str:
    return f"{hour:02d}:00"


def _day_part_for_hour(hour: int) -> str:
    if 5 <= hour < 12:
        return "Morning"
    if 12 <= hour < 17:
        return "Afternoon"
    if 17 <= hour < 21:
        return "Evening"
    return "Night"


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


def _build_time_analysis(events: List[ListeningEvent]) -> dict:
    if not events:
        return {
            "peak_hour": None,
            "peak_hour_count": 0,
            "day_part": None,
            "day_of_week": {},
            "hourly_distribution": [],
            "avg_tracks_per_day": 0.0,
            "unique_days": 0,
        }

    hour_counter = Counter(event.listened_at.hour for event in events)
    day_counter = Counter(event.listened_at.strftime("%A") for event in events)
    daily_counter = Counter(event.listened_at.date().isoformat() for event in events)

    peak_hour = max(hour_counter.items(), key=lambda item: (item[1], -item[0]))[0]
    peak_hour_count = hour_counter[peak_hour]
    day_part = _day_part_for_hour(peak_hour)

    return {
        "peak_hour": _format_hour(peak_hour),
        "peak_hour_count": peak_hour_count,
        "day_part": day_part,
        "day_of_week": dict(sorted(day_counter.items(), key=lambda item: (-item[1], item[0]))),
        "hourly_distribution": [
            {"hour": _format_hour(hour), "count": count}
            for hour, count in sorted(hour_counter.items())
        ],
        "avg_tracks_per_day": round(sum(daily_counter.values()) / len(daily_counter), 2) if daily_counter else 0.0,
        "unique_days": len(daily_counter),
    }


def _build_monthly_trend(events: List[ListeningEvent]) -> list[dict]:
    month_counter = Counter(event.listened_at.strftime("%Y-%m") for event in events)
    return [
        {"month": month, "plays": count}
        for month, count in sorted(month_counter.items())
    ]


def build_wrapped_summary(events: Iterable[ListeningEvent], spotify_client=None, audio_client=None):
    events = list(events)

    if not events:
        return {
            "total_tracks": 0,
            "unique_artists": 0,
            "top_artists": [],
            "top_tracks": [],
            "listening_window": {"first": None, "last": None},
            "most_active_day": None,
            "time_analysis": _build_time_analysis(events),
            "monthly_trend": [],
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
        "time_analysis": _build_time_analysis(events),
        "monthly_trend": _build_monthly_trend(events),
        "audio_features": [],
    }

    provider = audio_client or spotify_client
    if provider is not None:
        summary["audio_features"] = provider.enrich_tracks(events)

    return summary
