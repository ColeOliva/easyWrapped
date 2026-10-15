from __future__ import annotations

import json
from pathlib import Path


def _format_svg_bar_chart(title: str, labels: list[str], values: list[int], color: str = "#1DB954") -> str:
    if not labels or not values:
        return f"<div class='empty-chart'><strong>{title}</strong><p>No data in this range.</p></div>"

    max_value = max(values) or 1
    width = 540
    height = 210
    chart_height = 150
    bar_width = max(30, (width - 80) // max(len(labels), 1))
    bars = []

    for index, (label, value) in enumerate(zip(labels, values)):
        x = 40 + index * (bar_width + 12)
        bar_height = max(8, (value / max_value) * chart_height)
        y = height - 20 - bar_height
        bars.append(
            f"<g><rect x='{x}' y='{y}' width='{bar_width}' height='{bar_height}' rx='4' fill='{color}'/>"
            f"<text x='{x + bar_width / 2}' y='{height - 4}' text-anchor='middle' font-size='10' fill='#374151'>{label}</text>"
            f"<text x='{x + bar_width / 2}' y='{y - 6}' text-anchor='middle' font-size='9' fill='#111827'>{value}</text></g>"
        )

    return (
        f"<div class='chart-panel'><h3>{title}</h3>"
        f"<svg viewBox='0 0 {width} {height}' width='100%' height='210'>"
        f"<line x1='30' y1='170' x2='{width - 10}' y2='170' stroke='#D1D5DB'/>"
        f"{''.join(bars)}</svg></div>"
    )


def _render_table(title: str, rows: list[dict], columns: list[str], key_field: str = "label") -> str:
    if not rows:
        return f"<div class='table-panel'><h3>{title}</h3><p>No data available.</p></div>"

    header = "".join(f"<th>{column}</th>" for column in columns)
    body = []
    for row in rows[:10]:
        cells = []
        for column in columns:
            value = row.get(column.lower().replace(" ", "_"), row.get(column.lower(), row.get(key_field, "")))
            if isinstance(value, (int, float)):
                value = str(value)
            cells.append(f"<td>{value}</td>")
        body.append(f"<tr>{''.join(cells)}</tr>")

    return (
        f"<div class='table-panel'><h3>{title}</h3><table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def generate_html_report(summary: dict, events: list[dict], output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    events_json = json.dumps(events, ensure_ascii=False)
    summary_json = json.dumps(summary, ensure_ascii=False)

    html = """<!doctype html>
<html lang='en'>
  <head>
    <meta charset='utf-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>Your Wrapped</title>
    <style>
      :root {
        --bg: #f4f7fb;
        --panel: #ffffff;
        --panel-alt: #f9fafb;
        --text: #111827;
        --muted: #6b7280;
        --accent: #1DB954;
        --accent-soft: #d9f7e7;
        --shadow: rgba(17,24,39,0.08);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0; font-family: Arial, sans-serif; background: var(--bg); color: var(--text);
      }
      .wrap { max-width: 1180px; margin: 0 auto; padding: 28px 20px 50px; }
      .hero { background: linear-gradient(135deg, #0f172a, #1f2937); color: white; border-radius: 24px; padding: 28px; box-shadow: var(--shadow); }
      .hero h1 { margin: 0 0 10px; font-size: 42px; letter-spacing: 0.04em; }
      .hero p { margin: 0; color: #dbeafe; }
      .filters { display: flex; flex-wrap: wrap; gap: 14px; align-items: end; margin: 24px 0; background: var(--panel); padding: 18px; border-radius: 18px; box-shadow: var(--shadow); }
      .field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--muted); }
      .field input, .field select { border: 1px solid #d1d5db; border-radius: 10px; padding: 10px 12px; font-size: 14px; background: white; }
      button { background: var(--accent); border: none; color: white; border-radius: 10px; padding: 10px 16px; font-weight: 700; cursor: pointer; }
      .narrative-card { display: grid; grid-template-columns: 1.4fr 0.9fr; gap: 18px; background: linear-gradient(135deg, #ecfdf5, #e0f2fe); border-radius: 22px; padding: 22px; box-shadow: var(--shadow); margin-top: 22px; }
      .eyebrow { text-transform: uppercase; letter-spacing: 0.1em; font-size: 11px; color: var(--muted); }
      .narrative-card h2 { margin: 8px 0 10px; font-size: 28px; }
      .narrative-card p { color: #374151; margin: 0; line-height: 1.6; }
      .mood-box { background: rgba(255,255,255,0.7); border-radius: 18px; padding: 16px; }
      .mood-box h3 { margin: 0 0 12px; }
      .chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
      .chip { background: rgba(29,185,84,0.12); color: #065f46; border-radius: 999px; padding: 6px 10px; font-size: 12px; font-weight: 700; }
      .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin: 22px 0; }
      .stat-card { background: var(--panel); border-radius: 18px; padding: 18px; box-shadow: var(--shadow); }
      .stat-card .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }
      .stat-card .value { font-size: 30px; font-weight: 800; margin-top: 8px; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px; margin-top: 20px; }
      .chart-panel, .table-panel, .insights { background: var(--panel); border-radius: 18px; padding: 18px; box-shadow: var(--shadow); overflow: hidden; }
      .chart-panel h3, .table-panel h3, .insights h3 { margin-top: 0; margin-bottom: 12px; }
      table { width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
      th, td { padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; word-break: break-word; }
      th { background: #f3f4f6; color: var(--muted); width: 38%; }
      .empty-chart { background: var(--panel-alt); border: 1px dashed #d1d5db; border-radius: 12px; padding: 24px; color: var(--muted); text-align: center; }
      .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.55); z-index: 50; }
      .modal.open { display: flex; align-items: center; justify-content: center; }
      .modal-card { background: white; width: min(520px, 90vw); border-radius: 18px; padding: 20px; box-shadow: var(--shadow); }
      .modal-card h2 { margin-top: 0; }
      .close-btn { float: right; background: none; color: var(--text); font-size: 22px; border: none; }
      @media (max-width: 800px) { .grid { grid-template-columns: 1fr; } .hero h1 { font-size: 30px; } }
    </style>
  </head>
  <body>
    <div class='wrap'>
      <div class='hero'>
        <h1>YOUR WRAPPED</h1>
        <p id='rangeLabel'>Loading listening range…</p>
      </div>

      <div class='narrative-card'>
        <div>
          <div class='eyebrow'>Your music identity</div>
          <h2 id='listenerHeadline'>Loading your profile…</h2>
          <p id='listenerNarrative'>Gathering the energy behind your listening habits.</p>
        </div>
        <div class='mood-box'>
          <h3>Sound profile</h3>
          <div id='moodSummary'></div>
        </div>
      </div>

      <div class='filters'>
        <div class='field'>
          <label for='startMonth'>Start month</label>
          <select id='startMonth'></select>
        </div>
        <div class='field'>
          <label for='endMonth'>End month</label>
          <select id='endMonth'></select>
        </div>
        <div class='field'>
          <label for='topN'>Top results</label>
          <select id='topN'>
            <option value='5'>5</option>
            <option value='10'>10</option>
            <option value='15'>15</option>
          </select>
        </div>
        <button id='applyFilters'>Update report</button>
      </div>

      <div class='stats' id='statsGrid'></div>

      <div class='grid'>
        <div id='monthChart'></div>
        <div id='insightsPanel'></div>
      </div>

      <div class='grid' style='margin-top: 18px;'>
        <div id='artistTable'></div>
        <div id='trackTable'></div>
      </div>

      <div class='grid' style='margin-top: 18px;'>
        <div id='audioVibes'></div>
      </div>
    </div>

    <div id='detailModal' class='modal'>
      <div class='modal-card'>
        <button class='close-btn' id='closeModal' aria-label='Close'>×</button>
        <h2 id='modalTitle'>Details</h2>
        <div id='modalBody'></div>
      </div>
    </div>

    <script>
      const allEvents = __EVENTS_JSON__;
      const baseSummary = __SUMMARY_JSON__;
      const allMonths = [...new Set(allEvents.map(event => event.timestamp.slice(0, 7)))].sort();
      const startMonthSelect = document.getElementById('startMonth');
      const endMonthSelect = document.getElementById('endMonth');
      const statsGrid = document.getElementById('statsGrid');
      const monthChart = document.getElementById('monthChart');
      const insightsPanel = document.getElementById('insightsPanel');
      const artistTable = document.getElementById('artistTable');
      const trackTable = document.getElementById('trackTable');
      const modal = document.getElementById('detailModal');
      const modalTitle = document.getElementById('modalTitle');
      const modalBody = document.getElementById('modalBody');

      function populateMonths() {
        const options = allMonths.map(month => `<option value="${month}">${month}</option>`).join('');
        startMonthSelect.innerHTML = options;
        endMonthSelect.innerHTML = options;
        startMonthSelect.value = allMonths[0];
        endMonthSelect.value = allMonths[allMonths.length - 1];
      }

      function filterEvents(startMonth, endMonth) {
        const [startYear, startMonthIndex] = startMonth.split('-').map(Number);
        const [endYear, endMonthIndex] = endMonth.split('-').map(Number);
        const start = new Date(startYear, startMonthIndex - 1, 1, 0, 0, 0, 0);
        const end = new Date(endYear, endMonthIndex, 0, 23, 59, 59, 999);
        return allEvents.filter(event => {
          const ts = new Date(event.timestamp);
          return ts >= start && ts <= end;
        });
      }

      function average(values) {
        if (!values.length) return 0;
        return values.reduce((sum, value) => sum + value, 0) / values.length;
      }

      function buildMoodProfile(events, audioFeatures) {
        const nightShare = events.length ? (events.filter(event => {
          const hour = new Date(event.timestamp).getHours();
          return hour >= 21 || hour < 5;
        }).length / events.length) * 100 : 0;

        const energyValues = audioFeatures.map(item => Number(item.energy ?? 0)).filter(value => Number.isFinite(value));
        const valenceValues = audioFeatures.map(item => Number(item.valence ?? 0)).filter(value => Number.isFinite(value));
        const tempoValues = audioFeatures.map(item => Number(item.tempo ?? 0)).filter(value => Number.isFinite(value));
        const acousticValues = audioFeatures.map(item => Number(item.acousticness ?? 0)).filter(value => Number.isFinite(value));

        const energy = energyValues.length ? average(energyValues) : 0.5 + Math.min(0.2, (nightShare / 100) * 0.2);
        const valence = valenceValues.length ? average(valenceValues) : 0.52 + Math.min(0.15, (nightShare / 100) * 0.18);
        const tempo = tempoValues.length ? average(tempoValues) : 90 + Math.min(30, nightShare * 0.3);
        const acousticness = acousticValues.length ? average(acousticValues) : 0.45 + Math.min(0.2, (nightShare / 100) * 0.15);

        const energyLabel = energy >= 0.7 ? 'High-energy' : energy >= 0.45 ? 'Balanced' : 'Low-key';
        const valenceLabel = valence >= 0.7 ? 'Warm, bright' : valence >= 0.45 ? 'Balanced' : 'Reflective, moody';
        const tempoLabel = tempo >= 120 ? 'Fast and driving' : tempo >= 90 ? 'Steady groove' : 'Slow burn';
        const focusLabel = acousticness >= 0.6 ? 'Deep-focus' : acousticness >= 0.35 ? 'Blend of focus and mood' : 'Open and exploratory';

        return {
          energy: Number(energy.toFixed(3)),
          energy_label: energyLabel,
          valence: Number(valence.toFixed(3)),
          valence_label: valenceLabel,
          tempo: Number(tempo.toFixed(2)),
          tempo_label: tempoLabel,
          acousticness: Number(acousticness.toFixed(3)),
          focus_label: focusLabel,
          night_share: Number(nightShare.toFixed(1)),
          night_share_label: nightShare >= 30 ? 'Night owl' : nightShare <= 15 ? 'Mostly daytime' : 'Balanced rhythm'
        };
      }

      function buildCategories(events, audioFeatures, moodProfile) {
        if (!events.length) return [];

        const artistCounter = new Map();
        const trackCounter = new Map();
        for (const event of events) {
          artistCounter.set(event.artist, (artistCounter.get(event.artist) || 0) + 1);
          const key = `${event.artist}::${event.track}`;
          trackCounter.set(key, (trackCounter.get(key) || 0) + 1);
        }

        const uniqueArtists = artistCounter.size;
        const repeatedTracks = [...trackCounter.values()].filter(count => count > 1).length;
        const repeatedShare = (repeatedTracks / Math.max(trackCounter.size, 1)) * 100;
        const artistDensity = Math.min(100, Math.max(5, Math.round((uniqueArtists / Math.max(events.length, 1)) * 100 * 3)));
        const nightScore = Math.min(100, Math.max(10, Math.round(moodProfile.night_share)));

        return [
          { name: 'Late-night drift', score: nightScore, description: `${moodProfile.night_share}% of your listening happens after dark.` },
          { name: 'Replay habit', score: Math.min(100, Math.max(20, Math.round(repeatedShare * 2))), description: 'A few tracks keep replaying because they really match your mood.' },
          { name: 'Artist range', score: artistDensity, description: `You span ${uniqueArtists} artists and keep your taste moving without needing to chase the obvious picks.` },
          { name: 'Mood intensity', score: Math.min(100, Math.max(15, Math.round(moodProfile.energy * 100))), description: `Your signal feels ${moodProfile.energy_label.toLowerCase()} and emotionally tuned.` },
          { name: 'Top window', score: Math.min(100, Math.max(15, Math.round((events.filter(event => { const hour = new Date(event.timestamp).getHours(); return hour >= 21 || hour < 5; }).length / events.length) * 100))), description: `Your strongest listening window leans ${new Date(events[0].timestamp).getHours() >= 21 || new Date(events[0].timestamp).getHours() < 5 ? 'night' : 'day'} and gives your sound its shape.` }
        ];
      }

      function buildListenerProfile(events, moodProfile, categories) {
        if (!events.length) {
          return { archetype: 'Quiet observer', headline: 'No listening data yet.', summary: 'Once you have a few sessions, the profile will read your habits and mood more clearly.' };
        }

        const lateNight = moodProfile.night_share || 0;
        const energy = moodProfile.energy_label || 'Balanced';
        const valence = moodProfile.valence_label || 'Balanced';
        const artistCount = new Set(events.map(event => event.artist)).size;
        const trackCount = events.length;
        const energyValue = Number(moodProfile.energy || 0.5);
        const valenceValue = Number(moodProfile.valence || 0.5);

        let archetype = 'The steady rhythm explorer';
        let headline = 'You like a balance of momentum and feeling.';
        let summary = `Your profile reads as balanced rather than extreme: energy ${energyValue.toFixed(2)}, valence ${valenceValue.toFixed(2)}, and a late-night share of ${lateNight.toFixed(1)}%. That mix suggests you are not chasing one mood alone; you are building a personal soundtrack that can move between reflection, motion, and comfort.`;

        if (lateNight >= 35 && energy === 'High-energy') {
          archetype = 'The night-drive curator';
          headline = 'You turn the late hours into your own private soundtrack.';
          summary = `Your listening pattern is strongly evening-weighted: about ${lateNight.toFixed(1)}% of your sessions happen after dark, with an energy read of ${energyValue.toFixed(2)} and a ${valence.toLowerCase()} tone. That combination commonly points to music used for emotional processing, focus, or a bit of motion after the day settles.`;
        } else if (valence === 'Warm, bright') {
          archetype = 'The warm-hearted romantic';
          headline = 'Your taste feels cinematic, comforting, and a little nostalgic.';
          summary = `You are leaning into warm, emotionally resonant music: valence sits around ${valenceValue.toFixed(2)}, and the collection spans ${artistCount} artists across ${trackCount} listens. This kind of profile is often associated with music that feels comforting, uplifting, and personally familiar.`;
        } else if (energy === 'Low-key') {
          archetype = 'The reflective wanderer';
          headline = 'Your listening is quieter, more atmospheric, and intentional.';
          summary = `The signal is more reflective than high-arousal: energy sits around ${energyValue.toFixed(2)}, valence is around ${valenceValue.toFixed(2)}, and roughly ${lateNight.toFixed(1)}% of plays happen late. That pattern often matches introspective, textural listening used to slow the pace down.`;
        }

        return {
          archetype,
          headline,
          summary,
          evidence: [
            { label: 'Late-night share', value: `${lateNight.toFixed(1)}%`, detail: 'Research on music listening often links a strong evening signal to emotional regulation, routine, and lower-stimulation listening habits.' },
            { label: 'Energy', value: energyValue.toFixed(2), detail: 'Values around this range usually signal balanced listening: not purely high-arousal, but also not sleep-like or fully ambient.' },
            { label: 'Valence', value: valenceValue.toFixed(2), detail: 'This score indicates whether the music skews more reflective, moody, or warm and bright. Your pattern sits on the reflective-to-balanced side.' },
            { label: 'Artist breadth', value: `${artistCount} artists`, detail: 'A broad artist footprint usually suggests exploratory taste rather than a narrow fixation on a single scene or mood.' }
          ],
          categories,
          primary_trait: energy
        };
      }

      function buildSummary(events) {
        const artistMap = new Map();
        const trackMap = new Map();
        const monthMap = new Map();
        const hourMap = new Map();
        const weekdayMap = new Map();
        const audioFeatureMap = new Map();

        for (const feature of (baseSummary.audio_features || [])) {
          const key = `${(feature.artist || '').toLowerCase()}::${(feature.track || '').toLowerCase()}`;
          if (key) audioFeatureMap.set(key, feature);
        }

        for (const event of events) {
          const artist = event.artist || 'Unknown';
          const track = event.track || 'Unknown';
          const month = event.timestamp.slice(0, 7);
          const dt = new Date(event.timestamp);
          const hour = dt.getHours();
          const weekday = dt.toLocaleDateString('en-US', { weekday: 'long' });

          artistMap.set(artist, (artistMap.get(artist) || 0) + 1);
          trackMap.set(`${artist}::${track}`, (trackMap.get(`${artist}::${track}`) || 0) + 1);
          monthMap.set(month, (monthMap.get(month) || 0) + 1);
          hourMap.set(hour, (hourMap.get(hour) || 0) + 1);
          weekdayMap.set(weekday, (weekdayMap.get(weekday) || 0) + 1);
        }

        const topArtists = [...artistMap.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([artist, plays]) => ({ artist, plays }));
        const topTracks = [...trackMap.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([key, plays]) => {
          const [artist, track] = key.split('::');
          return { artist, track, plays };
        });

        const hourlyDistribution = [...Array(24).keys()].map(hour => ({ hour: hour.toString().padStart(2, '0') + ':00', count: hourMap.get(hour) || 0 }));
        const dayOfWeek = [...weekdayMap.entries()].sort((a, b) => b[1] - a[1]).slice(0, 7).reduce((acc, [day, plays]) => (acc[day] = plays, acc), {});
        const peakHour = hourlyDistribution.reduce((best, current) => current.count > best.count ? current : best, { hour: '00:00', count: 0 });
        const monthTrend = [...monthMap.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([month, plays]) => ({ month, plays }));

        const audioFeatures = [];
        const seenAudioKeys = new Set();
        for (const event of events) {
          const key = `${(event.artist || '').toLowerCase()}::${(event.track || '').toLowerCase()}`;
          if (!audioFeatureMap.has(key) || seenAudioKeys.has(key)) continue;
          seenAudioKeys.add(key);
          audioFeatures.push(audioFeatureMap.get(key));
        }

        const moodProfile = buildMoodProfile(events, audioFeatures);
        const categories = buildCategories(events, audioFeatures, moodProfile);
        const listenerProfile = buildListenerProfile(events, moodProfile, categories);

        return {
          total_tracks: events.length,
          unique_artists: artistMap.size,
          top_artists: topArtists,
          top_tracks: topTracks,
          most_active_day: [...weekdayMap.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A',
          listening_window: events.length ? {
            first: new Date(Math.min(...events.map(event => new Date(event.timestamp).getTime()))).toISOString(),
            last: new Date(Math.max(...events.map(event => new Date(event.timestamp).getTime()))).toISOString()
          } : { first: null, last: null },
          time_analysis: {
            peak_hour: peakHour.hour,
            peak_hour_count: peakHour.count,
            day_part: peakHour.hour >= '17:00' ? 'Evening' : peakHour.hour >= '12:00' ? 'Afternoon' : peakHour.hour >= '05:00' ? 'Morning' : 'Night',
            day_of_week: dayOfWeek,
            hourly_distribution: hourlyDistribution,
            avg_tracks_per_day: events.length ? Number((events.length / new Set(events.map(event => event.timestamp.slice(0, 10))).size).toFixed(2)) : 0,
            unique_days: new Set(events.map(event => event.timestamp.slice(0, 10))).size
          },
          monthly_trend: monthTrend,
          audio_features: audioFeatures,
          mood_profile: moodProfile,
          analysis_categories: categories,
          listener_profile: listenerProfile
        };
      }

      function formatRangeLabel(firstValue, lastValue) {
        if (!firstValue || !lastValue) return 'No listening window yet';
        const start = new Date(firstValue);
        const end = new Date(lastValue);
        if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 'No listening window yet';
        const format = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        return `${format.format(start)} → ${format.format(end)}`;
      }

      function renderStats(summary) {
        const avgPerDay = Number(summary.time_analysis?.avg_tracks_per_day || 0);
        const topTrack = summary.top_tracks?.[0];
        const cards = [
          ['Total listens', summary.total_tracks],
          ['Unique artists', summary.unique_artists],
          ['Top artist', summary.top_artists[0]?.artist || 'N/A'],
          ['Avg/day', avgPerDay.toFixed(1)],
          ['Peak hour', summary.time_analysis?.peak_hour || 'N/A'],
          ['Top track', topTrack ? `${topTrack.track} · ${topTrack.artist}` : 'N/A']
        ];
        statsGrid.innerHTML = cards.map(([label, value]) => `<div class='stat-card'><div class='label'>${label}</div><div class='value'>${value}</div></div>`).join('');
      }

      function renderMonthChart(summary) {
        const trend = summary.monthly_trend || [];
        const labels = trend.slice(-6).map(item => item.month.slice(5));
        const values = trend.slice(-6).map(item => item.plays);
        monthChart.innerHTML = _renderBarChart('Monthly trend', labels, values, '#34D399');
      }

      function renderNarrative(summary) {
        const profile = summary.listener_profile || {};
        const mood = summary.mood_profile || {};
        const headline = profile.headline || 'Your listening pattern is taking shape.';
        const narrative = profile.summary || 'Your recent sessions are being translated into a more personal listening profile.';
        const evidence = Array.isArray(profile.evidence) ? profile.evidence : [];
        document.getElementById('listenerHeadline').textContent = headline;
        document.getElementById('listenerNarrative').textContent = narrative;

        const badges = (summary.analysis_categories || []).slice(0, 4).map(item => `<span class='chip'>${item.name}: ${item.score}%</span>`).join('');
        const totalListens = summary.total_tracks || 0;
        const artistCount = summary.unique_artists || 0;
        const evidenceRows = evidence.length ? evidence.map(item => `<div><strong>${item.label}:</strong> ${item.value} — ${item.detail}</div>`).join('') : '';
        document.getElementById('moodSummary').innerHTML = `
          <div><strong>Energy:</strong> ${mood.energy_label || 'Balanced'} (${Number(mood.energy || 0.5).toFixed(2)})</div>
          <div><strong>Vibe:</strong> ${mood.valence_label || 'Balanced'}</div>
          <div><strong>Tempo:</strong> ${mood.tempo_label || 'Steady groove'} (${Number(mood.tempo || 95).toFixed(0)} BPM)</div>
          <div><strong>Pattern:</strong> ${totalListens} listens across ${artistCount} artists</div>
          <div class='chip-row'>${badges || '<span class="chip">Early pattern</span>'}</div>
          <div style='margin-top: 10px; line-height: 1.5;'>${evidenceRows}</div>
        `;
      }

      function renderInsights(summary) {
        const time = summary.time_analysis || {};
        const audio = (summary.audio_features || []).slice(0, 3);
        const topTrack = summary.top_tracks?.[0];
        const topArtist = summary.top_artists?.[0];
        const share = summary.total_tracks ? Math.round(((topArtist?.plays || 0) / summary.total_tracks) * 100) : 0;
        const categories = (summary.analysis_categories || []).slice(0, 3);
        const insights = [
          ['Peak hour', `${time.peak_hour || 'N/A'} (${time.peak_hour_count || 0} plays)`],
          ['Most active weekday', Object.entries(time.day_of_week || {}).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A'],
          ['Average/day', String(time.avg_tracks_per_day || 0)],
          ['Top track', topTrack ? `${topTrack.track} (${topTrack.plays} plays)` : 'N/A'],
          ['Listening window', formatRangeLabel(summary.listening_window?.first, summary.listening_window?.last)],
          ['Top artist share', `${share}%`]
        ];
        const audioRows = audio.length ? audio.slice(0, 2).map(item => `<tr><th>${item.track || 'Track'}</th><td>tempo ${item.tempo ?? 'N/A'} / energy ${item.energy ?? 'N/A'}</td></tr>`).join('') : '<tr><th>Audio summary</th><td>There is no enriched audio payload in this run, so the report is grounded in listening behavior itself.</td></tr>';
        const categoryRows = categories.length ? categories.map(item => `<tr><th>${item.name}</th><td>${item.score}% — ${item.description}</td></tr>`).join('') : '<tr><th>Profile</th><td>Your listening pattern is already forming.</td></tr>';
        const evidence = Array.isArray(summary.listener_profile?.evidence) ? summary.listener_profile.evidence.slice(0, 3) : [];
        const evidenceRows = evidence.length ? evidence.map(item => `<tr><th>${item.label}</th><td>${item.value} — ${item.detail}</td></tr>`).join('') : '';
        insightsPanel.innerHTML = `<div class='insights'><h3>Listening insights</h3><table>${insights.slice(0, 4).map(([label, value]) => `<tr><th>${label}</th><td>${value}</td></tr>`).join('')}</table><h3 style='margin-top:18px;'>Categories</h3><table>${categoryRows}</table><h3 style='margin-top:18px;'>Evidence</h3><table>${evidenceRows || '<tr><th>Profile</th><td>Signal is still forming.</td></tr>'}</table><h3 style='margin-top:18px;'>Audio summary</h3><table>${audioRows}</table></div>`;
      }

      function renderAudioVibes(summary) {
        const audio = summary.audio_features || [];
        const container = document.getElementById('audioVibes');
        if (!audio.length) {
          container.innerHTML = `<div class='table-panel'><h3>Spotify audio vibes</h3><p>Spotify audio data is unavailable for this run. This usually means the API request was rate-limited or blocked before response data was returned.</p></div>`;
          return;
        }
        const rows = audio.slice(0, 5).map(item => ({
          artist: item.artist || 'Unknown',
          track: item.track || 'Unknown',
          tempo: item.tempo ?? 'N/A',
          energy: item.energy ?? 'N/A',
          danceability: item.danceability ?? 'N/A',
          valence: item.valence ?? 'N/A'
        }));
        container.innerHTML = _renderTable('Spotify audio vibes', rows, ['Artist', 'Track', 'Tempo', 'Energy', 'Danceability', 'Valence'], 'audio');
      }

      function renderTables(summary, topN) {
        const artists = (summary.top_artists || []).slice(0, topN).map((item, index) => ({ rank: index + 1, artist: item.artist, plays: item.plays }));
        const tracks = (summary.top_tracks || []).slice(0, topN).map(item => ({ artist: item.artist, track: item.track, plays: item.plays }));
        artistTable.innerHTML = _renderTable('Top artists', artists, ['Rank', 'Artist', 'Plays'], 'artist');
        trackTable.innerHTML = _renderTable('Top tracks', tracks, ['Artist', 'Track', 'Plays'], 'track');

        document.querySelectorAll('#artistTable tbody tr[data-kind="artist"]').forEach(row => {
          row.addEventListener('click', () => {
            const artist = row.dataset.value;
            const plays = row.dataset.plays;
            modalTitle.textContent = artist;
            modalBody.innerHTML = `<p><strong>Plays:</strong> ${plays}</p><p>Explore this artist within the selected reporting window.</p>`;
            modal.classList.add('open');
          });
        });

        document.querySelectorAll('#trackTable tbody tr[data-kind="track"]').forEach(row => {
          row.addEventListener('click', () => {
            const artist = row.dataset.artist;
            const track = row.dataset.track;
            const plays = row.dataset.plays;
            modalTitle.textContent = `${artist} — ${track}`;
            modalBody.innerHTML = `<p><strong>Plays:</strong> ${plays}</p><p>Use the date filters to expand or narrow the range for this song.</p>`;
            modal.classList.add('open');
          });
        });
      }

      function _renderTable(title, rows, columns, kind) {
        if (!rows.length) {
          return `<div class='table-panel'><h3>${title}</h3><p>No data available.</p></div>`;
        }
        const header = columns.map(column => `<th>${column}</th>`).join('');
        const body = rows.map((row) => {
          const cells = columns.map((column) => `<td>${row[column.toLowerCase().replace(/ /g, '_')] ?? row[column.toLowerCase()] ?? row[Object.keys(row)[0]]}</td>`).join('');
          if (kind === 'artist') {
            return `<tr data-kind='artist' data-value='${row.artist}' data-plays='${row.plays}' style='cursor:pointer'>${cells}</tr>`;
          }
          return `<tr data-kind='track' data-artist='${row.artist}' data-track='${row.track}' data-plays='${row.plays}' style='cursor:pointer'>${cells}</tr>`;
        }).join('');
        return `<div class='table-panel'><h3>${title}</h3><table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></div>`;
      }

      function _renderBarChart(title, labels, values, color) {
        if (!labels.length) { return `<div class='empty-chart'><strong>${title}</strong><p>No data in this range.</p></div>`; }
        const maxValue = Math.max(...values, 1);
        const width = 540;
        const height = 220;
        const chartHeight = 130;
        const barWidth = Math.max(36, (width - 80) / labels.length);
        let bars = '';

        labels.forEach((label, index) => {
          const value = values[index] || 0;
          const x = 40 + index * (barWidth + 12);
          const barHeight = Math.max(10, (value / maxValue) * chartHeight);
          const y = height - 35 - barHeight;
          bars += `<g><rect x='${x}' y='${y}' width='${barWidth}' height='${barHeight}' rx='4' fill='${color}'/><text x='${x + barWidth / 2}' y='${height - 12}' text-anchor='middle' font-size='10' fill='#374151'>${label}</text><text x='${x + barWidth / 2}' y='${y - 5}' text-anchor='middle' font-size='9' fill='#111827'>${value}</text></g>`;
        });

        return `<div class='chart-panel'><h3>${title}</h3><svg viewBox='0 0 ${width} ${height}' width='100%' height='220'><line x1='30' y1='170' x2='${width - 12}' y2='170' stroke='#D1D5DB'/><g>${bars}</g></svg></div>`;
      }

      function updateReport() {
        const start = startMonthSelect.value;
        const end = endMonthSelect.value;
        const topN = Number(document.getElementById('topN').value || 5);
        const selectedEvents = filterEvents(start, end);
        const summary = buildSummary(selectedEvents);
        document.getElementById('rangeLabel').textContent = `Showing ${start} to ${end} · ${summary.total_tracks} listens · ${summary.top_artists[0]?.artist || 'No clear leader'}`;
        renderNarrative(summary);
        renderStats(summary);
        renderMonthChart(summary);
        renderInsights(summary);
        renderAudioVibes(summary);
        renderTables(summary, topN);
      }

      document.getElementById('applyFilters').addEventListener('click', updateReport);
      document.getElementById('closeModal').addEventListener('click', () => modal.classList.remove('open'));
      modal.addEventListener('click', (event) => { if (event.target === modal) modal.classList.remove('open'); });

      populateMonths();
      updateReport();
    </script>
  </body>
</html>
"""

    html = html.replace("__EVENTS_JSON__", events_json)
    html = html.replace("__SUMMARY_JSON__", summary_json)
    output_path.write_text(html, encoding="utf-8")
    return output_path
