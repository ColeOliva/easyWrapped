from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Protocol

import requests


def _load_project_env() -> None:
    project_root = Path(__file__).resolve().parents[2]
    candidates = [project_root / ".env", Path.cwd() / ".env"]
    for candidate in candidates:
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = [part.strip() for part in line.split("=", 1)]
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip("\"'")


_load_project_env()


class AudioFeatureClient(Protocol):
    def enrich_tracks(self, events: Iterable) -> list[dict]:
        ...


def _coerce_float(value, default: float = 0.0) -> float:
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_audio_features(payload: dict, artist: str, track: str, album: str) -> dict:
    metrics = payload or {}
    return {
        "artist": artist,
        "track": track,
        "album": album,
        "tempo": round(_coerce_float(metrics.get("tempo", metrics.get("bpm", 0.0))), 2),
        "danceability": round(_coerce_float(metrics.get("danceability", 0.0)), 3),
        "energy": round(_coerce_float(metrics.get("energy", 0.0)), 3),
        "valence": round(_coerce_float(metrics.get("valence", 0.0)), 3),
        "acousticness": round(_coerce_float(metrics.get("acousticness", 0.0)), 3),
        "speechiness": round(_coerce_float(metrics.get("speechiness", 0.0)), 3),
        "instrumentalness": round(_coerce_float(metrics.get("instrumentalness", 0.0)), 3),
        "key": metrics.get("key") or metrics.get("musical_key"),
        "camelot": metrics.get("camelot") or metrics.get("camelot_code"),
        "release_date": metrics.get("release_date"),
    }


class JsonAudioFeatureClient:
    """Reads a local directory of saved JSON payloads keyed by artist/track name."""

    def __init__(self, data_dir: str | os.PathLike[str] | None = None):
        self.data_dir = Path(data_dir or os.getenv("AUDIO_FEATURES_DIR") or Path.cwd())

    @staticmethod
    def _slugify(value: str) -> str:
        cleaned = value.lower().strip()
        cleaned = "".join(ch if ch.isalnum() else "_" for ch in cleaned)
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")
        return cleaned.strip("_")

    def _candidate_paths(self, artist: str, track: str) -> list[Path]:
        artist_slug = self._slugify(artist)
        track_slug = self._slugify(track)
        return [
            self.data_dir / f"{artist_slug}__{track_slug}.json",
            self.data_dir / f"{track_slug}.json",
            self.data_dir / f"{artist_slug}_{track_slug}.json",
            self.data_dir / f"{artist_slug}.json",
        ]

    def _load_payload(self, artist: str, track: str) -> dict | None:
        for candidate in self._candidate_paths(artist, track):
            if not candidate.exists():
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if isinstance(payload, dict):
                return payload
        return None

    def enrich_tracks(self, events: Iterable) -> list[dict]:
        enriched: list[dict] = []
        for event in events:
            artist = str(getattr(event, "artist", "") or "")
            track = str(getattr(event, "track", "") or "")
            album = str(getattr(event, "album", "") or "")

            if not artist or not track:
                continue

            payload = self._load_payload(artist, track)
            if not payload:
                if not isinstance(payload, dict):
                    payload = {}
                continue

            enriched.append(_normalize_audio_features(payload, artist, track, album))
        return enriched


class LocalJsonAudioClient(JsonAudioFeatureClient):
    """Compatibility alias for the local/offline data path."""

    pass


