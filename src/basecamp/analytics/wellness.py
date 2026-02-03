"""Wellness data loading for dashboard charts."""

import json
from datetime import date

import pandas as pd
from sqlalchemy import select

from basecamp.database import get_session
from basecamp.models import GarminDailySummary


STATUS_COLORS = {
    "BALANCED": "#2ca02c",  # green
    "LOW": "#ff7f0e",       # orange
    "UNBALANCED": "#d62728", # red
}
DEFAULT_STATUS_COLOR = "#888888"


def load_hrv_data() -> pd.DataFrame:
    """Load HRV data with status and baseline info from raw JSON."""
    with get_session() as session:
        rows = session.execute(
            select(GarminDailySummary)
            .where(GarminDailySummary.hrv_weekly_avg.isnot(None))
            .order_by(GarminDailySummary.date)
        ).scalars().all()

    if not rows:
        return pd.DataFrame()

    records = []
    for row in rows:
        record = {
            "date": row.date,
            "weekly_avg": row.hrv_weekly_avg,
            "last_night": row.hrv_last_night,
            "status": row.hrv_status,
            "color": STATUS_COLORS.get(row.hrv_status, DEFAULT_STATUS_COLOR),
        }

        if row.raw_hrv:
            try:
                raw = json.loads(row.raw_hrv)
                baseline = raw.get("hrvSummary", {}).get("baseline") or {}
                record["baseline_low_upper"] = baseline.get("lowUpper")
                record["baseline_balanced_low"] = baseline.get("balancedLow")
                record["baseline_balanced_upper"] = baseline.get("balancedUpper")
            except (json.JSONDecodeError, KeyError):
                pass

        records.append(record)

    return pd.DataFrame(records)


def get_latest_baseline() -> dict | None:
    """Get the most recent HRV baseline thresholds."""
    with get_session() as session:
        row = session.execute(
            select(GarminDailySummary)
            .where(GarminDailySummary.raw_hrv.isnot(None))
            .order_by(GarminDailySummary.date.desc())
        ).scalars().first()

    if not row or not row.raw_hrv:
        return None

    try:
        raw = json.loads(row.raw_hrv)
        baseline = raw.get("hrvSummary", {}).get("baseline", {})
        if baseline:
            return {
                "low_upper": baseline.get("lowUpper"),
                "balanced_low": baseline.get("balancedLow"),
                "balanced_upper": baseline.get("balancedUpper"),
            }
    except (json.JSONDecodeError, KeyError):
        pass

    return None