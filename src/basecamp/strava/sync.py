import json
from datetime import datetime, timezone

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
        gear_id=getattr(act, "gear_id", None),
    )


def sync_activities(include_streams: bool = False):
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
            _sync_streams(client, session)

    finally:
        session.close()


def _sync_streams(client, session):
    """Fetch stream data for activities that don't have it yet."""
    activities = session.query(Activity).filter(Activity.has_streams == False).all()

    if not activities:
        console.print("All activities already have stream data.")
        return

    console.print(f"Fetching streams for {len(activities)} activities...")

    for i, activity in enumerate(activities):
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

            console.print(f"  [{i + 1}/{len(activities)}] {activity.name} - streams fetched")

        except Exception as e:
            console.print(f"  [{i + 1}/{len(activities)}] {activity.name} - [red]error: {e}[/red]")

    console.print("Stream sync complete.")
