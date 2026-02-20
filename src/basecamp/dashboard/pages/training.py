"""Training breakdown — volume, zone distribution, weekly summary."""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select

from basecamp.analytics.zones import compute_activity_zones, load_zone_thresholds
from basecamp.database import get_session
from basecamp.models import Activity, Stream

# ── Design tokens ─────────────────────────────────────────────────────
SPORT_COLORS = {
    "Swim":  "#38BDF8",  # sky blue
    "Bike":  "#FB923C",  # orange
    "Run":   "#A78BFA",  # violet
    "Other": "#52525B",  # zinc
}
ZONE_COLORS = {
    "LIT": "#4ADE80",   # green  — easy aerobic
    "MIT": "#FACC15",   # yellow — threshold
    "HIT": "#F87171",   # red    — intense
}
SPORT_CATEGORIES = {
    "Swim": "Swim", "Run": "Run", "TrailRun": "Run", "VirtualRun": "Run",
    "Ride": "Bike", "VirtualRide": "Bike", "MountainBikeRide": "Bike",
    "GravelRide": "Bike", "EBikeRide": "Bike",
}

_PLOTLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#6B7280", size=12),
    hoverlabel=dict(bgcolor="#1A1D27", bordercolor="#2D3748", font_color="#F0F2F6"),
)
_AXIS = dict(gridcolor="#2D3748", linecolor="#2D3748", tickcolor="#2D3748")
_MARGIN = dict(l=40, r=40, t=10, b=40)
_MARGIN_PIE = dict(l=10, r=10, t=10, b=10)

def get_category(sport_type: str) -> str:
    return SPORT_CATEGORIES.get(sport_type, "Other")

# ── Period selector ────────────────────────────────────────────────────

period = st.selectbox(
    "Time period",
    ["Last 4 weeks", "Last 8 weeks", "Last 12 weeks", "This year", "All time"],
    index=1,
)
period_map = {
    "Last 4 weeks": 28, "Last 8 weeks": 56, "Last 12 weeks": 84,
    "This year": (date.today() - date(date.today().year, 1, 1)).days,
    "All time": 10000,
}
cutoff = date.today() - timedelta(days=period_map[period])

# ── Load data ──────────────────────────────────────────────────────────

thresholds = load_zone_thresholds()
has_thresholds = bool(thresholds.lthr or thresholds.ftp)

with get_session() as session:
    activities = session.execute(
        select(Activity)
        .where(Activity.start_date_local >= cutoff)
        .order_by(Activity.start_date_local)
    ).scalars().all()

    activity_ids = [a.id for a in activities]
    streams = {
        s.activity_id: s
        for s in session.execute(
            select(Stream).where(Stream.activity_id.in_(activity_ids))
        ).scalars().all()
    } if activity_ids else {}

if not activities:
    st.info("No activities in this period.")
    st.stop()

rows = []
for act in activities:
    stream = streams.get(act.id)
    zones  = compute_activity_zones(act, stream, thresholds) if has_thresholds else None
    sport  = act.sport_type or "Other"
    rows.append({
        "date":       (act.start_date_local or act.start_date).date(),
        "week":       (act.start_date_local or act.start_date).date().isocalendar()[1],
        "year":       (act.start_date_local or act.start_date).date().year,
        "sport":      sport,
        "category":   get_category(sport),
        "duration_h": (act.moving_time or 0) / 3600,
        "kcal":       act.computed_calories or 0,
        "lit_s":      zones["lit"] if zones else 0,
        "mit_s":      zones["mit"] if zones else 0,
        "hit_s":      zones["hit"] if zones else 0,
    })

df = pd.DataFrame(rows)
df["year_week"] = df["year"].astype(str) + "-W" + df["week"].astype(str).str.zfill(2)

# ── Summary stats ──────────────────────────────────────────────────────

st.markdown('<div class="section-header">Summary</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Hours",    f"{df['duration_h'].sum():.1f}")
c2.metric("Total kcal",     f"{df['kcal'].sum():,.0f}")
c3.metric("Activities",     len(df))
c4.metric("Weeks",          df["year_week"].nunique())

# ── Weekly volume ──────────────────────────────────────────────────────

st.markdown('<div class="section-header">Weekly Volume</div>', unsafe_allow_html=True)

weekly_long = (
    df.groupby(["year_week", "category"])["duration_h"]
    .sum().reset_index()
    .rename(columns={"year_week": "Week", "category": "Sport", "duration_h": "Hours"})
)
fig_vol = px.bar(
    weekly_long, x="Week", y="Hours", color="Sport",
    color_discrete_map=SPORT_COLORS,
    category_orders={"Sport": ["Swim", "Bike", "Run", "Other"]},
    labels={"Week": "", "Hours": "Hours"},
)
fig_vol.update_layout(
    **_PLOTLY_BASE,
    margin=_MARGIN,
    height=320,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(color="#9CA3AF")),
    xaxis=dict(tickangle=-45, **_AXIS),
    yaxis=_AXIS,
    bargap=0.2,
)
st.plotly_chart(fig_vol, use_container_width=True)

