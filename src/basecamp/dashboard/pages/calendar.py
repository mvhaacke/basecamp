"""Calendar page — activity heatmap with sport dots."""

from datetime import date, timedelta
import json

import streamlit as st
from sqlalchemy import select

from basecamp.analytics.tss import AthleteThresholds, compute_activity_tss
from basecamp.database import get_session
from basecamp.models import Activity, AthleteSettings

# Sport → colour mapping (same tokens as training.py)
SPORT_COLOR = {
    "Swim": "#38BDF8", "Run": "#A78BFA", "TrailRun": "#A78BFA",
    "Ride": "#FB923C", "VirtualRide": "#FB923C", "MountainBikeRide": "#FB923C",
    "GravelRide": "#FB923C", "EBikeRide": "#FB923C",
}

def _sport_dot_color(sport: str) -> str:
    return SPORT_COLOR.get(sport, "#52525B")

def _tss_cell_color(tss: float) -> str:
    """Map a TSS value to a background colour (dark → teal gradient)."""
    if tss <= 0:
        return "#1A1D27"
    elif tss < 30:
        return "#0D3D38"
    elif tss < 60:
        return "#0E6B62"
    elif tss < 100:
        return "#14B8A6"
    else:
        return "#2DD4BF"

def _weeks_back_label(w: int) -> str:
    return {12: "3 months", 26: "6 months", 52: "12 months"}.get(w, f"{w} weeks")

# ── Controls ───────────────────────────────────────────────────────────

weeks_options = [12, 26, 52]
weeks_labels  = [_weeks_back_label(w) for w in weeks_options]
selected_label = st.selectbox("Period", weeks_labels, index=1)
num_weeks = weeks_options[weeks_labels.index(selected_label)]

# ── Load data ──────────────────────────────────────────────────────────

end_date   = date.today()
start_date = end_date - timedelta(weeks=num_weeks)

with get_session() as session:
    settings = session.get(AthleteSettings, 1)
    thresholds = AthleteThresholds(
        ftp=settings.ftp if settings else None,
        run_threshold_pace=settings.run_threshold_pace if settings else None,
        swim_css=settings.swim_css if settings else None,
        max_hr=settings.max_hr if settings else None,
        resting_hr=settings.resting_hr if settings else None,
        lthr=settings.lthr if settings else None,
    ) if settings else AthleteThresholds()

    activities = session.execute(
        select(Activity)
        .where(Activity.start_date_local >= start_date)
        .order_by(Activity.start_date_local)
    ).scalars().all()

# Build day → {tss, sports} lookup
day_data: dict[date, dict] = {}
for act in activities:
    d = (act.start_date_local or act.start_date).date()
    tss, _ = compute_activity_tss(
        sport_type=act.sport_type or "",
        duration_s=float(act.moving_time or 0),
        weighted_average_watts=act.weighted_average_watts,
        average_watts=act.average_watts,
        average_heartrate=act.average_heartrate,
        thresholds=thresholds,
        average_speed_m_per_s=act.average_speed,
        distance_m=act.distance,
    )
    entry = day_data.setdefault(d, {"tss": 0.0, "sports": [], "names": []})
    entry["tss"]   += tss or 0
    entry["sports"].append(act.sport_type or "Other")
    entry["names"].append(act.name or "")

# ── Build calendar HTML ────────────────────────────────────────────────

# Align start to Monday of the week containing start_date
grid_start = start_date - timedelta(days=start_date.weekday())

# Day-of-week labels (Mon first)
dow_labels  = ["M", "T", "W", "T", "F", "S", "S"]
month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# Build week columns
weeks: list[list[date]] = []
d = grid_start
while d <= end_date + timedelta(days=6):
    week = [d + timedelta(days=i) for i in range(7)]
    weeks.append(week)
    d += timedelta(days=7)

# Month header — figure out which column each month starts in
month_spans: list[tuple[int, str]] = []  # (col_index, label)
seen_months = set()
for col_i, week in enumerate(weeks):
    for day in week:
        key = (day.year, day.month)
        if key not in seen_months and start_date <= day <= end_date:
            seen_months.add(key)
            month_spans.append((col_i, month_names[day.month - 1]))

# ── Render ─────────────────────────────────────────────────────────────

CELL = 30    # px per cell
GAP  = 4     # px gap
DOW  = 28    # px left gutter for day labels

total_cols = len(weeks)
width_px   = DOW + total_cols * (CELL + GAP)

# Build month header row
month_header_parts = []
prev_col = 0
for col_i, label in month_spans:
    # fill gap with empty span
    gap_cols = col_i - prev_col
    if gap_cols > 0:
        month_header_parts.append(
            f'<span style="display:inline-block;width:{gap_cols*(CELL+GAP)}px"></span>'
        )
    month_header_parts.append(
        f'<span style="display:inline-block;width:{CELL+GAP}px;'
        f'font-size:11px;font-weight:600;color:#9CA3AF;letter-spacing:0.05em">{label}</span>'
    )
    prev_col = col_i + 1

