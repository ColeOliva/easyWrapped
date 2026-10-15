from __future__ import annotations

import csv
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List
from zoneinfo import ZoneInfo

from .models import ListeningEvent


def _format_hour(hour: int) -> str:
    return f"{hour:02d}:00"


def _normalize_artist_name(artist: str | None) -> str:
    if artist is None:
        return ""
    cleaned = str(artist).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+feat(?:uring)?\.?\s+.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+&\s+", " and ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\(.*?\)$", "", cleaned)
    return cleaned.strip()


def _day_part_for_hour(hour: int) -> str:
    if 5 <= hour < 12:
        return "Morning"
    if 12 <= hour < 17:
        return "Afternoon"
    if 17 <= hour < 21:
        return "Evening"
    return "Night"


def _parse_datetime(value: str | None, timezone_name: str | None = None) -> datetime | None:
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
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            break
        except ValueError:
            continue
    else:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is None and timezone_name:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
        except Exception:
            parsed = parsed.replace(tzinfo=timezone.utc)
    elif parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def _calculate_listening_diversity(artist_counter: Counter) -> float:
    if not artist_counter:
        return 0.0

    total = sum(artist_counter.values())
    entropy = -sum((count / total) * math.log2(count / total) for count in artist_counter.values() if count)
    max_entropy = math.log2(len(artist_counter)) if len(artist_counter) > 1 else 1.0
    if max_entropy <= 0:
        return 0.0
    return round(entropy / max_entropy, 3)


def _build_discovery_by_month(events: List[ListeningEvent]) -> list[dict]:
    month_map: dict[str, list[str]] = {}
    for event in events:
        month = event.listened_at.strftime("%Y-%m")
        month_map.setdefault(month, [])
        month_map[month].append(_normalize_artist_name(event.artist))

    seen_artists: set[str] = set()
    results: list[dict] = []
    for month in sorted(month_map):
        artist_names = month_map[month]
        month_counter = Counter(artist_names)
        new_artists = sum(1 for artist in month_counter if artist and artist not in seen_artists)
        repeat_artists = sum(1 for artist in month_counter if artist and artist in seen_artists)
        seen_artists.update(artist for artist in month_counter if artist)
        results.append({
            "month": month,
            "new_artists": new_artists,
            "repeat_artists": repeat_artists,
            "top_artists": [{"artist": artist, "plays": count} for artist, count in month_counter.most_common(5)],
        })
    return results


def _jensen_shannon_divergence(left: Counter, right: Counter) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 0.0

    left_total = sum(left.values()) or 1
    right_total = sum(right.values()) or 1
    p = {key: left.get(key, 0) / left_total for key in keys}
    q = {key: right.get(key, 0) / right_total for key in keys}
    m = {key: 0.5 * (p[key] + q[key]) for key in keys}

    entropy_part = 0.0
    for key in keys:
        term_left = 0.0
        term_right = 0.0

        if p[key] > 0 and m[key] > 0:
            term_left = p[key] * math.log2(p[key] / m[key])
        if q[key] > 0 and m[key] > 0:
            term_right = q[key] * math.log2(q[key] / m[key])

        entropy_part += (term_left + term_right) * 0.5
    return round(entropy_part, 4)


def _build_taste_drift(events: List[ListeningEvent]) -> float:
    month_artist_counts: dict[str, Counter] = {}
    for event in events:
        month = event.listened_at.strftime("%Y-%m")
        month_artist_counts.setdefault(month, Counter())
        month_artist_counts[month][_normalize_artist_name(event.artist)] += 1

    months = sorted(month_artist_counts)
    if len(months) < 2:
        return 0.0

    divergences = []
    for left_month, right_month in zip(months, months[1:]):
        divergences.append(_jensen_shannon_divergence(month_artist_counts[left_month], month_artist_counts[right_month]))

    return round(sum(divergences) / len(divergences), 3) if divergences else 0.0


def _build_familiarity_curve(events: List[ListeningEvent]) -> list[dict]:
    track_counts = Counter((event.artist, event.track) for event in events)
    repeated_play_counts = Counter(count for count in track_counts.values() if count > 1)
    if not repeated_play_counts:
        return [{"play_count": 1, "track_count": len(track_counts)}]

    return [
        {"play_count": play_count, "track_count": count}
        for play_count, count in sorted(repeated_play_counts.items())
    ]


def _build_reminiscence_bump(audio_features: list[dict]) -> dict:
    release_years = []
    for item in audio_features:
        if not isinstance(item, dict):
            continue
        value = item.get("release_date") or item.get("release_year")
        if not value:
            continue
        try:
            if isinstance(value, str) and len(value) >= 4:
                year = int(value[:4])
            else:
                year = int(value)
            release_years.append(year)
        except (TypeError, ValueError):
            continue

    if not release_years:
        return {"available": False, "message": "No release years were available in the enriched metadata."}

    avg_year = round(sum(release_years) / len(release_years), 1)
    return {
        "available": True,
        "average_release_year": avg_year,
        "earliest_release_year": min(release_years),
        "latest_release_year": max(release_years),
        "message": "This signal is only meaningful when the audio metadata contains release years.",
    }


