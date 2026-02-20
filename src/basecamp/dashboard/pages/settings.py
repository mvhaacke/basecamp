"""Settings page — athlete thresholds and data sync."""

import subprocess
import sys
from datetime import datetime, timezone

import streamlit as st
from sqlalchemy import func, select

from basecamp.database import get_session
from basecamp.models import Activity, AthleteSettings, GarminDailySummary


def seconds_to_pace(seconds: float | None) -> tuple[int, int]:
    """Convert seconds to (minutes, seconds) tuple."""
    if not seconds:
        return (0, 0)
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return (mins, secs)


def pace_to_seconds(mins: int, secs: int) -> float | None:
    """Convert (minutes, seconds) to total seconds. Returns None if zero."""
    total = mins * 60 + secs
    return float(total) if total > 0 else None


st.markdown('<div class="section-header">Athlete Thresholds</div>', unsafe_allow_html=True)

with get_session() as session:
    settings = session.get(AthleteSettings, 1)

current = {
    "ftp": int(settings.ftp) if settings and settings.ftp else None,
    "run_pace": settings.run_threshold_pace if settings else None,
    "swim_css": settings.swim_css if settings else None,
    "max_hr": int(settings.max_hr) if settings and settings.max_hr else None,
    "resting_hr": int(settings.resting_hr) if settings and settings.resting_hr else None,
    "lthr": int(settings.lthr) if settings and settings.lthr else None,
    "weight_kg": float(settings.weight_kg) if settings and settings.weight_kg else None,
    "age": int(settings.age) if settings and settings.age else None,
    "sex": settings.sex if settings and settings.sex else None,
}

run_pace_mins, run_pace_secs = seconds_to_pace(current["run_pace"])
swim_css_mins, swim_css_secs = seconds_to_pace(current["swim_css"])

has_settings = current["ftp"] or current["run_pace"] or current["max_hr"] or current["weight_kg"]
if not has_settings:
    st.warning("Set your thresholds to enable power- and HR-based TSS calculation.")

col1, col2 = st.columns(2)

with col1:
    with st.form("settings_form"):
        weight_kg = st.number_input("Weight (kg)", value=current["weight_kg"] or 0.0, min_value=0.0, step=0.5, format="%.1f")
        age = st.number_input("Age", value=current["age"] or 0, min_value=0, step=1)
        sex = st.selectbox("Sex", ["M", "F"], index=0 if current["sex"] != "F" else 1)
        ftp = st.number_input("Cycling FTP (W)", value=current["ftp"] or 0, min_value=0, step=5)

        st.markdown("**Run Threshold Pace** (per km)")
        rp_col1, rp_col2 = st.columns(2)
        with rp_col1:
            run_mins = st.number_input("min", value=run_pace_mins, min_value=0, max_value=15, step=1, key="run_mins")
        with rp_col2:
            run_secs = st.number_input("sec", value=run_pace_secs, min_value=0, max_value=59, step=1, key="run_secs")

        st.markdown("**Swim CSS** (per 100m)")
        sw_col1, sw_col2 = st.columns(2)
        with sw_col1:
            swim_mins = st.number_input("min", value=swim_css_mins, min_value=0, max_value=5, step=1, key="swim_mins")
        with sw_col2:
            swim_secs = st.number_input("sec", value=swim_css_secs, min_value=0, max_value=59, step=1, key="swim_secs")

        max_hr = st.number_input("Max HR (bpm)", value=current["max_hr"] or 0, min_value=0, step=1)
        resting_hr = st.number_input("Resting HR (bpm)", value=current["resting_hr"] or 0, min_value=0, step=1)
        lthr = st.number_input("LTHR (bpm)", value=current["lthr"] or 0, min_value=0, step=1)
        submitted = st.form_submit_button("Save Thresholds")

        if submitted:
            with get_session() as session:
                settings = session.get(AthleteSettings, 1)
                if not settings:
                    settings = AthleteSettings(id=1)
                    session.add(settings)
                settings.weight_kg = weight_kg or None
                settings.age = age or None
                settings.sex = sex
                settings.ftp = ftp or None
                settings.run_threshold_pace = pace_to_seconds(run_mins, run_secs)
                settings.swim_css = pace_to_seconds(swim_mins, swim_secs)
                settings.max_hr = max_hr or None
                settings.resting_hr = resting_hr or None
                settings.lthr = lthr or None
                settings.updated_at = datetime.now(timezone.utc)
                session.commit()
            st.success("Thresholds saved!")
            st.rerun()

st.markdown('<div class="section-header">Data Sync</div>', unsafe_allow_html=True)

with get_session() as session:
    strava_count = session.execute(select(func.count(Activity.id))).scalar()
    strava_latest = session.execute(
        select(Activity.synced_at).order_by(Activity.synced_at.desc()).limit(1)
    ).scalar()

    garmin_count = session.execute(select(func.count(GarminDailySummary.date))).scalar()
    garmin_latest = session.execute(
        select(GarminDailySummary.synced_at).order_by(GarminDailySummary.synced_at.desc()).limit(1)
    ).scalar()

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Strava**")
    st.text(f"Activities: {strava_count}")
    if strava_latest:
        st.text(f"Last sync: {strava_latest.strftime('%Y-%m-%d %H:%M')}")
    else:
        st.text("Last sync: Never")

    bcol1, bcol2 = st.columns(2)
    with bcol1:
        if st.button("Sync", type="primary", use_container_width=True, key="strava_sync"):
            with st.spinner("Syncing from Strava..."):
                result = subprocess.run(
                    [sys.executable, "-m", "basecamp.cli", "strava", "sync"],
                    capture_output=True,
                    text=True,
                )
            if result.returncode == 0:
                st.success("Sync complete!")
                st.rerun()
            else:
                st.error("Sync failed")
                st.code(result.stderr or result.stdout)
    with bcol2:
        if st.button("Backfill", use_container_width=True, key="strava_backfill"):
            with st.spinner("Re-extracting from raw JSON..."):
                result = subprocess.run(
                    [sys.executable, "-m", "basecamp.cli", "strava", "backfill"],
                    capture_output=True,
                    text=True,
                )
            if result.returncode == 0:
                st.success("Backfill complete!")
                st.rerun()
            else:
                st.error("Backfill failed")
                st.code(result.stderr or result.stdout)

with col2:
    st.markdown("**Garmin**")
    st.text(f"Days: {garmin_count}")
    if garmin_latest:
        st.text(f"Last sync: {garmin_latest.strftime('%Y-%m-%d %H:%M')}")
    else:
        st.text("Last sync: Never")

    gcol1, gcol2 = st.columns(2)
    with gcol1:
        if st.button("Sync", type="primary", use_container_width=True, key="garmin_sync"):
            with st.spinner("Syncing from Garmin..."):
                result = subprocess.run(
                    [sys.executable, "-m", "basecamp.cli", "garmin", "sync"],
                    capture_output=True,
                    text=True,
                )
            if result.returncode == 0:
                st.success("Sync complete!")
                st.rerun()
            else:
                st.error("Sync failed")
                st.code(result.stderr or result.stdout)
    with gcol2:
        if st.button("Backfill", use_container_width=True, key="garmin_backfill"):
            with st.spinner("Re-extracting from raw JSON..."):
                result = subprocess.run(
                    [sys.executable, "-m", "basecamp.cli", "garmin", "backfill"],
                    capture_output=True,
                    text=True,
                )
            if result.returncode == 0:
                st.success("Backfill complete!")
                st.rerun()
            else:
                st.error("Backfill failed")
                st.code(result.stderr or result.stdout)