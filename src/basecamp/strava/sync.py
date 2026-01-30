import json
from datetime import datetime, timezone

from rich.console import Console

from basecamp.db import Activity, Stream, get_session, init_db
from basecamp.strava.auth import get_authenticated_client

console = Console()

STREAM_TYPES = [
    "time", "heartrate", "watts", "cadence",
    "velocity_smooth", "altitude", "distance", "latlng", "grade_smooth",
]


def _activity_to_dict(act) -> dict:
    """Extract fields from a stravalib Activity object into a dict for our DB model."""
    return dict(
        id=act.id,
        sport_type=str(act.sport_type) if act.sport_type else str(act.type),
        name=act.name,
        description=getattr(act, "description", None),
        start_date=act.start_date,
        timezone=str(act.timezone) if act.timezone else None,
        distance=float(act.distance) if act.distance else None,
        moving_time=int(act.moving_time.total_seconds()) if act.moving_time else None,
        elapsed_time=int(act.elapsed_time.total_seconds()) if act.elapsed_time else None,
        total_elevation_gain=float(act.total_elevation_gain) if act.total_elevation_gain else None,
        average_speed=float(act.average_speed) if act.average_speed else None,
        max_speed=float(act.max_speed) if act.max_speed else None,
        average_heartrate=act.average_heartrate,
        max_heartrate=act.max_heartrate,
        average_watts=act.average_watts,
        max_watts=getattr(act, "max_watts", None),
        weighted_average_watts=getattr(act, "weighted_average_watts", None),
        average_cadence=act.average_cadence,
        calories=act.calories,
        gear_id=act.gear_id,
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
            data["raw_json"] = json.dumps(act.dict() if hasattr(act, "dict") else {"id": act.id}, default=str)
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
