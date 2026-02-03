"""Streamlit dashboard for training load analysis (PMC chart)."""

from datetime import date, datetime, timezone

import plotly.graph_objects as go
import streamlit as st
from dateutil.relativedelta import relativedelta

from basecamp.analytics.pmc import compute_pmc
from basecamp.database import get_session, init_db
from basecamp.models import AthleteSettings

st.set_page_config(page_title="Basecamp", layout="wide")

init_db()


# --- Sidebar: Athlete Settings ---

st.sidebar.header("Athlete Settings")

with get_session() as session:
    settings = session.get(AthleteSettings, 1)

current = {
    "ftp": int(settings.ftp) if settings and settings.ftp else None,
    "run_ftp": int(settings.run_ftp) if settings and settings.run_ftp else None,
    "max_hr": int(settings.max_hr) if settings and settings.max_hr else None,
    "resting_hr": int(settings.resting_hr) if settings and settings.resting_hr else None,
    "lthr": int(settings.lthr) if settings and settings.lthr else None,
}

has_settings = any(v is not None for v in current.values())
if not has_settings:
    st.sidebar.warning("Set your thresholds to enable power- and HR-based TSS.")

with st.sidebar.form("settings_form"):
    ftp = st.number_input("Cycling FTP (W)", value=current["ftp"] or 0, min_value=0, step=5)
    run_ftp = st.number_input("Running FTP (W)", value=current["run_ftp"] or 0, min_value=0, step=5)
    max_hr = st.number_input("Max HR (bpm)", value=current["max_hr"] or 0, min_value=0, step=1)
    resting_hr = st.number_input("Resting HR (bpm)", value=current["resting_hr"] or 0, min_value=0, step=1)
    lthr = st.number_input("LTHR (bpm)", value=current["lthr"] or 0, min_value=0, step=1)
    submitted = st.form_submit_button("Save")

    if submitted:
        with get_session() as session:
            settings = session.get(AthleteSettings, 1)
            if not settings:
                settings = AthleteSettings(id=1)
                session.add(settings)
            settings.ftp = ftp or None
            settings.run_ftp = run_ftp or None
            settings.max_hr = max_hr or None
            settings.resting_hr = resting_hr or None
            settings.lthr = lthr or None
            settings.updated_at = datetime.now(timezone.utc)
            session.commit()
        st.rerun()


# --- Main: PMC Chart ---

st.title("Performance Management Chart")

time_range = st.selectbox(
    "Time range",
    ["3 months", "6 months", "12 months", "24 months", "All time"],
    index=2,
)

df = compute_pmc()

if df.empty:
    st.info("No activities found. Run `basecamp strava sync` first.")
    st.stop()

range_months = {"3 months": 3, "6 months": 6, "12 months": 12, "24 months": 24}
if time_range in range_months:
    cutoff = date.today() - relativedelta(months=range_months[time_range])
    df = df[df["date"] >= cutoff]

if df.empty:
    st.info("No activities in the selected time range.")
    st.stop()

latest = df.iloc[-1]
cols = st.columns(3)
cols[0].metric("CTL (Fitness)", f"{latest['ctl']:.0f}")
cols[1].metric("ATL (Fatigue)", f"{latest['atl']:.0f}")
cols[2].metric("TSB (Form)", f"{latest['tsb']:.0f}")

fig = go.Figure()

fig.add_trace(go.Bar(
    x=df["date"],
    y=df["tss"],
    name="Daily TSS",
    marker_color="rgba(180, 180, 180, 0.4)",
    yaxis="y2",
))

fig.add_trace(go.Scatter(
    x=df["date"], y=df["ctl"], name="CTL (Fitness)",
    line=dict(color="#1f77b4", width=2),
))

fig.add_trace(go.Scatter(
    x=df["date"], y=df["atl"], name="ATL (Fatigue)",
    line=dict(color="#d62728", width=2),
))

fig.add_trace(go.Scatter(
    x=df["date"], y=df["tsb"], name="TSB (Form)",
    line=dict(color="#2ca02c", width=1.5),
    fill="tozeroy",
    fillcolor="rgba(44, 160, 44, 0.1)",
))

fig.update_layout(
    height=500,
    margin=dict(l=40, r=40, t=30, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    yaxis=dict(title="CTL / ATL / TSB", side="left"),
    yaxis2=dict(title="TSS", side="right", overlaying="y", showgrid=False),
    hovermode="x unified",
    shapes=[dict(
        type="line", y0=0, y1=0, x0=df["date"].iloc[0], x1=df["date"].iloc[-1],
        xref="x", yref="y", line=dict(color="gray", width=1, dash="dot"),
    )],
)

st.plotly_chart(fig, width="stretch")
