from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Protocol

import requests


class AudioFeatureClient(Protocol):
    def enrich_tracks(self, events: Iterable) -> list[dict]:
        ...


def _normalize_audio_features(payload: dict, artist: str, track: str, album: str) -> dict:
    metrics = payload or {}
    return {
        "artist": artist,
        "track": track,
        "album": album,
        "tempo": round(float(metrics.get("tempo", metrics.get("bpm", 0.0))), 2),
        "danceability": round(float(metrics.get("danceability", 0.0)), 3),
        "energy": round(float(metrics.get("energy", 0.0)), 3),
        "valence": round(float(metrics.get("valence", 0.0)), 3),
        "acousticness": round(float(metrics.get("acousticness", 0.0)), 3),
        "speechiness": round(float(metrics.get("speechiness", 0.0)), 3),
        "instrumentalness": round(float(metrics.get("instrumentalness", 0.0)), 3),
        "melodic_complexity_estimate": _estimate_melodic_complexity(metrics),
        "key": metrics.get("key") or metrics.get("musical_key"),
        "camelot": metrics.get("camelot") or metrics.get("camelot_code"),
        "release_date": metrics.get("release_date"),
    }


def _estimate_melodic_complexity(metrics: dict) -> float:
    acousticness = float(metrics.get("acousticness", 0.0))
    instrumentalness = float(metrics.get("instrumentalness", 0.0))
    valence = float(metrics.get("valence", 0.5))
    speechiness = float(metrics.get("speechiness", 0.0))

    estimate = (
        (1.0 - acousticness) * 0.35
        + (1.0 - instrumentalness) * 0.25
        + valence * 0.2
        + speechiness * 0.2
    )
    return round(max(0.0, min(1.0, estimate)), 3)


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
    """Minimal adapter for a Spotify-shaped audio-features provider.

    This intentionally keeps the surface area small and is designed around a
    local CSV wrapped app, where the data source is already known and the API is
    only used to enrich a limited subset of tracks.
    """

    def __init__(self, api_key: str | None = None, base_url: str = "https://api.freqblog.com"):
        self.api_key = api_key or os.getenv("FREQBLOG_API_KEY")
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _lookup_by_isrc(self, isrc: str) -> dict | None:
        if not isrc:
            return None

        url = f"{self.base_url}/v1/audio-features/{isrc}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=12)
        except (requests.RequestException, OSError, TimeoutError):
            return None

        if response.status_code >= 400:
            return None

        payload = response.json()
        if not isinstance(payload, dict):
            return None
        return payload

    def enrich_tracks(self, events: Iterable) -> list[dict]:
        enriched: list[dict] = []
        for event in events:
            isrc = getattr(event, "isrc", None) or getattr(event, "external_isrc", None)
            if not isrc:
                continue

            features = self._lookup_by_isrc(str(isrc))
            if not features:
                continue

            enriched.append(
                _normalize_audio_features(
                    features,
                    artist=str(getattr(event, "artist", "") or "Unknown"),
                    track=str(getattr(event, "track", "") or "Unknown"),
                    album=str(getattr(event, "album", "") or "Unknown"),
                )
            )

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
