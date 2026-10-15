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

from easywrapper.audio_enrichment import create_audio_client
from easywrapper.html_report import generate_html_report
from easywrapper.loader import build_wrapped_summary, load_listening_history
from easywrapper.report_generator import generate_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a wrapped-style report from CSV listening history."
    )
    parser.add_argument("csv_path", help="Path to a CSV file with artist, album, track, and timestamp columns.")
    parser.add_argument(
        "--timezone",
        default=os.getenv("LOCAL_TIMEZONE", "UTC"),
        help="IANA timezone to apply to naive timestamps (for example America/New_York or Europe/London). Defaults to UTC unless set in LOCAL_TIMEZONE.",
    )
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
        help="Optionally enrich tracks with audio features using the configured provider (Spotify or Freqblog).",
    )
    parser.add_argument(
        "--audio-provider",
        choices=["spotify", "freqblog", "local"],
        default=os.getenv("AUDIO_PROVIDER", "local"),
        help="Audio-features provider to use for enrichment. Defaults to local/off unless --enrich is set.",
    )
    parser.add_argument(
        "--freqblog-api-key",
        default=os.getenv("FREQBLOG_API_KEY"),
        help="Optional Freqblog API key. Only used when the Freqblog provider is selected.",
    )
    parser.add_argument(
        "--top-artists",
        type=int,
        default=5,
        help="Enrich the top N artists by play count, then choose up to --tracks-per-artist tracks from each artist.",
    )
    parser.add_argument(
        "--tracks-per-artist",
        type=int,
        default=5,
        help="How many tracks from each artist to enrich when using artist-first selection. The default is 5 tracks for each of the top 5 artists.",
    )
    parser.add_argument(
        "--max-enrich",
        type=int,
        default=None,
        help="Optional final cap on total enriched tracks. If omitted, it defaults to top_artists * tracks_per_artist.",
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
    parser.add_argument(
        "--debug-api",
        action="store_true",
        help="Print each audio lookup request and a short response summary so you can confirm the provider is receiving data.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    events = load_listening_history(args.csv_path, timezone_name=args.timezone)
    audio_client = None

    if args.enrich:
        try:
            audio_client = create_audio_client(
                args.audio_provider,
                api_key=args.freqblog_api_key,
                client_id=args.client_id,
                client_secret=args.client_secret,
                max_tracks=args.max_enrich,
                top_artists=args.top_artists,
                tracks_per_artist=args.tracks_per_artist,
                debug=args.debug_api,
            )
        except ValueError as exc:
            print(f"Warning: audio enrichment skipped: {exc}")
            audio_client = None

    summary = build_wrapped_summary(events, audio_client=audio_client)

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
