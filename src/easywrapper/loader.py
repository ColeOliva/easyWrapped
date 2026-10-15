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


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _energy_label(value: float) -> str:
    if value >= 0.7:
        return "High-energy"
    if value >= 0.45:
        return "Balanced"
    return "Low-key"


def _valence_label(value: float) -> str:
    if value >= 0.7:
        return "Warm, bright"
    if value >= 0.45:
        return "Balanced"
    return "Reflective, moody"


def _tempo_label(value: float) -> str:
    if value >= 120:
        return "Fast and driving"
    if value >= 90:
        return "Steady groove"
    return "Slow burn"


def _focus_label(value: float) -> str:
    if value >= 0.6:
        return "Deep-focus"
    if value >= 0.35:
        return "Blend of focus and mood"
    return "Open and exploratory"


def _build_mood_profile(events: List[ListeningEvent], audio_features: list[dict]) -> dict:
    if not events:
        return {
            "energy": 0.5,
            "energy_label": "Balanced",
            "valence": 0.5,
            "valence_label": "Balanced",
            "tempo": 95.0,
            "tempo_label": "Steady groove",
            "acousticness": 0.45,
            "focus_label": "Blend of focus and mood",
            "night_share": 0.0,
            "night_share_label": "Balanced rhythm",
        }

    night_plays = sum(1 for event in events if event.listened_at.hour >= 21 or event.listened_at.hour < 5)
    night_share = round((night_plays / len(events)) * 100, 1)

    energy_values = [float(item.get("energy", 0.0)) for item in audio_features if isinstance(item, dict)]
    valence_values = [float(item.get("valence", 0.0)) for item in audio_features if isinstance(item, dict)]
    tempo_values = [float(item.get("tempo", 0.0)) for item in audio_features if isinstance(item, dict)]
    acoustic_values = [float(item.get("acousticness", 0.0)) for item in audio_features if isinstance(item, dict)]

    if not energy_values:
        energy = 0.5 + min(0.2, (night_share / 100) * 0.2)
    else:
        energy = _average(energy_values)

    if not valence_values:
        valence = 0.52 + min(0.15, (night_share / 100) * 0.18)
    else:
        valence = _average(valence_values)

    if not tempo_values:
        tempo = 90.0 + min(30.0, night_share * 0.3)
    else:
        tempo = _average(tempo_values)

    if not acoustic_values:
        acousticness = 0.45 + min(0.2, (night_share / 100) * 0.15)
    else:
        acousticness = _average(acoustic_values)

    return {
        "energy": round(energy, 3),
        "energy_label": _energy_label(energy),
        "valence": round(valence, 3),
        "valence_label": _valence_label(valence),
        "tempo": round(tempo, 2),
        "tempo_label": _tempo_label(tempo),
        "acousticness": round(acousticness, 3),
        "focus_label": _focus_label(acousticness),
        "night_share": night_share,
        "night_share_label": "Night owl" if night_share >= 30 else "Mostly daytime" if night_share <= 15 else "Balanced rhythm",
    }


def _build_analysis_categories(events: List[ListeningEvent], audio_features: list[dict]) -> list[dict]:
    if not events:
        return []

    artist_counter = Counter(event.artist for event in events)
    track_counter = Counter((event.artist, event.track) for event in events)
    unique_artists = len(artist_counter)
    unique_tracks = len({(event.artist, event.track) for event in events})
    repeated_tracks = sum(1 for count in track_counter.values() if count > 1)
    repeated_share = round((repeated_tracks / max(len(track_counter), 1)) * 100, 1)

    mood_profile = _build_mood_profile(events, audio_features)
    top_daypart = Counter(
        "Night" if event.listened_at.hour >= 21 or event.listened_at.hour < 5 else "Day"
        for event in events
    ).most_common(1)[0][0]
    artist_density = min(100, max(5, round((unique_artists / max(len(events), 1)) * 100 * 3)))
    night_score = min(100, max(10, int(mood_profile["night_share"])))

    categories = [
        {
            "name": "Late-night drift",
            "score": night_score,
            "description": f"{mood_profile['night_share']}% of your listening happens after dark.",
        },
        {
            "name": "Replay habit",
            "score": int(min(100, max(20, repeated_share * 2))),
            "description": "A few tracks keep replaying because they really match your mood.",
        },
        {
            "name": "Artist range",
            "score": artist_density,
            "description": f"You span {unique_artists} artists and keep your taste moving without needing to chase the obvious picks.",
        },
        {
            "name": "Mood intensity",
            "score": int(min(100, max(15, mood_profile["energy"] * 100))),
            "description": f"Your signal feels {mood_profile['energy_label'].lower()} and emotionally tuned.",
        },
        {
            "name": "Top window",
            "score": int(min(100, max(15, (len([event for event in events if event.listened_at.hour >= 21 or event.listened_at.hour < 5]) / max(len(events), 1)) * 100))),
            "description": f"Your strongest listening window leans {top_daypart.lower()} and gives your sound its shape.",
        },
    ]

    return categories


def _build_listener_profile(events: List[ListeningEvent], mood_profile: dict, analysis_categories: list[dict]) -> dict:
    if not events:
        return {
            "archetype": "Quiet observer",
            "headline": "No listening data yet.",
            "summary": "Once you have a few sessions, the profile will read your habits and mood more clearly.",
        }

    late_night = mood_profile.get("night_share", 0)
    energy = mood_profile.get("energy_label", "Balanced")
    valence = mood_profile.get("valence_label", "Balanced")
    artist_count = len({event.artist for event in events})
    track_count = len(events)

    if late_night >= 35 and energy == "High-energy":
        archetype = "The night-drive curator"
        headline = "You turn the late hours into your own private soundtrack."
        summary = f"Your {track_count} listens are leaning into late-night motion, with {artist_count} artists shaping a soundtrack that feels both alive and personal."
    elif valence == "Warm, bright":
        archetype = "The warm-hearted romantic"
        headline = "Your taste feels cinematic, comforting, and a little nostalgic."
        summary = f"You keep returning to warmth and emotional detail, and your library reads like a personal love letter to good melodies."
    elif energy == "Low-key":
        archetype = "The reflective wanderer"
        headline = "Your listening is quieter, more atmospheric, and intentional."
        summary = f"Across {track_count} sessions, you prefer texture, space, and the kind of songs that feel like a late thought."
    else:
        archetype = "The steady rhythm explorer"
        headline = "You like a balance of momentum and feeling."
        summary = f"Your taste sits in that sweet middle ground: enough motion to move, enough feeling to stick. It feels personal without trying too hard."

    return {
        "archetype": archetype,
        "headline": headline,
        "summary": summary,
        "categories": analysis_categories,
        "primary_trait": mood_profile.get("energy_label", "Balanced"),
    }


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
        profile = _build_listener_profile([], _build_mood_profile([], []), [])
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
            "mood_profile": _build_mood_profile([], []),
            "analysis_categories": [],
            "listener_profile": profile,
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

    summary["mood_profile"] = _build_mood_profile(events, summary["audio_features"])
    summary["analysis_categories"] = _build_analysis_categories(events, summary["audio_features"])
    summary["listener_profile"] = _build_listener_profile(events, summary["mood_profile"], summary["analysis_categories"])
    return summary
