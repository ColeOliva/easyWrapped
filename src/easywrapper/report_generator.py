from __future__ import annotations

from io import BytesIO
from pathlib import Path

from matplotlib import pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)


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


def _chart_image(title: str, labels: list[str], values: list[int], color: str = "#1DB954") -> BytesIO:
    fig, ax = plt.subplots(figsize=(5.2, 2.4))
    ax.bar(labels, values, color=color)
    ax.set_title(title, fontsize=9)
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer


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
    body_style = ParagraphStyle(
        "BodySmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#374151"),
    )

    first_seen = summary.get("listening_window", {}).get("first") or "N/A"
    last_seen = summary.get("listening_window", {}).get("last") or "N/A"
    time_analysis = summary.get("time_analysis") or {}
    monthly_trend = summary.get("monthly_trend") or []

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

    if time_analysis:
        story.append(Paragraph("LISTENING PATTERNS", section_style))
        peak_hour = time_analysis.get("peak_hour") or "N/A"
        peak_hour_count = time_analysis.get("peak_hour_count", 0)
        day_part = time_analysis.get("day_part") or "N/A"
        avg_per_day = time_analysis.get("avg_tracks_per_day", 0)
        hourly_distribution = time_analysis.get("hourly_distribution") or []
        weekday_distribution = time_analysis.get("day_of_week") or {}
        insight_rows = [["Metric", "Value"], ["Peak hour", f"{peak_hour} ({peak_hour_count} plays)"], ["Day part", day_part], ["Avg/day", str(avg_per_day)], ["Most active weekday", next(iter(weekday_distribution.items()), ("N/A", 0))[0] if weekday_distribution else "N/A"]]
        story.append(_make_table(insight_rows, [2.2 * inch, 3.6 * inch]))
        story.append(Spacer(1, 10))

        if hourly_distribution:
            labels = [entry.get("hour", "") for entry in hourly_distribution[:12]]
            values = [int(entry.get("count", 0)) for entry in hourly_distribution[:12]]
            chart_buffer = _chart_image("Hourly listening pattern", labels, values)
            story.append(Image(chart_buffer, width=5.2 * inch, height=2.4 * inch))
            story.append(Spacer(1, 10))

        if weekday_distribution:
            weekday_rows = [["Day", "Plays"]]
            for day, plays in list(weekday_distribution.items())[:7]:
                weekday_rows.append([day, str(plays)])
            story.append(Paragraph("BY DAY OF WEEK", section_style))
            story.append(_make_table(weekday_rows, [2.3 * inch, 2.4 * inch]))
            story.append(Spacer(1, 12))

    if monthly_trend:
        story.append(Paragraph("MONTHLY TREND", section_style))
        trend_labels = [entry.get("month", "") for entry in monthly_trend[-6:]]
        trend_values = [int(entry.get("plays", 0)) for entry in monthly_trend[-6:]]
        trend_chart = _chart_image("Monthly listening trend", trend_labels, trend_values, color="#34D399")
        story.append(Image(trend_chart, width=5.2 * inch, height=2.4 * inch))
        story.append(Spacer(1, 10))

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
