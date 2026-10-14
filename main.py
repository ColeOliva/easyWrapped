import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from easywrapper.loader import build_wrapped_summary, load_listening_history
from easywrapper.spotify_client import SpotifyAudioClient


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a basic wrapped summary from CSV listening history."
    )
    parser.add_argument("csv_path", help="Path to a CSV file with artist, album, track, and timestamp columns.")
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Optionally enrich tracks with Spotify audio features.",
    )
    parser.add_argument(
        "--client-id",
        default=os.getenv("SPOTIFY_CLIENT_ID"),
        help="Optional Spotify client ID (or set SPOTIFY_CLIENT_ID in the environment).",
    )
    parser.add_argument(
        "--client-secret",
        default=os.getenv("SPOTIFY_CLIENT_SECRET"),
        help="Optional Spotify client secret (or set SPOTIFY_CLIENT_SECRET in the environment).",
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
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
