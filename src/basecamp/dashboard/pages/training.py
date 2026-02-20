"""Training breakdown page — sport distribution, zone analysis, weekly summaries."""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select

from basecamp.analytics.zones import compute_activity_zones, load_zone_thresholds
from basecamp.database import get_session
from basecamp.models import Activity, Stream

st.title("Training Breakdown")

# --- Sport category mapping ---

SPORT_CATEGORIES = {
    "Swim": "Swim",
    "Run": "Run",
    "TrailRun": "Run",
    "VirtualRun": "Run",
    "Ride": "Bike",
    "VirtualRide": "Bike",
    "MountainBikeRide": "Bike",
    "GravelRide": "Bike",
    "EBikeRide": "Bike",
}

CATEGORY_COLORS = {
    "Swim": "#3498db",  # Blue
    "Bike": "#e74c3c",  # Red
    "Run": "#2ecc71",   # Green
    "Other": "#95a5a6", # Gray
}

def get_category(sport_type: str) -> str:
    return SPORT_CATEGORIES.get(sport_type, "Other")

# --- Time period selector ---

period = st.selectbox(
    "Time period",
    ["Last 4 weeks", "Last 8 weeks", "Last 12 weeks", "This year", "All time"],
    index=1,
)

period_map = {
    "Last 4 weeks": 28,
    "Last 8 weeks": 56,
    "Last 12 weeks": 84,
    "This year": (date.today() - date(date.today().year, 1, 1)).days,
    "All time": 10000,
}
days_back = period_map[period]
cutoff = date.today() - timedelta(days=days_back)

# --- Load data ---

thresholds = load_zone_thresholds()
has_thresholds = thresholds.lthr or thresholds.ftp

if not has_thresholds:
    st.warning("Set LTHR or FTP in Settings to enable zone analysis.")

with get_session() as session:
    activities = session.execute(
        select(Activity)
        .where(Activity.start_date_local >= cutoff)
        .order_by(Activity.start_date_local)
    ).scalars().all()

    # Pre-load streams for zone calculation
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

# --- Process activities ---

rows = []
for act in activities:
    stream = streams.get(act.id)
    zones = compute_activity_zones(act, stream, thresholds) if has_thresholds else None
    sport = act.sport_type or "Other"

    rows.append({
        "date": (act.start_date_local or act.start_date).date(),
        "week": (act.start_date_local or act.start_date).date().isocalendar()[1],
        "year": (act.start_date_local or act.start_date).date().year,
        "sport": sport,
        "category": get_category(sport),
        "duration_s": act.moving_time or 0,
        "duration_h": (act.moving_time or 0) / 3600,
        "kcal": act.computed_calories or 0,
        "lit_s": zones["lit"] if zones else 0,
        "mit_s": zones["mit"] if zones else 0,
        "hit_s": zones["hit"] if zones else 0,
    })

df = pd.DataFrame(rows)
df["year_week"] = df["year"].astype(str) + "-W" + df["week"].astype(str).str.zfill(2)

# --- Summary metrics ---

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Hours", f"{df['duration_h'].sum():.1f}")
col2.metric("Total kcal", f"{df['kcal'].sum():,.0f}")
col3.metric("Activities", len(df))
col4.metric("Weeks", df["year_week"].nunique())

# --- Weekly stacked bar chart (by category) ---

st.subheader("Weekly Volume by Category")

weekly_cat = df.groupby(["year_week", "category"])["duration_h"].sum().reset_index()
weekly_cat = weekly_cat.pivot(index="year_week", columns="category", values="duration_h").fillna(0)
weekly_cat = weekly_cat.reset_index()

# Melt for plotly
weekly_cat_long = weekly_cat.melt(id_vars=["year_week"], var_name="category", value_name="hours")

