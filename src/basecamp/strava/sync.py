import json
import time as time_mod
from datetime import datetime, timezone
from dateutil.parser import parse as parse_date

from rich.console import Console

from ..db import Activity, Stream, get_session, init_db
from ..strava.auth import get_authenticated_client

console = Console()

STREAM_TYPES = [
    "time", "heartrate", "watts", "cadence",
    "velocity_smooth", "altitude", "distance", "latlng", "grade_smooth",
]


def _safe_float(val) -> float | None:
    """Safely convert stravalib quantity (pint) or raw value to float."""
    if val is None:
        return None
    try:
        # pint Quantity objects have a .magnitude attribute
        if hasattr(val, "magnitude"):
            return float(val.magnitude)
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    """Safely convert stravalib quantity or raw value to int (seconds)."""
    f = _safe_float(val)
    return int(f) if f is not None else None


def _activity_to_dict(act) -> dict:
    """Extract fields from a stravalib Activity object into a dict for our DB model.
    Uses getattr throughout since get_activities() returns SummaryActivity objects
    which lack some fields that only DetailedActivity has (e.g. calories, description).
    """
    return dict(
        id=act.id,
        sport_type=str(getattr(act, "sport_type", None) or getattr(act, "type", "")),
        name=getattr(act, "name", None),
        description=getattr(act, "description", None),
        start_date=getattr(act, "start_date", None),
        timezone=str(act.timezone) if getattr(act, "timezone", None) else None,
        distance=_safe_float(getattr(act, "distance", None)),
        moving_time=_safe_int(getattr(act, "moving_time", None)),
        elapsed_time=_safe_int(getattr(act, "elapsed_time", None)),
        total_elevation_gain=_safe_float(getattr(act, "total_elevation_gain", None)),
        average_speed=_safe_float(getattr(act, "average_speed", None)),
        max_speed=_safe_float(getattr(act, "max_speed", None)),
        average_heartrate=_safe_float(getattr(act, "average_heartrate", None)),
        max_heartrate=_safe_float(getattr(act, "max_heartrate", None)),
        average_watts=_safe_float(getattr(act, "average_watts", None)),
        max_watts=_safe_float(getattr(act, "max_watts", None)),
        weighted_average_watts=_safe_float(getattr(act, "weighted_average_watts", None)),
        average_cadence=_safe_float(getattr(act, "average_cadence", None)),
        calories=_safe_float(getattr(act, "calories", None)),
        kilojoules=_safe_float(getattr(act, "kilojoules", None)),
        gear_id=getattr(act, "gear_id", None),
        elev_high=_safe_float(getattr(act, "elev_high", None)),
        elev_low=_safe_float(getattr(act, "elev_low", None)),
        start_date_local=getattr(act, "start_date_local", None),
        device_watts=getattr(act, "device_watts", None),
        trainer=getattr(act, "trainer", None),
        workout_type=_safe_int(getattr(act, "workout_type", None)),
        has_heartrate=getattr(act, "has_heartrate", None),
    )


