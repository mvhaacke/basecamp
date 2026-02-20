import json
from datetime import date, datetime, timedelta

from sqlalchemy import desc, func, select

from basecamp.analytics.pmc import compute_pmc
from basecamp.analytics.tss import AthleteThresholds, compute_activity_tss
from basecamp.analytics.zones import ZoneThresholds, compute_activity_zones
from basecamp.database import get_session
from basecamp.models import Activity, AthleteSettings, GarminDailySummary, Stream


def _activity_datetime_expr():
    return func.coalesce(Activity.start_date_local, Activity.start_date)


def _build_thresholds(settings: AthleteSettings | None) -> AthleteThresholds:
    if not settings:
        return AthleteThresholds()
    return AthleteThresholds(
        ftp=settings.ftp,
        run_threshold_pace=settings.run_threshold_pace,
        swim_css=settings.swim_css,
        max_hr=settings.max_hr,
        resting_hr=settings.resting_hr,
        lthr=settings.lthr,
    )


def _activity_tss(activity: Activity, thresholds: AthleteThresholds) -> float:
    tss, _ = compute_activity_tss(
        sport_type=activity.sport_type or "",
        duration_s=float(activity.moving_time or 0),
        weighted_average_watts=activity.weighted_average_watts,
        average_watts=activity.average_watts,
        average_heartrate=activity.average_heartrate,
        thresholds=thresholds,
        average_speed_m_per_s=activity.average_speed,
        distance_m=activity.distance,
    )
    return float(tss or 0)


def _sport_bucket(sport_type: str | None) -> str:
    if sport_type in {"Run", "TrailRun", "VirtualRun", "TreadmillRun"}:
        return "Run"
    if sport_type in {"Ride", "VirtualRide", "MountainBikeRide", "GravelRide", "EBikeRide"}:
        return "Bike"
    if sport_type == "Swim":
        return "Swim"
    return "Other"


def build_status_summary() -> dict:
    today = date.today()
    week_ago = today - timedelta(days=7)

    with get_session() as session:
        settings = session.get(AthleteSettings, 1)
        thresholds = _build_thresholds(settings)

        week_activities = session.execute(
            select(Activity).where(_activity_datetime_expr() >= week_ago)
        ).scalars().all()

        weekly_seconds = sum(float(a.moving_time or 0) for a in week_activities)
        weekly_tss = sum(_activity_tss(a, thresholds) for a in week_activities)

        latest_wellness = session.execute(
            select(GarminDailySummary).order_by(desc(GarminDailySummary.date)).limit(1)
        ).scalar_one_or_none()

    pmc = compute_pmc()
    ctl = atl = tsb = None
    if not pmc.empty:
        latest = pmc.iloc[-1]
        ctl = float(latest["ctl"])
        atl = float(latest["atl"])
        tsb = float(latest["tsb"])

    readiness = latest_wellness.training_readiness_score if latest_wellness else None
    if readiness is None:
        nudge = "Sync Garmin to unlock readiness guidance."
    elif readiness >= 75:
        nudge = "Readiness is high. A quality session can fit today."
    elif readiness >= 50:
        nudge = "Moderate readiness. Keep the work controlled."
    else:
        nudge = "Low readiness. Prioritize recovery or an easy day."

    return {
        "readiness_score": readiness,
        "sleep_score": latest_wellness.sleep_score if latest_wellness else None,
        "hrv_last_night": latest_wellness.hrv_last_night if latest_wellness else None,
        "body_battery_high": latest_wellness.body_battery_high if latest_wellness else None,
        "weekly_hours": round(weekly_seconds / 3600, 1),
        "weekly_sessions": len(week_activities),
        "weekly_tss": round(weekly_tss, 1),
        "ctl": ctl,
        "atl": atl,
        "tsb": tsb,
        "nudge": nudge,
    }


