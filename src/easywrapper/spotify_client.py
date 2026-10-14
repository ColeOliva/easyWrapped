from __future__ import annotations

import os
from typing import Iterable, List

import requests


class SpotifyAudioClient:
    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self.client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Spotify credentials are missing. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET or pass them explicitly."
            )

        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token is not None:
            return self._token

        response = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=10,
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise RuntimeError("Spotify API did not return an access token.")

        self._token = token
        return self._token

    def _headers(self):
        return {"Authorization": f"Bearer {self._get_token()}"}

    def search_track(self, artist: str, track: str):
        query = f'artist:"{artist}" track:"{track}"'
        response = requests.get(
            "https://api.spotify.com/v1/search",
            headers=self._headers(),
            params={"q": query, "type": "track", "limit": 1},
            timeout=10,
        )
        response.raise_for_status()
        items = response.json().get("tracks", {}).get("items", [])
        if not items:
            return None
        return items[0]

    def get_audio_features(self, track_id: str):
        response = requests.get(
            f"https://api.spotify.com/v1/audio-features/{track_id}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def _melodic_complexity_estimate(self, features: dict) -> float:
        acousticness = float(features.get("acousticness", 0.0))
        instrumentalness = float(features.get("instrumentalness", 0.0))
        valence = float(features.get("valence", 0.5))
        speechiness = float(features.get("speechiness", 0.0))

        estimate = (
            (1.0 - acousticness) * 0.35
            + (1.0 - instrumentalness) * 0.25
            + valence * 0.2
            + speechiness * 0.2
        )
        return round(max(0.0, min(1.0, estimate)), 3)

    def enrich_tracks(self, events: Iterable) -> List[dict]:
        enriched: List[dict] = []
        seen = set()

        for event in events:
            key = (str(event.artist).lower(), str(event.track).lower())
            if key in seen:
                continue
            seen.add(key)

            try:
                spotify_track = self.search_track(event.artist, event.track)
                if spotify_track is None:
                    continue

                features = self.get_audio_features(spotify_track["id"])
            except (requests.RequestException, RuntimeError):
                continue

            enriched.append(
                {
                    "artist": event.artist,
                    "track": event.track,
                    "album": event.album,
                    "tempo": round(float(features.get("tempo", 0.0)), 2),
                    "danceability": round(float(features.get("danceability", 0.0)), 3),
                    "energy": round(float(features.get("energy", 0.0)), 3),
                    "valence": round(float(features.get("valence", 0.0)), 3),
                    "acousticness": round(float(features.get("acousticness", 0.0)), 3),
                    "speechiness": round(float(features.get("speechiness", 0.0)), 3),
                    "instrumentalness": round(float(features.get("instrumentalness", 0.0)), 3),
                    "melodic_complexity_estimate": self._melodic_complexity_estimate(features),
                }
            )

        return enriched
