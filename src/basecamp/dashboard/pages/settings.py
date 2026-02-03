"""Settings page — athlete thresholds and data sync."""

import subprocess
import sys
from datetime import datetime, timezone

import streamlit as st
from sqlalchemy import func, select

from basecamp.database import get_session
from basecamp.models import Activity, AthleteSettings, GarminDailySummary

st.title("Settings")

# --- Athlete Thresholds ---

st.subheader("Athlete Thresholds")

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
    st.warning("Set your thresholds to enable power- and HR-based TSS calculation.")

col1, col2 = st.columns(2)

with col1:
    with st.form("settings_form"):
        ftp = st.number_input("Cycling FTP (W)", value=current["ftp"] or 0, min_value=0, step=5)
        run_ftp = st.number_input("Running FTP (W)", value=current["run_ftp"] or 0, min_value=0, step=5)
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
                settings.ftp = ftp or None
                settings.run_ftp = run_ftp or None
                settings.max_hr = max_hr or None
                settings.resting_hr = resting_hr or None
                settings.lthr = lthr or None
                settings.updated_at = datetime.now(timezone.utc)
                session.commit()
            st.success("Thresholds saved!")
            st.rerun()

# --- Data Sync ---

st.subheader("Data Sync")

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

    if st.button("Sync Strava", type="primary", use_container_width=True):
        with st.spinner("Syncing from Strava..."):
            result = subprocess.run(
                [sys.executable, "-m", "basecamp.cli", "strava", "sync"],
                capture_output=True,
                text=True,
            )
        if result.returncode == 0:
            st.success("Strava sync complete!")
            st.rerun()
        else:
            st.error("Sync failed")
            st.code(result.stderr or result.stdout)

with col2:
    st.markdown("**Garmin**")
    st.text(f"Days: {garmin_count}")
    if garmin_latest:
        st.text(f"Last sync: {garmin_latest.strftime('%Y-%m-%d %H:%M')}")
    else:
        st.text("Last sync: Never")

    if st.button("Sync Garmin", type="primary", use_container_width=True):
        with st.spinner("Syncing from Garmin..."):
            result = subprocess.run(
                [sys.executable, "-m", "basecamp.cli", "garmin", "sync"],
                capture_output=True,
                text=True,
            )
        if result.returncode == 0:
            st.success("Garmin sync complete!")
            st.rerun()
        else:
            st.error("Sync failed")
            st.code(result.stderr or result.stdout)