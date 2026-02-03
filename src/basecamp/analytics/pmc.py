"""Performance Management Chart — CTL, ATL, TSB via exponential weighted moving averages."""

from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy import select

from basecamp.analytics.tss import AthleteThresholds, compute_activity_tss
from basecamp.database import get_session
from basecamp.models import Activity, AthleteSettings


def load_athlete_thresholds() -> AthleteThresholds:
    with get_session() as session:
        settings = session.get(AthleteSettings, 1)
        if not settings:
            return AthleteThresholds()
        return AthleteThresholds(
            ftp=settings.ftp,
            run_ftp=settings.run_ftp,
            max_hr=settings.max_hr,
            resting_hr=settings.resting_hr,
            lthr=settings.lthr,
        )


def get_sport_types() -> list[str]:
    """Get all distinct sport types from the database."""
    with get_session() as session:
        result = session.execute(
            select(Activity.sport_type).distinct().where(Activity.sport_type.isnot(None))
        ).scalars().all()
    return sorted(result)


def compute_pmc(
    ctl_days: int = 42,
    atl_days: int = 7,
    sport_types: list[str] | None = None,
) -> pd.DataFrame:
    """Build a daily PMC dataframe with columns: date, tss, ctl, atl, tsb."""
    thresholds = load_athlete_thresholds()

    with get_session() as session:
        query = select(Activity).order_by(Activity.start_date)
        if sport_types:
            query = query.where(Activity.sport_type.in_(sport_types))
        activities = session.execute(query).scalars().all()

    if not activities:
        return pd.DataFrame(columns=["date", "tss", "ctl", "atl", "tsb"])

    daily_tss: dict[date, float] = {}
    for act in activities:
        activity_date = (act.start_date_local or act.start_date).date()
        tss_value, _ = compute_activity_tss(
            sport_type=act.sport_type or "",
            duration_s=float(act.moving_time or 0),
            weighted_average_watts=act.weighted_average_watts,
            average_watts=act.average_watts,
            average_heartrate=act.average_heartrate,
            thresholds=thresholds,
        )
        if tss_value:
            daily_tss[activity_date] = daily_tss.get(activity_date, 0.0) + tss_value

    first_date = min(daily_tss)
    today = datetime.now(timezone.utc).date()

    date_range = pd.date_range(start=first_date, end=today, freq="D")
    df = pd.DataFrame({"date": date_range.date})
    df["tss"] = df["date"].map(daily_tss).fillna(0.0)

    df["ctl"] = df["tss"].ewm(span=ctl_days, adjust=False).mean()
    df["atl"] = df["tss"].ewm(span=atl_days, adjust=False).mean()
    df["tsb"] = df["ctl"] - df["atl"]

    return df
