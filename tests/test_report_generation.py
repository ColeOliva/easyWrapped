import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from easywrapper.report_generator import generate_report


class ReportGenerationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