# ── Zone distribution ──────────────────────────────────────────────────

if has_thresholds:
    total_lit = df["lit_s"].sum()
    total_mit = df["mit_s"].sum()
    total_hit = df["hit_s"].sum()
    total_zone = total_lit + total_mit + total_hit

    if total_zone > 0:
        st.markdown('<div class="section-header">Zone Distribution</div>', unsafe_allow_html=True)

        col_pie, col_bars = st.columns([1, 2])

        with col_pie:
            lit_pct = total_lit / total_zone * 100
            zone_df = pd.DataFrame({
                "Zone":  ["LIT", "MIT", "HIT"],
                "Hours": [total_lit / 3600, total_mit / 3600, total_hit / 3600],
            })
            fig_pie = px.pie(
                zone_df, values="Hours", names="Zone", color="Zone",
                color_discrete_map=ZONE_COLORS, hole=0.55,
            )
            fig_pie.update_traces(textinfo="percent+label", textposition="outside",
                                  textfont=dict(color="#9CA3AF"))
            fig_pie.update_layout(
                **_PLOTLY_BASE,
                margin=_MARGIN_PIE,
                height=280,
                showlegend=False,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

            if lit_pct >= 75:
                st.success(f"Good polarization — {lit_pct:.0f}% LIT")
            elif lit_pct >= 60:
                st.warning(f"Moderate polarization — {lit_pct:.0f}% LIT")
            else:
                st.error(f"Low polarization — {lit_pct:.0f}% LIT")

        with col_bars:
            weekly_zones = df.groupby("year_week")[["lit_s", "mit_s", "hit_s"]].sum().reset_index()
            weekly_zones_long = pd.melt(
                weekly_zones.assign(
                    LIT=weekly_zones["lit_s"] / 3600,
                    MIT=weekly_zones["mit_s"] / 3600,
                    HIT=weekly_zones["hit_s"] / 3600,
                )[["year_week", "LIT", "MIT", "HIT"]],
                id_vars="year_week", var_name="Zone", value_name="Hours",
            ).rename(columns={"year_week": "Week"})

            fig_wz = px.bar(
                weekly_zones_long, x="Week", y="Hours", color="Zone",
                color_discrete_map=ZONE_COLORS,
                category_orders={"Zone": ["LIT", "MIT", "HIT"]},
            )
            fig_wz.update_layout(
                **_PLOTLY_BASE,
                margin=_MARGIN,
                height=300,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(color="#9CA3AF")),
                xaxis=dict(tickangle=-45, **_AXIS),
                yaxis=_AXIS,
                bargap=0.2,
            )
            st.plotly_chart(fig_wz, use_container_width=True)

# ── Sport split ────────────────────────────────────────────────────────

st.markdown('<div class="section-header">Sport Split</div>', unsafe_allow_html=True)

cat_hours = df.groupby("category")["duration_h"].sum().reset_index()
fig_split = px.pie(
    cat_hours, values="duration_h", names="category", color="category",
    color_discrete_map=SPORT_COLORS, hole=0.55,
)
fig_split.update_traces(textinfo="percent+label", textposition="outside",
                        textfont=dict(color="#9CA3AF"))
fig_split.update_layout(
    **_PLOTLY_BASE,
    margin=_MARGIN_PIE,
    height=280,
    showlegend=False,
)
col_split, _ = st.columns([1, 2])
with col_split:
    st.plotly_chart(fig_split, use_container_width=True)

# ── Weekly summary table ───────────────────────────────────────────────

st.markdown('<div class="section-header">Weekly Summary</div>', unsafe_allow_html=True)

cat_pivot = df.pivot_table(
    index="year_week", columns="category", values="duration_h",
    aggfunc="sum", fill_value=0,
).reset_index()

weekly_summary = (
    df.groupby("year_week")
    .agg(total=("duration_h", "sum"), kcal=("kcal", "sum"), activities=("sport", "count"))
    .reset_index()
    .merge(cat_pivot, on="year_week")
    .sort_values("year_week", ascending=False)
)
weekly_summary["total"] = weekly_summary["total"].round(1)
weekly_summary["kcal"]  = weekly_summary["kcal"].round(0).astype(int)
for cat in ["Swim", "Bike", "Run", "Other"]:
    if cat in weekly_summary.columns:
        weekly_summary[cat] = weekly_summary[cat].round(1)

cols_order = ["year_week", "total"] + [c for c in ["Swim", "Bike", "Run", "Other"] if c in weekly_summary.columns] + ["kcal", "activities"]
st.dataframe(
    weekly_summary[cols_order].rename(columns={"year_week": "Week", "total": "Total h", "activities": "#"}),
    use_container_width=True,
    hide_index=True,
)