def build_calendar_summary(start: date, end: date) -> dict:
    with get_session() as session:
        settings = session.get(AthleteSettings, 1)
        thresholds = _build_thresholds(settings)
        zone_thresholds = ZoneThresholds(
            lthr=settings.lthr if settings else None,
            ftp=settings.ftp if settings else None,
        )
        activities = session.execute(
            select(Activity)
            .where(_activity_datetime_expr() >= start)
            .where(_activity_datetime_expr() < end + timedelta(days=1))
            .order_by(_activity_datetime_expr())
        ).scalars().all()
        activity_ids = [activity.id for activity in activities]
        streams = (
            session.execute(select(Stream).where(Stream.activity_id.in_(activity_ids))).scalars().all()
            if activity_ids
            else []
        )

    streams_by_activity = {stream.activity_id: stream for stream in streams}

    by_day: dict[date, dict[str, float | int | list[dict[str, str | int | None]]]] = {}
    sport_seconds: dict[str, float] = {}
    zone_seconds = {"lit": 0.0, "mit": 0.0, "hit": 0.0}
    for activity in activities:
        activity_dt = activity.start_date_local or activity.start_date
        activity_day = activity_dt.date()
        slot = by_day.setdefault(activity_day, {"sessions": 0, "duration_hours": 0.0, "tss": 0.0, "activities": []})
        duration_seconds = float(activity.moving_time or 0)
        slot["sessions"] += 1
        slot["duration_hours"] += duration_seconds / 3600
        slot["tss"] += _activity_tss(activity, thresholds)
        slot["activities"].append(
            {
                "id": activity.id,
                "name": activity.name,
                "sport_type": activity.sport_type,
                "start_time": activity_dt.strftime("%H:%M"),
                "duration_minutes": int(round(duration_seconds / 60)),
            }
        )
        sport = _sport_bucket(activity.sport_type)
        sport_seconds[sport] = sport_seconds.get(sport, 0.0) + duration_seconds

        zone_values = compute_activity_zones(activity, streams_by_activity.get(activity.id), zone_thresholds)
        if zone_values:
            zone_seconds["lit"] += float(zone_values["lit"])
            zone_seconds["mit"] += float(zone_values["mit"])
            zone_seconds["hit"] += float(zone_values["hit"])

    days = []
    totals = {"sessions": 0, "duration_hours": 0.0, "tss": 0.0}
    cursor = start
    while cursor <= end:
        values = by_day.get(cursor, {"sessions": 0, "duration_hours": 0.0, "tss": 0.0, "activities": []})
        days.append(
            {
                "date": cursor,
                "sessions": int(values["sessions"]),
                "duration_hours": round(float(values["duration_hours"]), 2),
                "tss": round(float(values["tss"]), 1),
                "activities": list(values["activities"]),
            }
        )
        totals["sessions"] += int(values["sessions"])
        totals["duration_hours"] += float(values["duration_hours"])
        totals["tss"] += float(values["tss"])
        cursor += timedelta(days=1)

    totals["duration_hours"] = round(totals["duration_hours"], 1)
    totals["tss"] = round(totals["tss"], 1)
    return {
        "days": days,
        "totals": totals,
        "breakdown": {
            "sport_minutes": [
                {"sport_type": sport, "minutes": int(round(seconds / 60))}
                for sport, seconds in sorted(sport_seconds.items(), key=lambda item: item[1], reverse=True)
            ],
            "zone_minutes": {
                "lit": int(round(zone_seconds["lit"] / 60)),
                "mit": int(round(zone_seconds["mit"] / 60)),
                "hit": int(round(zone_seconds["hit"] / 60)),
            },
        },
    }


def list_recent_activities(limit: int) -> list[dict]:
    with get_session() as session:
        activities = session.execute(
            select(Activity).order_by(desc(_activity_datetime_expr())).limit(limit)
        ).scalars().all()
    return [
        {
            "id": a.id,
            "start_date": (a.start_date_local or a.start_date or datetime.now()).isoformat(),
            "sport_type": a.sport_type,
            "name": a.name,
        }
        for a in activities
    ]


def get_activity_detail(activity_id: int) -> dict | None:
    with get_session() as session:
        activity = session.get(Activity, activity_id)
        if not activity:
            return None

        stream = session.execute(select(Stream).where(Stream.activity_id == activity_id)).scalar_one_or_none()
        activity_day = (activity.start_date_local or activity.start_date).date()
        wellness = session.get(GarminDailySummary, activity_day)

    def _parse_stream(value: str | None) -> list[float]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []

    return {
        "id": activity.id,
        "sport_type": activity.sport_type,
        "name": activity.name,
        "start_date": (activity.start_date_local or activity.start_date or datetime.now()).isoformat(),
        "duration_s": int(activity.moving_time or 0),
        "distance_m": activity.distance,
        "average_heartrate": activity.average_heartrate,
        "average_watts": activity.average_watts,
        "calories": activity.computed_calories,
        "average_speed_m_per_s": activity.average_speed,
        "stream_time": _parse_stream(stream.time if stream else None),
        "stream_heartrate": _parse_stream(stream.heartrate if stream else None),
        "stream_watts": _parse_stream(stream.watts if stream else None),
        "stream_velocity_smooth": _parse_stream(stream.velocity_smooth if stream else None),
        "wellness": {
            "sleep_score": wellness.sleep_score if wellness else None,
            "hrv_last_night": wellness.hrv_last_night if wellness else None,
            "training_readiness_score": wellness.training_readiness_score if wellness else None,
            "body_battery_high": wellness.body_battery_high if wellness else None,
            "stress_avg": wellness.stress_avg if wellness else None,
        },
    }