class FreqblogAudioClient:
    """Minimal adapter for the Freqblog lookup endpoint used in local wrapped reports."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.freqblog.com",
        top_artists: int = 5,
        tracks_per_artist: int = 5,
        debug: bool = False,
    ):
        self.api_key = api_key or os.getenv("FREQBLOG_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.top_artists = max(1, int(top_artists))
        self.tracks_per_artist = max(1, int(tracks_per_artist))
        self.debug = bool(debug)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        return headers

    def _lookup_by_track(self, artist: str, track: str) -> dict | None:
        if not self.api_key or not artist or not track:
            if self.debug:
                print(f"Freqblog lookup skipped: missing key or blank artist/track (artist={bool(artist)}, track={bool(track)}, key={bool(self.api_key)})")
            return None

        params = {"track": track, "artist": artist}
        try:
            if self.debug:
                print(f"Freqblog lookup -> artist={artist} | track={track}")
            response = requests.get(f"{self.base_url}/lookup", params=params, headers=self._headers(), timeout=12)
        except (requests.RequestException, OSError, TimeoutError) as exc:
            if self.debug:
                print(f"Freqblog lookup failed for {artist} - {track}: {exc}")
            return None

        if response.status_code >= 400:
            if self.debug:
                print(f"Freqblog lookup returned status {response.status_code} for {artist} - {track}")
            return None

        payload = response.json()
        if not isinstance(payload, dict):
            if self.debug:
                print(f"Freqblog lookup returned non-dict payload for {artist} - {track}: {type(payload).__name__}")
            return None

        if self.debug:
            key_preview = list(payload.keys())[:8]
            print(f"Freqblog success for {artist} - {track}: status={response.status_code}, keys={key_preview}")
        return payload

    def enrich_tracks(self, events: Iterable) -> list[dict]:
        events = list(events)
        if not events:
            return []

        artist_counts = {}
        artist_track_counts: dict[str, dict[str, int]] = {}
        album_lookup: dict[tuple[str, str], str] = {}

        for event in events:
            artist = str(getattr(event, "artist", "") or "").strip()
            track = str(getattr(event, "track", "") or "").strip()
            album = str(getattr(event, "album", "") or "").strip()
            if not artist or not track:
                continue

            artist_key = artist.lower()
            track_key = track.lower()
            artist_counts[artist_key] = artist_counts.get(artist_key, 0) + 1
            artist_track_counts.setdefault(artist_key, {})
            artist_track_counts[artist_key][track_key] = artist_track_counts[artist_key].get(track_key, 0) + 1
            album_lookup.setdefault((artist_key, track_key), album)

        prioritized_artists = [
            artist for artist, _ in sorted(artist_counts.items(), key=lambda item: (-item[1], item[0]))[: self.top_artists]
        ]

        prioritized_pairs: list[tuple[str, str]] = []
        seen_pairs: set[tuple[str, str]] = set()
        for artist_key in prioritized_artists:
            tracks = sorted(
                artist_track_counts.get(artist_key, {}).items(),
                key=lambda item: (-item[1], item[0]),
            )[: self.tracks_per_artist]
            for track_key, _ in tracks:
                pair = (artist_key, track_key)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                prioritized_pairs.append(pair)

        enriched: list[dict] = []
        for artist_key, track_key in prioritized_pairs:
            artist_name = next((event.artist for event in events if str(event.artist).lower() == artist_key), artist_key.title())
            track_name = next((event.track for event in events if str(event.artist).lower() == artist_key and str(event.track).lower() == track_key), track_key.title())
            album_name = album_lookup.get((artist_key, track_key), "Unknown")
            payload = self._lookup_by_track(artist_name, track_name)
            if not payload:
                continue
            enriched.append(_normalize_audio_features(payload, artist_name, track_name, album_name))

        return enriched


def create_audio_client(provider: str | None = None, **kwargs) -> AudioFeatureClient | None:
    provider_name = (provider or os.getenv("AUDIO_PROVIDER") or "local").lower()

    if provider_name in {"none", "disabled"}:
        return None

    if provider_name in {"local", "json", "offline", "data"}:
        return LocalJsonAudioClient(data_dir=kwargs.get("data_dir") or os.getenv("AUDIO_FEATURES_DIR"))

    if provider_name in {"freqblog", "freqblog-music"}:
        return FreqblogAudioClient(
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url", "https://api.freqblog.com"),
            top_artists=kwargs.get("top_artists", 5),
            tracks_per_artist=kwargs.get("tracks_per_artist", 5),
            debug=bool(kwargs.get("debug", False)),
        )

    if provider_name in {"spotify", "sp"}:
        from .spotify_client import SpotifyAudioClient

        return SpotifyAudioClient(
            client_id=kwargs.get("client_id"),
            client_secret=kwargs.get("client_secret"),
            max_tracks=kwargs.get("max_tracks"),
            top_artists=kwargs.get("top_artists", 10),
            tracks_per_artist=kwargs.get("tracks_per_artist", 5),
        )

    return LocalJsonAudioClient(data_dir=kwargs.get("data_dir") or os.getenv("AUDIO_FEATURES_DIR"))