# Build cell rows (one per day of week)
rows_html = []
for dow in range(7):
    cells = []
    for week in weeks:
        day = week[dow]
        data    = day_data.get(day, {})
        tss     = data.get("tss", 0)
        sports  = data.get("sports", [])
        names   = data.get("names", [])
        is_future = day > end_date
        is_outside = day < start_date

        bg = "#0F1117" if (is_future or is_outside) else _tss_cell_color(tss)

        # Tooltip
        if not is_future and not is_outside and (tss > 0 or sports):
            tooltip_parts = [day.strftime("%d %b %Y")]
            if tss > 0:
                tooltip_parts.append(f"TSS {tss:.0f}")
            for s, n in zip(sports, names):
                tooltip_parts.append(f"{s}: {n}" if n else s)
            tooltip = " · ".join(tooltip_parts)
        else:
            tooltip = day.strftime("%d %b")

        # Sport dots (max 4 visible)
        dots_html = ""
        for sport in sports[:4]:
            color = _sport_dot_color(sport)
            dots_html += f'<span style="display:inline-block;width:5px;height:5px;border-radius:50%;background:{color};margin:0 1px"></span>'

        today_ring = "outline:1.5px solid #14B8A6;outline-offset:-2px;" if day == date.today() else ""

        cells.append(
            f'<div title="{tooltip}" style="'
            f'width:{CELL}px;height:{CELL}px;'
            f'background:{bg};'
            f'border-radius:4px;'
            f'display:inline-flex;flex-direction:column;'
            f'align-items:center;justify-content:center;gap:2px;'
            f'margin-right:{GAP}px;cursor:default;'
            f'{today_ring}'
            f'">'
            f'{dots_html}'
            f'</div>'
        )

    dow_label = f'<span style="display:inline-block;width:{DOW}px;font-size:10px;color:#4B5563;line-height:{CELL}px">{dow_labels[dow]}</span>'
    rows_html.append(
        f'<div style="height:{CELL}px;margin-bottom:{GAP}px;white-space:nowrap">'
        f'{dow_label}{"".join(cells)}'
        f'</div>'
    )

# Legend
legend_items = [
    ("No training",  "#1A1D27"),
    ("< 30 TSS",     "#0D3D38"),
    ("30–60",        "#0E6B62"),
    ("60–100",       "#14B8A6"),
    ("> 100",        "#2DD4BF"),
]
legend_html = "".join(
    f'<div style="display:flex;align-items:center;gap:5px;margin-right:14px">'
    f'<div style="width:12px;height:12px;border-radius:3px;background:{c}"></div>'
    f'<span style="font-size:11px;color:#6B7280">{label}</span></div>'
    for label, c in legend_items
)

sport_legend_items = [
    ("Swim",  "#38BDF8"),
    ("Bike",  "#FB923C"),
    ("Run",   "#A78BFA"),
    ("Other", "#52525B"),
]
sport_legend_html = "".join(
    f'<div style="display:flex;align-items:center;gap:5px;margin-right:14px">'
    f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{c}"></span>'
    f'<span style="font-size:11px;color:#6B7280">{label}</span></div>'
    for label, c in sport_legend_items
)

html = f"""
<div style="font-family:system-ui,-apple-system,sans-serif;overflow-x:auto;padding-bottom:8px">

  <!-- Month headers -->
  <div style="margin-left:{DOW}px;margin-bottom:6px;white-space:nowrap">
    {"".join(month_header_parts)}
  </div>

  <!-- Day rows -->
  {"".join(rows_html)}

  <!-- Legend row -->
  <div style="margin-top:16px;display:flex;flex-wrap:wrap;align-items:center;gap:4px">
    <span style="font-size:11px;color:#4B5563;margin-right:6px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em">TSS</span>
    {legend_html}
    <span style="font-size:11px;color:#4B5563;margin-left:12px;margin-right:6px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em">Sport</span>
    {sport_legend_html}
  </div>
</div>
"""

st.markdown('<div class="section-header">Activity Calendar</div>', unsafe_allow_html=True)
st.html(html)

# ── Monthly summary below the calendar ────────────────────────────────

if day_data:
    st.markdown('<div class="section-header">Monthly Totals</div>', unsafe_allow_html=True)

    monthly: dict[str, dict] = {}
    for d, data in day_data.items():
        if start_date <= d <= end_date:
            key = d.strftime("%Y-%m")
            entry = monthly.setdefault(key, {"tss": 0.0, "days": 0})
            entry["tss"]  += data["tss"]
            entry["days"] += 1

    import pandas as pd
    monthly_df = pd.DataFrame([
        {"Month": k, "Training days": v["days"], "Total TSS": round(v["tss"])}
        for k, v in sorted(monthly.items())
    ])
    st.dataframe(monthly_df, use_container_width=True, hide_index=True)
