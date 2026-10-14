from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _safe_value(value):
    if value is None:
        return "N/A"
    return str(value)


def _build_header(summary: dict) -> list:
    total_tracks = summary.get("total_tracks", 0)
    unique_artists = summary.get("unique_artists", 0)
    top_artist = (summary.get("top_artists") or [{}])[0].get("artist", "N/A")
    most_active_day = summary.get("most_active_day") or "N/A"

    return [
        [
            ("Total listens", str(total_tracks)),
            ("Unique artists", str(unique_artists)),
        ],
        [
            ("Top artist", _safe_value(top_artist)),
            ("Most active day", _safe_value(most_active_day)),
        ],
    ]


def _make_table(rows: list[list[str]], col_widths: list[float]) -> Table:
    table = Table(rows, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1DB954")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#E5E7EB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def generate_report(summary: dict, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "WrappedTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#111827"),
        spaceAfter=12,
    )
    subtitle_style = ParagraphStyle(
        "WrappedSubtitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#6B7280"),
        spaceAfter=18,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=18,
        textColor=colors.HexColor("#111827"),
        spaceBefore=12,
        spaceAfter=8,
    )

    first_seen = summary.get("listening_window", {}).get("first") or "N/A"
    last_seen = summary.get("listening_window", {}).get("last") or "N/A"

    story = []
    story.append(Paragraph("YOUR WRAPPED", title_style))
    story.append(
        Paragraph(
            f"Listening range: {first_seen} to {last_seen}",
            subtitle_style,
        )
    )

    cards = []
    for row in _build_header(summary):
        cards.append(
            Table(
                [[Paragraph(f"<b>{label}</b>", styles["BodyText"]), Paragraph(value, styles["BodyText"]) ] for label, value in row],
                colWidths=[2.6 * inch, 2.6 * inch],
            )
        )
        cards[-1].setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
                    ("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#D1D5DB")),
                    ("PADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(cards[-1])
        story.append(Spacer(1, 12))

    story.append(Paragraph("TOP ARTISTS", section_style))
    artist_rows = [["Rank", "Artist", "Plays"]]
    for index, artist in enumerate(summary.get("top_artists", [])[:5], start=1):
        artist_rows.append([str(index), artist.get("artist", "N/A"), str(artist.get("plays", 0))])
    story.append(_make_table(artist_rows, [0.7 * inch, 2.5 * inch, 1.3 * inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("TOP TRACKS", section_style))
    track_rows = [["Artist", "Track", "Plays"]]
    for track in summary.get("top_tracks", [])[:5]:
        track_rows.append([track.get("artist", "N/A"), track.get("track", "N/A"), str(track.get("plays", 0))])
    story.append(_make_table(track_rows, [2.0 * inch, 2.5 * inch, 1.0 * inch]))
    story.append(Spacer(1, 12))

    audio_features = summary.get("audio_features") or []
    if audio_features:
        story.append(Paragraph("AUDIO VIBES", section_style))
        feature_rows = [["Track", "Snapshot"]]
        for feature in audio_features[:3]:
            feature_rows.append(
                [
                    feature.get("track", "N/A"),
                    (
                        f"tempo {feature.get('tempo', 'N/A')} • "
                        f"danceability {feature.get('danceability', 'N/A')} • "
                        f"energy {feature.get('energy', 'N/A')}"
                    ),
                ]
            )
        story.append(_make_table(feature_rows, [1.8 * inch, 3.8 * inch]))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    doc.build(story)
    return output_path