fig_cat = px.bar(
    weekly_cat_long,
    x="year_week",
    y="hours",
    color="category",
    color_discrete_map=CATEGORY_COLORS,
    category_orders={"category": ["Swim", "Bike", "Run", "Other"]},
    title=None,
    labels={"year_week": "Week", "hours": "Hours", "category": "Category"},
)
fig_cat.update_layout(
    height=350,
    margin=dict(l=40, r=40, t=20, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    xaxis_tickangle=-45,
)
st.plotly_chart(fig_cat, width="stretch")

# --- Zone distribution ---

if has_thresholds:
    st.subheader("Zone Distribution")

    total_lit = df["lit_s"].sum()
    total_mit = df["mit_s"].sum()
    total_hit = df["hit_s"].sum()
    total_zone_time = total_lit + total_mit + total_hit

    if total_zone_time > 0:
        col1, col2 = st.columns(2)

        with col1:
            # Overall zone pie
            zone_data = pd.DataFrame({
                "zone": ["LIT", "MIT", "HIT"],
                "hours": [total_lit / 3600, total_mit / 3600, total_hit / 3600],
                "pct": [
                    total_lit / total_zone_time * 100,
                    total_mit / total_zone_time * 100,
                    total_hit / total_zone_time * 100,
                ],
            })

            fig_zone = px.pie(
                zone_data,
                values="hours",
                names="zone",
                color="zone",
                color_discrete_map={"LIT": "#2ecc71", "MIT": "#f39c12", "HIT": "#e74c3c"},
                hole=0.4,
            )
            fig_zone.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=30, b=20),
                title=dict(text="Overall Zone Split", x=0.5),
            )
            fig_zone.update_traces(
                textinfo="percent+label",
                textposition="outside",
            )
            st.plotly_chart(fig_zone, width="stretch")

        with col2:
            # Zone breakdown text
            st.markdown("**Zone Summary**")
            st.markdown(f"- **LIT** (< 80% LTHR / < 75% FTP): {total_lit/3600:.1f}h ({total_lit/total_zone_time*100:.0f}%)")
            st.markdown(f"- **MIT** (80-100% LTHR / 75-100% FTP): {total_mit/3600:.1f}h ({total_mit/total_zone_time*100:.0f}%)")
            st.markdown(f"- **HIT** (> LTHR / > FTP): {total_hit/3600:.1f}h ({total_hit/total_zone_time*100:.0f}%)")

            # Polarized check
            lit_pct = total_lit / total_zone_time * 100
            if lit_pct >= 75:
                st.success(f"Good polarization: {lit_pct:.0f}% LIT")
            elif lit_pct >= 60:
                st.warning(f"Moderate polarization: {lit_pct:.0f}% LIT")
            else:
                st.error(f"Low polarization: {lit_pct:.0f}% LIT — consider more easy volume")

        # Weekly zone stacked bar
        st.subheader("Weekly Zone Distribution")

        weekly_zones = df.groupby("year_week")[["lit_s", "mit_s", "hit_s"]].sum().reset_index()
        weekly_zones["LIT"] = weekly_zones["lit_s"] / 3600
        weekly_zones["MIT"] = weekly_zones["mit_s"] / 3600
        weekly_zones["HIT"] = weekly_zones["hit_s"] / 3600

        weekly_zones_long = weekly_zones[["year_week", "LIT", "MIT", "HIT"]].melt(
            id_vars=["year_week"], var_name="zone", value_name="hours"
        )

        fig_weekly_zones = px.bar(
            weekly_zones_long,
            x="year_week",
            y="hours",
            color="zone",
            color_discrete_map={"LIT": "#2ecc71", "MIT": "#f39c12", "HIT": "#e74c3c"},
            title=None,
            labels={"year_week": "Week", "hours": "Hours", "zone": "Zone"},
        )
        fig_weekly_zones.update_layout(
            height=300,
            margin=dict(l=40, r=40, t=20, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            xaxis_tickangle=-45,
            barmode="stack",
        )
        st.plotly_chart(fig_weekly_zones, width="stretch")

        # Zone breakdown by category
        st.subheader("Zone Distribution by Category")

        zone_by_cat = df.groupby("category")[["lit_s", "mit_s", "hit_s"]].sum().reset_index()
        zone_by_cat["LIT"] = zone_by_cat["lit_s"] / 3600
        zone_by_cat["MIT"] = zone_by_cat["mit_s"] / 3600
        zone_by_cat["HIT"] = zone_by_cat["hit_s"] / 3600

        zone_by_cat_long = zone_by_cat[["category", "LIT", "MIT", "HIT"]].melt(
            id_vars=["category"], var_name="zone", value_name="hours"
        )

        fig_zone_cat = px.bar(
            zone_by_cat_long,
            x="category",
            y="hours",
            color="zone",
            color_discrete_map={"LIT": "#2ecc71", "MIT": "#f39c12", "HIT": "#e74c3c"},
            title=None,
            labels={"category": "Category", "hours": "Hours", "zone": "Zone"},
            barmode="group",
        )
        fig_zone_cat.update_layout(
            height=300,
            margin=dict(l=40, r=40, t=20, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            xaxis=dict(categoryorder="array", categoryarray=["Swim", "Bike", "Run", "Other"]),
        )
        st.plotly_chart(fig_zone_cat, width="stretch")
    else:
        st.info("No zone data available. Ensure activities have HR or power data.")

# --- Category split donut ---

st.subheader("Category Distribution")

col1, col2 = st.columns(2)

with col1:
    cat_hours = df.groupby("category")["duration_h"].sum().reset_index()
    fig_cat_pie = px.pie(
        cat_hours,
        values="duration_h",
        names="category",
        color="category",
        color_discrete_map=CATEGORY_COLORS,
        hole=0.4,
        title="By Duration",
    )
    fig_cat_pie.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
    fig_cat_pie.update_traces(textinfo="percent+label", textposition="outside")
    st.plotly_chart(fig_cat_pie, width="stretch")

with col2:
    cat_kcal = df.groupby("category")["kcal"].sum().reset_index()
    fig_kcal_pie = px.pie(
        cat_kcal,
        values="kcal",
        names="category",
        color="category",
        color_discrete_map=CATEGORY_COLORS,
        hole=0.4,
        title="By Calories",
    )
    fig_kcal_pie.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
    fig_kcal_pie.update_traces(textinfo="percent+label", textposition="outside")
    st.plotly_chart(fig_kcal_pie, width="stretch")

# --- Weekly summary table ---

st.subheader("Weekly Summary")

# Calculate hours per category per week
cat_pivot = df.pivot_table(
    index="year_week",
    columns="category",
    values="duration_h",
    aggfunc="sum",
    fill_value=0,
).reset_index()

weekly_summary = df.groupby("year_week").agg({
    "duration_h": "sum",
    "kcal": "sum",
    "sport": "count",
}).rename(columns={"sport": "activities", "duration_h": "total"}).reset_index()

# Merge category hours
weekly_summary = weekly_summary.merge(cat_pivot, on="year_week")
weekly_summary = weekly_summary.sort_values("year_week", ascending=False)

# Format columns
weekly_summary["total"] = weekly_summary["total"].round(1)
weekly_summary["kcal"] = weekly_summary["kcal"].round(0).astype(int)
for cat in ["Swim", "Bike", "Run", "Other"]:
    if cat in weekly_summary.columns:
        weekly_summary[cat] = weekly_summary[cat].round(1)

# Reorder columns
cols = ["year_week", "total"]
for cat in ["Swim", "Bike", "Run", "Other"]:
    if cat in weekly_summary.columns:
        cols.append(cat)
cols.extend(["kcal", "activities"])
weekly_summary = weekly_summary[cols]

st.dataframe(
    weekly_summary.rename(columns={
        "year_week": "Week",
        "total": "Total",
        "kcal": "kcal",
        "activities": "#",
    }),
    width="stretch",
    hide_index=True,
)