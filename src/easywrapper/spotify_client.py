from __future__ import annotations

import os
import ssl
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, List

import requests

SPOTIFY_REQUEST_TIMEOUT_SECONDS = 8
DEFAULT_TOP_ARTISTS = 10
DEFAULT_TRACKS_PER_ARTIST = 5
DEFAULT_MAX_TRACKS_TO_ENRICH = DEFAULT_TOP_ARTISTS * DEFAULT_TRACKS_PER_ARTIST


def _load_local_spotify_env() -> None:
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


_load_local_spotify_env()


class SpotifyAudioClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        max_tracks: int | None = None,
        top_artists: int = DEFAULT_TOP_ARTISTS,
        tracks_per_artist: int = DEFAULT_TRACKS_PER_ARTIST,
    ):
        self.client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Spotify credentials are missing. Add them to a local .env file in the project root or pass SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET explicitly."
            )

        self.top_artists = max(1, int(top_artists))
        self.tracks_per_artist = max(1, int(tracks_per_artist))
        self.max_tracks = max(1, int(max_tracks)) if max_tracks is not None else self.top_artists * self.tracks_per_artist
        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token is not None:
            return self._token

        try:
            response = requests.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                timeout=SPOTIFY_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except (requests.RequestException, OSError, TimeoutError, ssl.SSLError, KeyboardInterrupt) as exc:
            raise RuntimeError(f"Spotify authentication failed: {exc}") from exc

        token = response.json().get("access_token")
        if not token:
            raise RuntimeError("Spotify API did not return an access token.")

        self._token = token
        return self._token

    def _headers(self):
        return {"Authorization": f"Bearer {self._get_token()}"}

    def _request_with_retry(self, method: str, url: str, **kwargs):
        last_exception = None
        for attempt in range(3):
            try:
                response = requests.request(method, url, **kwargs)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    sleep_seconds = float(retry_after) if retry_after is not None else 2 ** attempt
                    time.sleep(sleep_seconds)
                    continue
                response.raise_for_status()
                return response
            except requests.HTTPError as exc:
                status_code = getattr(exc.response, "status_code", None)
                if status_code == 429:
                    retry_after = exc.response.headers.get("Retry-After") if exc.response is not None else None
                    time.sleep(float(retry_after) if retry_after is not None else 2 ** attempt)
                    last_exception = exc
                    continue
                raise RuntimeError(f"Spotify API request failed for {url}: {exc}") from exc
            except (requests.RequestException, OSError, TimeoutError, ssl.SSLError, KeyboardInterrupt) as exc:
                last_exception = exc
                raise RuntimeError(f"Spotify API request failed for {url}: {exc}") from exc

        if last_exception is not None:
            raise RuntimeError(f"Spotify API request failed for {url}: {last_exception}") from last_exception
        raise RuntimeError(f"Spotify API request failed for {url}: no response received")

    def search_track(self, artist: str, track: str):
        query = f'artist:"{artist}" track:"{track}"'
        try:
            headers = self._headers()
            response = self._request_with_retry(
                "GET",
                "https://api.spotify.com/v1/search",
                headers=headers,
                params={"q": query, "type": "track", "limit": 1},
                timeout=SPOTIFY_REQUEST_TIMEOUT_SECONDS,
            )
        except (requests.RequestException, OSError, TimeoutError, ssl.SSLError, KeyboardInterrupt, RuntimeError) as exc:
            raise RuntimeError(f"Spotify track search failed for '{artist} - {track}': {exc}") from exc

        items = response.json().get("tracks", {}).get("items", [])
        if not items:
            return None
        return items[0]

    def get_audio_features(self, track_id: str):
        try:
            headers = self._headers()
            response = self._request_with_retry(
                "GET",
                f"https://api.spotify.com/v1/audio-features/{track_id}",
                headers=headers,
                timeout=SPOTIFY_REQUEST_TIMEOUT_SECONDS,
            )
        except (requests.RequestException, OSError, TimeoutError, ssl.SSLError, KeyboardInterrupt, RuntimeError) as exc:
            raise RuntimeError(f"Spotify audio feature lookup failed for track {track_id}: {exc}") from exc

        return response.json()

    def get_audio_features_batch(self, track_ids: Iterable[str]) -> dict[str, dict]:
        unique_ids = list(dict.fromkeys(str(track_id).strip() for track_id in track_ids if str(track_id).strip()))
        features_by_id: dict[str, dict] = {}
        if not unique_ids:
            return features_by_id

        for start in range(0, len(unique_ids), 50):
            batch = unique_ids[start : start + 50]
            try:
                headers = self._headers()
                response = self._request_with_retry(
                    "GET",
                    "https://api.spotify.com/v1/audio-features",
                    headers=headers,
                    params={"ids": ",".join(batch)},
                    timeout=SPOTIFY_REQUEST_TIMEOUT_SECONDS,
                )
            except (requests.RequestException, OSError, TimeoutError, ssl.SSLError, KeyboardInterrupt, RuntimeError):
                continue

            for features in response.json().get("audio_features", []) or []:
                if features and features.get("id"):
                    features_by_id[features["id"]] = features

        return features_by_id

    def enrich_tracks(self, events: Iterable) -> List[dict]:
        enriched: List[dict] = []
        seen = set()
        events = list(events)

        if not events:
            return enriched

        artist_counts = Counter(str(event.artist).lower() for event in events)
        top_artists = [artist for artist, _ in artist_counts.most_common(self.top_artists)]

        artist_track_counts: dict[str, Counter] = {artist: Counter() for artist in top_artists}
        for event in events:
            artist_key = str(event.artist).lower()
            if artist_key not in artist_track_counts:
                continue
            artist_track_counts[artist_key][str(event.track).lower()] += 1

        prioritized_keys: list[tuple[str, str]] = []
        for artist in top_artists:
            track_names = [track for track, _ in artist_track_counts.get(artist, Counter()).most_common(self.tracks_per_artist)]
            for track_name in track_names:
                prioritized_keys.append((artist, track_name))

        prioritized_keys = prioritized_keys[: self.max_tracks]
        prioritized_set = set(prioritized_keys)
        track_lookup: dict[str, tuple[str, str, str]] = {}

        for event in events:
            key = (str(event.artist).lower(), str(event.track).lower())
            if key not in prioritized_set or key in seen:
                continue
            seen.add(key)

            try:
                spotify_track = self.search_track(event.artist, event.track)
                if spotify_track is None:
                    continue
            except (Exception, KeyboardInterrupt):
                continue

            if not spotify_track.get("id"):
                continue
            track_lookup[spotify_track["id"]] = (event.artist, event.track, event.album)

        features_by_id = self.get_audio_features_batch(track_lookup.keys())
        if not features_by_id and track_lookup:
            for track_id, _ in track_lookup.items():
                try:
                    features_by_id[track_id] = self.get_audio_features(track_id)
                except (Exception, KeyboardInterrupt):
                    continue

        for track_id, (artist, track, album) in track_lookup.items():
            features = features_by_id.get(track_id)
            if features is None:
                continue

            enriched.append(
                {
                    "artist": artist,
                    "track": track,
                    "album": album,
                    "tempo": round(float(features.get("tempo", 0.0)), 2),
                    "danceability": round(float(features.get("danceability", 0.0)), 3),
                    "energy": round(float(features.get("energy", 0.0)), 3),
                    "valence": round(float(features.get("valence", 0.0)), 3),
                    "acousticness": round(float(features.get("acousticness", 0.0)), 3),
                    "speechiness": round(float(features.get("speechiness", 0.0)), 3),
                    "instrumentalness": round(float(features.get("instrumentalness", 0.0)), 3),
                }
            )

        return enriched
