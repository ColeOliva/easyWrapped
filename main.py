import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from easywrapper.html_report import generate_html_report
from easywrapper.loader import build_wrapped_summary, load_listening_history
from easywrapper.report_generator import generate_report
from easywrapper.spotify_client import SpotifyAudioClient


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a wrapped-style report from CSV listening history."
    )
    parser.add_argument("csv_path", help="Path to a CSV file with artist, album, track, and timestamp columns.")
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the report to. Defaults to a <name>_wrapped_report.pdf or .html file next to the CSV.",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate an interactive HTML report instead of a static PDF.",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the generated HTML report in the default browser.",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Optionally enrich tracks with personal-use Spotify audio features from a local .env file or explicit credentials.",
    )
    parser.add_argument(
        "--client-id",
        default=os.getenv("SPOTIFY_CLIENT_ID"),
        help="Optional personal Spotify client ID. If omitted, the app will look for SPOTIFY_CLIENT_ID in a local .env file.",
    )
    parser.add_argument(
        "--client-secret",
        default=os.getenv("SPOTIFY_CLIENT_SECRET"),
        help="Optional personal Spotify client secret. If omitted, the app will look for SPOTIFY_CLIENT_SECRET in a local .env file.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the structured JSON summary in addition to saving the wrapped report.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    events = load_listening_history(args.csv_path)
    spotify_client = None

    if args.enrich:
        try:
            spotify_client = SpotifyAudioClient(args.client_id, args.client_secret)
        except ValueError as exc:
            print(f"Warning: Spotify enrichment skipped: {exc}")
            spotify_client = None

    summary = build_wrapped_summary(events, spotify_client=spotify_client)

    if args.html:
        output_path = Path(args.output) if args.output else Path(args.csv_path).with_name(f"{Path(args.csv_path).stem}_wrapped_report.html")
        report_path = generate_html_report(
            summary,
            [{
                "artist": event.artist,
                "album": event.album,
                "track": event.track,
                "timestamp": event.listened_at.isoformat(),
            } for event in events],
            output_path,
        )
        print(f"Wrapped HTML report saved to: {report_path}")
        if args.open_browser:
            webbrowser.open(report_path.as_uri())
    else:
        output_path = Path(args.output) if args.output else Path(args.csv_path).with_name(f"{Path(args.csv_path).stem}_wrapped_report.pdf")
        report_path = generate_report(summary, output_path)
        print(f"Wrapped PDF report saved to: {report_path}")

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