def load_listening_history(csv_path: str | Path, timezone_name: str | None = None) -> List[ListeningEvent]:
    csv_path = Path(csv_path)
    events: List[ListeningEvent] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

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

        artist = _normalize_artist_name(row[0])
        album = str(row[1]).strip() if len(row) > 1 else ""
        track = str(row[2]).strip() if len(row) > 2 else ""
        timestamp_value = str(row[3]).strip() if len(row) > 3 else ""

        timestamp = _parse_datetime(timestamp_value, timezone_name=timezone_name)
        if not artist or not track or timestamp is None:
            continue

        key = (artist.lower(), track.lower(), album.lower(), timestamp.isoformat())
        if key in seen_keys:
            continue
        seen_keys.add(key)

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
    energy_value = float(mood_profile.get("energy", 0.5))
    valence_value = float(mood_profile.get("valence", 0.5))

    valence_label = mood_profile.get("valence_label", "Balanced").lower()

    if late_night >= 35 and energy == "High-energy":
        archetype = "The night-drive curator"
        headline = "You turn the late hours into your own private soundtrack."
        summary = (
            "Your listening pattern is strongly evening-weighted: about "
            f"{late_night}% of your sessions happen after dark, with an energy read of {energy_value:.2f} and a {valence_label} tone. "
            "That combination commonly points to music used for emotional processing, focus, or a bit of motion after the day settles."
        )
    elif valence == "Warm, bright":
        archetype = "The warm-hearted romantic"
        headline = "Your taste feels cinematic, comforting, and a little nostalgic."
        summary = (
            f"You are leaning into warm, emotionally resonant music: valence sits around {valence_value:.2f}, and the collection spans {artist_count} artists across {track_count} listens. "
            "This kind of profile is often associated with music that feels comforting, uplifting, and personally familiar."
        )
    elif energy == "Low-key":
        archetype = "The reflective wanderer"
        headline = "Your listening is quieter, more atmospheric, and intentional."
        summary = (
            f"The signal is more reflective than high-arousal: energy sits around {energy_value:.2f}, valence is around {valence_value:.2f}, and roughly {late_night}% of plays happen late. "
            "That pattern often matches introspective, textural listening used to slow the pace down."
        )
    else:
        archetype = "The steady rhythm explorer"
        headline = "You like a balance of momentum and feeling."
        summary = (
            f"Your profile reads as balanced rather than extreme: energy {energy_value:.2f}, valence {valence_value:.2f}, and a late-night share of {late_night}%. "
            "That mix suggests you are not chasing one mood alone; you are building a personal soundtrack that can move between reflection, motion, and comfort."
        )

    evidence = [
        {
            "label": "Late-night share",
            "value": f"{late_night}%",
            "detail": "Research on music listening often links a strong evening signal to emotional regulation, routine, and lower-stimulation listening habits.",
        },
        {
            "label": "Energy",
            "value": f"{energy_value:.2f}",
            "detail": "Values around this range usually signal balanced listening: not purely high-arousal, but also not sleep-like or fully ambient.",
        },
        {
            "label": "Valence",
            "value": f"{valence_value:.2f}",
            "detail": "This score indicates whether the music skews more reflective, moody, or warm and bright. Your pattern sits on the reflective-to-balanced side.",
        },
        {
            "label": "Artist breadth",
            "value": f"{artist_count} artists",
            "detail": "A broad artist footprint usually suggests exploratory taste rather than a narrow fixation on a single scene or mood.",
        },
    ]

    return {
        "archetype": archetype,
        "headline": headline,
        "summary": summary,
        "categories": analysis_categories,
        "primary_trait": mood_profile.get("energy_label", "Balanced"),
        "evidence": evidence,
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
            "discovery_by_month": [],
            "artist_trends": [],
            "listening_diversity": 0.0,
            "taste_drift": 0.0,
            "familiarity_curve": [],
            "reminiscence_bump": {"available": False, "message": "No release years are available without enriched metadata."},
            "audio_features": [],
            "mood_profile": _build_mood_profile([], []),
            "analysis_categories": [],
            "listener_profile": profile,
            "research_signals": [],
        }

    artist_counter = Counter(_normalize_artist_name(event.artist) for event in events)
    track_counter = Counter((_normalize_artist_name(event.artist), event.track) for event in events)
    day_counter = Counter(event.listened_at.strftime("%A") for event in events)
    discovery_by_month = _build_discovery_by_month(events)

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
        "discovery_by_month": discovery_by_month,
        "artist_trends": [{
            "month": item["month"],
            "top_artists": item["top_artists"],
        } for item in discovery_by_month],
        "listening_diversity": _calculate_listening_diversity(artist_counter),
        "taste_drift": _build_taste_drift(events),
        "familiarity_curve": _build_familiarity_curve(events),
        "reminiscence_bump": {"available": False, "message": "No release years are available without enriched metadata."},
        "audio_features": [],
    }

    provider = audio_client or spotify_client
    if provider is not None:
        summary["audio_features"] = provider.enrich_tracks(events)

    summary["reminiscence_bump"] = _build_reminiscence_bump(summary["audio_features"])
    summary["mood_profile"] = _build_mood_profile(events, summary["audio_features"])
    summary["analysis_categories"] = _build_analysis_categories(events, summary["audio_features"])
    summary["listener_profile"] = _build_listener_profile(events, summary["mood_profile"], summary["analysis_categories"])
    summary["research_signals"] = [
        {
            "name": "Listening diversity",
            "value": summary["listening_diversity"],
            "method": "Normalized Shannon entropy over the artist distribution in this window.",
            "limit": "This is a descriptive measure, not a personality label.",
        },
        {
            "name": "Taste drift",
            "value": summary["taste_drift"],
            "method": "Average Jensen-Shannon divergence across monthly artist distributions.",
            "limit": "Only stable when there are at least two months of data.",
        },
        {
            "name": "Discovery rate",
            "value": discovery_by_month[-1]["new_artists"] if discovery_by_month else 0,
            "method": "New artists versus repeat artists by month.",
            "limit": "Short windows can exaggerate novelty or comfort.",
        },
        {
            "name": "Familiarity curve",
            "value": len(summary["familiarity_curve"]),
            "method": "Tracks repeated more than once are counted to show how replay-heavy your library is.",
            "limit": "This is not a direct measure of attachment or preference strength.",
        },
    ]
    return summary
