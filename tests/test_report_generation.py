import importlib
import json
import os
import ssl
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from easywrapper.html_report import generate_html_report
from easywrapper.loader import build_wrapped_summary, load_listening_history
from easywrapper.models import ListeningEvent
from easywrapper.report_generator import generate_report


class ReportGenerationTests(unittest.TestCase):
    def test_build_wrapped_summary_includes_time_analysis(self):
        events = [
            ListeningEvent("Laufey", "Bewitched Hand", "Dreamer", datetime(2025, 1, 1, 21, 0)),
            ListeningEvent("Laufey", "Bewitched Hand", "Like the Movies", datetime(2025, 1, 1, 21, 15)),
            ListeningEvent("Faye Webster", "Underdressed at the Symphony", "Lifetime", datetime(2025, 1, 2, 10, 0)),
            ListeningEvent("Faye Webster", "Underdressed at the Symphony", "But Not Kiss", datetime(2025, 1, 2, 9, 30)),
        ]

        summary = build_wrapped_summary(events)

        self.assertIn("time_analysis", summary)
        self.assertIn("peak_hour", summary["time_analysis"])
        self.assertIn("monthly_trend", summary)
        self.assertIn("day_part", summary["time_analysis"])
        self.assertIn("listener_profile", summary)
        self.assertIn("mood_profile", summary)
        self.assertIn("analysis_categories", summary)

    def test_generate_report_creates_pdf(self):
        summary = {
            "total_tracks": 12,
            "unique_artists": 4,
            "top_artists": [
                {"artist": "Laufey", "plays": 6},
                {"artist": "Faye Webster", "plays": 3},
            ],
            "top_tracks": [
                {"artist": "Laufey", "track": "Misty", "plays": 4},
            ],
            "most_active_day": "Friday",
            "listening_window": {"first": "2025-01-01T00:00:00", "last": "2025-01-07T00:00:00"},
            "time_analysis": {
                "peak_hour": "21:00",
                "peak_hour_count": 4,
                "day_part": "Evening",
                "day_of_week": {"Friday": 6, "Tuesday": 4},
                "hourly_distribution": [{"hour": "21", "count": 4}],
            },
            "monthly_trend": [{"month": "2025-01", "plays": 12}],
            "audio_features": [],
        }

        output_path = Path("test_wrapped_report.pdf")
        if output_path.exists():
            output_path.unlink()

        result = generate_report(summary, output_path)

        self.assertTrue(result.exists())
        self.assertGreater(result.stat().st_size, 1000)

        if output_path.exists():
            output_path.unlink()

    def test_generate_html_report_creates_dashboard(self):
        summary = {
            "total_tracks": 5,
            "unique_artists": 2,
            "top_artists": [{"artist": "Laufey", "plays": 3}],
            "top_tracks": [{"artist": "Laufey", "track": "Misty", "plays": 2}],
            "most_active_day": "Friday",
            "listening_window": {"first": "2025-01-01T00:00:00", "last": "2025-01-07T00:00:00"},
            "time_analysis": {"peak_hour": "21:00", "peak_hour_count": 2, "day_part": "Evening", "day_of_week": {"Friday": 5}, "hourly_distribution": [{"hour": "21:00", "count": 2}]},
            "monthly_trend": [{"month": "2025-01", "plays": 5}],
            "audio_features": [],
        }
        events = [{"artist": "Laufey", "album": "Bewitched Hand", "track": "Misty", "timestamp": "2025-01-03T21:30:00"}]

        output_path = Path("test_wrapped_report.html")
        if output_path.exists():
            output_path.unlink()

        result = generate_html_report(summary, events, output_path)
        rendered = result.read_text(encoding="utf-8")

        self.assertTrue(result.exists())
        self.assertIn("Update report", rendered)
        self.assertIn("Top track", rendered)
        self.assertIn("Listening window", rendered)

        if output_path.exists():
            output_path.unlink()

    def test_spotify_client_loads_local_dotenv_credentials(self):
        existing_client_id = os.environ.pop("SPOTIFY_CLIENT_ID", None)
        existing_client_secret = os.environ.pop("SPOTIFY_CLIENT_SECRET", None)

        try:
            module = __import__("easywrapper.spotify_client", fromlist=["SpotifyAudioClient"])
            module = importlib.reload(module)
            client = module.SpotifyAudioClient()

            expected_env = {}
            for raw_line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = [part.strip() for part in line.split("=", 1)]
                expected_env[key] = value.strip().strip("\"'")

            self.assertEqual(client.client_id, expected_env["SPOTIFY_CLIENT_ID"])
            self.assertEqual(client.client_secret, expected_env["SPOTIFY_CLIENT_SECRET"])
        finally:
            if existing_client_id is not None:
                os.environ["SPOTIFY_CLIENT_ID"] = existing_client_id
            if existing_client_secret is not None:
                os.environ["SPOTIFY_CLIENT_SECRET"] = existing_client_secret

    def test_spotify_client_enrich_tracks_handles_network_failures(self):
        from easywrapper.spotify_client import SpotifyAudioClient

        client = SpotifyAudioClient("client-id", "client-secret")
        client.search_track = lambda artist, track: {"id": "abc123"}
        client.get_audio_features = lambda track_id: (_ for _ in ()).throw(OSError("network unreachable"))

        events = [
            ListeningEvent("Laufey", "Bewitched Hand", "Dreamer", datetime(2025, 1, 1, 21, 0)),
            ListeningEvent("Faye Webster", "Underdressed at the Symphony", "Lifetime", datetime(2025, 1, 2, 10, 0)),
        ]

        self.assertEqual(client.enrich_tracks(events), [])

    def test_spotify_client_enrich_tracks_handles_header_auth_failures(self):
        from easywrapper.spotify_client import SpotifyAudioClient

        client = SpotifyAudioClient("client-id", "client-secret")
        client._headers = lambda: (_ for _ in ()).throw(RuntimeError("token request failed"))

        events = [
            ListeningEvent("Laufey", "Bewitched Hand", "Dreamer", datetime(2025, 1, 1, 21, 0)),
        ]

        self.assertEqual(client.enrich_tracks(events), [])

    def test_spotify_client_enrich_tracks_handles_ssl_failures(self):
        from easywrapper.spotify_client import SpotifyAudioClient

        client = SpotifyAudioClient("client-id", "client-secret")
        client._headers = lambda: (_ for _ in ()).throw(ssl.SSLError("tls handshake failed"))

        events = [
            ListeningEvent("Faye Webster", "Underdressed at the Symphony", "Lifetime", datetime(2025, 1, 2, 10, 0)),
        ]

        self.assertEqual(client.enrich_tracks(events), [])

    def test_spotify_client_enrich_tracks_handles_keyboard_interrupts(self):
        from easywrapper.spotify_client import SpotifyAudioClient

        client = SpotifyAudioClient("client-id", "client-secret")
        client.search_track = lambda artist, track: (_ for _ in ()).throw(KeyboardInterrupt())

        events = [
            ListeningEvent("Laufey", "Bewitched Hand", "Dreamer", datetime(2025, 1, 1, 21, 0)),
        ]

        self.assertEqual(client.enrich_tracks(events), [])

    def test_spotify_client_enrich_tracks_respects_max_track_limit(self):
        from easywrapper.spotify_client import SpotifyAudioClient

        client = SpotifyAudioClient("client-id", "client-secret", max_tracks=2)
        calls = []

        def fake_search(artist, track):
            calls.append((artist, track))
            return {"id": f"id-{artist}-{track}"}

        def fake_get(track_id):
            return {
                "tempo": 120.0,
                "danceability": 0.7,
                "energy": 0.8,
                "valence": 0.6,
                "acousticness": 0.2,
                "speechiness": 0.1,
                "instrumentalness": 0.05,
            }

        client.search_track = fake_search
        client.get_audio_features = fake_get

        events = [
            ListeningEvent("Laufey", "Bewitched Hand", "Dreamer", datetime(2025, 1, 1, 21, 0)),
            ListeningEvent("Laufey", "Bewitched Hand", "Dreamer", datetime(2025, 1, 1, 21, 5)),
            ListeningEvent("Laufey", "Bewitched Hand", "Like the Movies", datetime(2025, 1, 2, 22, 0)),
            ListeningEvent("Faye Webster", "Underdressed at the Symphony", "Lifetime", datetime(2025, 1, 3, 10, 0)),
        ]

        result = client.enrich_tracks(events)

        self.assertEqual(len(result), 2)
        self.assertEqual(len(calls), 2)

    def test_audio_provider_adapter_supports_non_spotify_enrichment(self):
        class FakeClient:
            def enrich_tracks(self, events):
                return [{
                    "artist": "Laufey",
                    "track": "Dreamer",
                    "album": "Bewitched",
                    "tempo": 101.5,
                    "danceability": 0.61,
                    "energy": 0.74,
                    "valence": 0.8,
                    "acousticness": 0.2,
                    "speechiness": 0.1,
                    "instrumentalness": 0.05,
                }]

        events = [
            ListeningEvent("Laufey", "Bewitched", "Dreamer", datetime(2025, 1, 1, 21, 0)),
        ]

        summary = build_wrapped_summary(events, spotify_client=FakeClient())

        self.assertEqual(summary["audio_features"][0]["artist"], "Laufey")
        self.assertEqual(summary["audio_features"][0]["tempo"], 101.5)

    def test_load_listening_history_handles_duplicates_timezone_and_bad_rows(self):
        csv_path = Path("test_duplicate_csv.csv")
        csv_path.write_text(
            "Laufey, Bewitched Hand, Dreamer, 2025-01-01 21:00:00\n"
            "Laufey, Bewitched Hand, Dreamer, 2025-01-01 21:00:00\n"
            "Faye Webster, Underdressed, Lifetime, not-a-time\n"
            "Faye Webster feat. Yannis, Underdressed, But Not Kiss, 2025-01-02 09:30:00\n",
            encoding="utf-8",
        )
        try:
            events = load_listening_history(csv_path, timezone_name="UTC")
        finally:
            if csv_path.exists():
                csv_path.unlink()

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].artist, "Laufey")
        self.assertEqual(events[1].artist, "Faye Webster")
        self.assertEqual(events[0].listened_at.tzinfo is not None, True)

    def test_wrapped_summary_has_diversity_and_discovery_stats(self):
        events = [
            ListeningEvent("Laufey", "Bewitched Hand", "Dreamer", datetime(2025, 1, 1, 21, 0)),
            ListeningEvent("Laufey", "Bewitched Hand", "Dreamer", datetime(2025, 1, 2, 21, 0)),
            ListeningEvent("Faye Webster", "Underdressed at the Symphony", "Lifetime", datetime(2025, 1, 3, 10, 0)),
            ListeningEvent("Faye Webster feat. Yannis", "Underdressed at the Symphony", "But Not Kiss", datetime(2025, 1, 4, 9, 30)),
        ]

        summary = build_wrapped_summary(events)

        self.assertIn("listening_diversity", summary)
        self.assertIn("discovery_by_month", summary)
        self.assertEqual(summary["discovery_by_month"][0]["new_artists"], 2)

    def test_summary_includes_research_signals_and_taste_drift(self):
        events = [
            ListeningEvent("Laufey", "Bewitched Hand", "Dreamer", datetime(2025, 1, 1, 21, 0)),
            ListeningEvent("Laufey", "Bewitched Hand", "Dreamer", datetime(2025, 1, 2, 21, 0)),
            ListeningEvent("Faye Webster", "Underdressed at the Symphony", "Lifetime", datetime(2025, 2, 1, 10, 0)),
            ListeningEvent("Faye Webster", "Underdressed at the Symphony", "Lifetime", datetime(2025, 2, 2, 10, 0)),
            ListeningEvent("The National", "Trouble Will Find Me", "Slow Show", datetime(2025, 2, 3, 18, 0)),
        ]

        summary = build_wrapped_summary(events)

        self.assertIn("research_signals", summary)
        self.assertIn("taste_drift", summary)
        self.assertIn("familiarity_curve", summary)
        self.assertGreaterEqual(summary["taste_drift"], 0.0)
        self.assertIsInstance(summary["familiarity_curve"], list)

    def test_local_json_audio_provider_matches_track_payloads_without_live_requests(self):
        from easywrapper.audio_enrichment import LocalJsonAudioClient

        with tempfile.TemporaryDirectory() as tmpdir:
            track = {
                "track_name": "Uptown Funk",
                "artist_name": "Mark Ronson featuring Bruno Mars",
                "album_name": "Uptown Special",
                "release_date": "2015-01-13",
                "bpm": 116.69,
                "key": "C-Major",
                "camelot": "8B",
                "energy": 0.451,
                "danceability": 0.851,
                "valence": 0.503,
            }
            json_path = Path(tmpdir) / "uptown_funk.json"
            json_path.write_text(json.dumps(track), encoding="utf-8")

            client = LocalJsonAudioClient(data_dir=tmpdir)
            events = [
                ListeningEvent("Mark Ronson featuring Bruno Mars", "Uptown Special", "Uptown Funk", datetime(2025, 1, 1, 21, 0)),
            ]

            result = client.enrich_tracks(events)

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["tempo"], 116.69)
            self.assertEqual(result[0]["danceability"], 0.851)
            self.assertEqual(result[0]["track"], "Uptown Funk")

    def test_spotify_client_retries_after_rate_limit(self):
        from easywrapper.spotify_client import SpotifyAudioClient

        client = SpotifyAudioClient("client-id", "client-secret")
        client._token = "test-token"

        class FakeResponse:
            def __init__(self, status_code, payload=None, headers=None):
                self.status_code = status_code
                self._payload = payload or {}
                self.headers = headers or {}

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.HTTPError(f"HTTP {self.status_code}")

            def json(self):
                return self._payload

        with patch("easywrapper.spotify_client.requests.request") as mock_request:
            mock_request.side_effect = [
                FakeResponse(429, {}, {"Retry-After": "0"}),
                FakeResponse(200, {"tracks": {"items": [{"id": "abc123"}]}}),
            ]

            track = client.search_track("Laufey", "Dreamer")

            self.assertEqual(track["id"], "abc123")
            self.assertEqual(mock_request.call_count, 2)

    def test_spotify_client_batches_audio_features_lookup(self):
        from easywrapper.spotify_client import SpotifyAudioClient

        client = SpotifyAudioClient("client-id", "client-secret")
        client._token = "test-token"

        class FakeResponse:
            def __init__(self, status_code, payload=None, headers=None):
                self.status_code = status_code
                self._payload = payload or {}
                self.headers = headers or {}

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.HTTPError(f"HTTP {self.status_code}")

            def json(self):
                return self._payload

        with patch("easywrapper.spotify_client.requests.request") as mock_request:
            mock_request.return_value = FakeResponse(
                200,
                {
                    "audio_features": [
                        {"id": "abc123", "tempo": 110.0, "danceability": 0.7},
                        {"id": "def456", "tempo": 120.0, "danceability": 0.8},
                    ]
                },
            )

            result = client.get_audio_features_batch(["abc123", "def456"])

            self.assertEqual(result["abc123"]["tempo"], 110.0)
            self.assertEqual(mock_request.call_count, 1)
            self.assertEqual(mock_request.call_args.kwargs["params"]["ids"], "abc123,def456")

    def test_spotify_client_enrich_tracks_prioritizes_top_artists_then_top_tracks(self):
        from easywrapper.spotify_client import SpotifyAudioClient

        client = SpotifyAudioClient("client-id", "client-secret", top_artists=2, tracks_per_artist=2)
        calls = []

        def fake_search(artist, track):
            calls.append((artist, track))
            return {"id": f"id-{artist}-{track}"}

        def fake_get(track_id):
            return {
                "tempo": 120.0,
                "danceability": 0.7,
                "energy": 0.8,
                "valence": 0.6,
                "acousticness": 0.2,
                "speechiness": 0.1,
                "instrumentalness": 0.05,
            }

        client.search_track = fake_search
        client.get_audio_features = fake_get

        events = [
            ListeningEvent("Artist A", "Album 1", "Song A1", datetime(2025, 1, 1, 21, 0)),
            ListeningEvent("Artist A", "Album 1", "Song A1", datetime(2025, 1, 1, 21, 5)),
            ListeningEvent("Artist A", "Album 1", "Song A2", datetime(2025, 1, 1, 21, 10)),
            ListeningEvent("Artist A", "Album 1", "Song A2", datetime(2025, 1, 1, 21, 15)),
            ListeningEvent("Artist A", "Album 1", "Song A3", datetime(2025, 1, 1, 21, 20)),
            ListeningEvent("Artist B", "Album 2", "Song B1", datetime(2025, 1, 2, 21, 0)),
            ListeningEvent("Artist B", "Album 2", "Song B1", datetime(2025, 1, 2, 21, 5)),
            ListeningEvent("Artist B", "Album 2", "Song B2", datetime(2025, 1, 2, 21, 10)),
            ListeningEvent("Artist C", "Album 3", "Song C1", datetime(2025, 1, 3, 21, 0)),
            ListeningEvent("Artist C", "Album 3", "Song C1", datetime(2025, 1, 3, 21, 5)),
            ListeningEvent("Artist C", "Album 3", "Song C1", datetime(2025, 1, 3, 21, 10)),
            ListeningEvent("Artist C", "Album 3", "Song C1", datetime(2025, 1, 3, 21, 15)),
            ListeningEvent("Artist C", "Album 3", "Song C1", datetime(2025, 1, 3, 21, 20)),
        ]

        result = client.enrich_tracks(events)

        self.assertEqual(len(result), 3)
        self.assertEqual({(item["artist"], item["track"]) for item in result}, {("Artist A", "Song A1"), ("Artist A", "Song A2"), ("Artist C", "Song C1")})
        self.assertEqual(len(calls), 3)

    def test_freqblog_client_uses_top_five_artists_and_top_five_tracks(self):
        from easywrapper.audio_enrichment import FreqblogAudioClient

        events = [
            ListeningEvent("Artist A", "Album 1", "Song A1", datetime(2025, 1, 1, 21, 0)),
            ListeningEvent("Artist A", "Album 1", "Song A1", datetime(2025, 1, 1, 21, 5)),
            ListeningEvent("Artist A", "Album 1", "Song A2", datetime(2025, 1, 1, 21, 10)),
            ListeningEvent("Artist A", "Album 1", "Song A3", datetime(2025, 1, 1, 21, 15)),
            ListeningEvent("Artist A", "Album 1", "Song A4", datetime(2025, 1, 1, 21, 20)),
            ListeningEvent("Artist A", "Album 1", "Song A5", datetime(2025, 1, 1, 21, 25)),
            ListeningEvent("Artist A", "Album 1", "Song A6", datetime(2025, 1, 1, 21, 30)),
            ListeningEvent("Artist B", "Album 2", "Song B1", datetime(2025, 1, 2, 21, 0)),
            ListeningEvent("Artist B", "Album 2", "Song B2", datetime(2025, 1, 2, 21, 5)),
            ListeningEvent("Artist C", "Album 3", "Song C1", datetime(2025, 1, 3, 21, 0)),
            ListeningEvent("Artist C", "Album 3", "Song C2", datetime(2025, 1, 3, 21, 5)),
            ListeningEvent("Artist D", "Album 4", "Song D1", datetime(2025, 1, 4, 21, 0)),
            ListeningEvent("Artist E", "Album 5", "Song E1", datetime(2025, 1, 5, 21, 0)),
            ListeningEvent("Artist F", "Album 6", "Song F1", datetime(2025, 1, 6, 21, 0)),
            ListeningEvent("Artist G", "Album 7", "Song G1", datetime(2025, 1, 7, 21, 0)),
        ]

        client = FreqblogAudioClient(api_key="demo-key")
        calls = []

        class FakeResponse:
            def __init__(self, payload):
                self.status_code = 200
                self._payload = payload
            def json(self):
                return self._payload

        def fake_get(url, params=None, headers=None, timeout=None):
            calls.append((url, params, headers))
            track = params["track"] if params else ""
            artist = params["artist"] if params else ""
            return FakeResponse({
                "track_name": track,
                "artist_name": artist,
                "bpm": 110.0,
                "energy": 0.75,
                "danceability": 0.82,
                "valence": 0.64,
                "acousticness": 0.3,
                "speechiness": 0.2,
                "instrumentalness": 0.1,
            })

        with patch("easywrapper.audio_enrichment.requests.get", side_effect=fake_get):
            result = client.enrich_tracks(events)

        self.assertLessEqual(len(result), 25)
        self.assertGreaterEqual(len(calls), 5)
        self.assertLessEqual(len(calls), 25)
        artists_requested = {call[1]["artist"] for call in calls}
        self.assertIn("Artist A", artists_requested)
        self.assertNotIn("Artist G", artists_requested)

    def test_freqblog_audio_normalizer_handles_none_feature_fields(self):
        from easywrapper.audio_enrichment import _normalize_audio_features

        result = _normalize_audio_features(
            {
                "tempo": 110.0,
                "danceability": 0.82,
                "energy": 0.75,
                "valence": 0.64,
                "acousticness": 0.3,
                "speechiness": None,
                "instrumentalness": None,
            },
            "Artist A",
            "Song A1",
            "Album 1",
        )

        self.assertEqual(result["tempo"], 110.0)
        self.assertEqual(result["speechiness"], 0.0)
        self.assertEqual(result["instrumentalness"], 0.0)


if __name__ == "__main__":
    unittest.main()
