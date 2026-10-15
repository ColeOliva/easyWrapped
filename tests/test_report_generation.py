import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from easywrapper.html_report import generate_html_report
from easywrapper.loader import build_wrapped_summary
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

        self.assertTrue(result.exists())
        self.assertIn("Update report", result.read_text(encoding="utf-8"))

        if output_path.exists():
            output_path.unlink()

    def test_spotify_client_loads_local_dotenv_credentials(self):
        original_cwd = Path.cwd()

        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text("SPOTIFY_CLIENT_ID=personal-client-id\nSPOTIFY_CLIENT_SECRET=personal-client-secret\n", encoding="utf-8")
            os.chdir(tmp_dir)
            try:
                client = __import__("easywrapper.spotify_client", fromlist=["SpotifyAudioClient"]).SpotifyAudioClient()
                self.assertEqual(client.client_id, "personal-client-id")
                self.assertEqual(client.client_secret, "personal-client-secret")
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