def _safe_date(val) -> datetime | None:
    """Parse a date string into a datetime object."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return parse_date(str(val))
    except (ValueError, TypeError):
        return None


def _extract_from_raw(raw: dict) -> dict:
    """Extract all tracked fields from a raw Strava JSON response."""
    return dict(
        sport_type=str(raw.get("sport_type") or raw.get("type", "")),
        name=raw.get("name"),
        description=raw.get("description"),
        start_date=_safe_date(raw.get("start_date")),
        timezone=raw.get("timezone"),
        distance=_safe_float(raw.get("distance")),
        moving_time=_safe_int(raw.get("moving_time")),
        elapsed_time=_safe_int(raw.get("elapsed_time")),
        total_elevation_gain=_safe_float(raw.get("total_elevation_gain")),
        average_speed=_safe_float(raw.get("average_speed")),
        max_speed=_safe_float(raw.get("max_speed")),
        average_heartrate=_safe_float(raw.get("average_heartrate")),
        max_heartrate=_safe_float(raw.get("max_heartrate")),
        average_watts=_safe_float(raw.get("average_watts")),
        max_watts=_safe_float(raw.get("max_watts")),
        weighted_average_watts=_safe_float(raw.get("weighted_average_watts")),
        average_cadence=_safe_float(raw.get("average_cadence")),
        calories=_safe_float(raw.get("calories")),
        kilojoules=_safe_float(raw.get("kilojoules")),
        gear_id=raw.get("gear_id"),
        elev_high=_safe_float(raw.get("elev_high")),
        elev_low=_safe_float(raw.get("elev_low")),
        start_date_local=_safe_date(raw.get("start_date_local")),
        device_watts=raw.get("device_watts"),
        trainer=raw.get("trainer"),
        workout_type=_safe_int(raw.get("workout_type")),
        has_heartrate=raw.get("has_heartrate"),
    )


def backfill_from_raw_json():
    """Re-extract all fields from stored raw_json for every activity."""
    init_db()
    session = get_session()
    try:
        activities = session.query(Activity).all()
        count = 0
        for act in activities:
            if not act.raw_json:
                continue
            raw = json.loads(act.raw_json)
            for key, value in _extract_from_raw(raw).items():
                setattr(act, key, value)
            count += 1
        session.commit()
        console.print(f"Backfilled {count} activities from raw_json.")
    finally:
        session.close()


def sync_activities(include_streams: bool = False, stream_limit: int | None = None):
    """Fetch activities from Strava and store them locally."""
    init_db()
    client = get_authenticated_client()
    session = get_session()

    try:
        # Find the most recent activity we have to avoid re-fetching everything
        latest = session.query(Activity).order_by(Activity.start_date.desc()).first()
        after = latest.start_date if latest else None

        if after:
            console.print(f"Fetching activities after {after.date()}...")
        else:
            console.print("Fetching all activities...")

        activities = client.get_activities(after=after)
        new_count = 0
        updated_count = 0

        for act in activities:
            data = _activity_to_dict(act)
            try:
                raw = act.model_dump() if hasattr(act, "model_dump") else act.dict() if hasattr(act, "dict") else {"id": act.id}
            except Exception:
                raw = {"id": act.id}
            data["raw_json"] = json.dumps(raw, default=str)
            data["synced_at"] = datetime.now(timezone.utc)

            existing = session.get(Activity, act.id)
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                updated_count += 1
            else:
                session.add(Activity(**data))
                new_count += 1

        session.commit()
        console.print(f"Synced {new_count} new, {updated_count} updated activities.")

        if include_streams:
            _sync_streams(client, session, limit=stream_limit)

    finally:
        session.close()


def _sync_streams(client, session, limit: int | None = None):
    """Fetch stream data for activities that don't have it yet. Newest first, rate-limit aware."""
    activities = (
        session.query(Activity)
        .filter(Activity.has_streams == False)
        .order_by(Activity.start_date.desc())
        .all()
    )

    if not activities:
        console.print("All activities already have stream data.")
        return

    if limit:
        activities = activities[:limit]

    total = len(activities)
    console.print(f"Fetching streams for {total} activities (newest first)...")

    request_count = 0
    window_start = time_mod.time()

    for i, activity in enumerate(activities):
        # Rate limit: 200 requests per 15 minutes
        request_count += 1
        if request_count >= 190:
            elapsed = time_mod.time() - window_start
            remaining = 900 - elapsed  # 15 min = 900 sec
            if remaining > 0:
                console.print(f"  [yellow]Rate limit approaching, pausing {remaining:.0f}s...[/yellow]")
                time_mod.sleep(remaining + 5)
            request_count = 0
            window_start = time_mod.time()

        try:
            streams = client.get_activity_streams(
                activity.id,
                types=STREAM_TYPES,
            )

            stream_data = {}
            for stream_type in STREAM_TYPES:
                if stream_type in streams:
                    stream_data[stream_type] = json.dumps(
                        streams[stream_type].data, default=str
                    )

            if stream_data:
                existing_stream = session.query(Stream).filter_by(activity_id=activity.id).first()
                if existing_stream:
                    for key, value in stream_data.items():
                        setattr(existing_stream, key, value)
                else:
                    session.add(Stream(
                        activity_id=activity.id,
                        synced_at=datetime.now(timezone.utc),
                        **stream_data,
                    ))

            activity.has_streams = True
            session.commit()

            date_str = activity.start_date.strftime("%Y-%m-%d") if activity.start_date else "?"
            console.print(f"  [{i + 1}/{total}] {date_str} {activity.name}")

        except Exception as e:
            if "rate limit" in str(e).lower() or "429" in str(e):
                console.print(f"  [yellow]Rate limited. Pausing 15 minutes...[/yellow]")
                time_mod.sleep(910)
                request_count = 0
                window_start = time_mod.time()
            else:
                console.print(f"  [{i + 1}/{total}] {activity.name} - [red]error: {e}[/red]")

    console.print("Stream sync complete.")
