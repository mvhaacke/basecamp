import json
import time as time_mod
from datetime import datetime, timezone
from dateutil.parser import parse as parse_date

from rich.console import Console

from ..database import get_session
from ..models import Activity, AthleteSettings, Stream
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


# Metabolic cost in kcal per kg per km
KCAL_PER_KG_PER_KM = {
    "Run": 1.0,
    "TrailRun": 1.1,
    "Swim": 3.2,
    "Hike": 1.0,
    "Walk": 0.8,
}

# MET values for duration-based calorie estimation of non-distance sports
MET_BY_SPORT: dict[str, float] = {
    "WeightTraining": 4.0,
    "Rowing": 7.0,
    "Yoga": 2.5,
    "Elliptical": 5.0,
    "StairStepper": 6.0,
    "Crossfit": 8.0,
    "IceSkate": 7.0,
    "Kayaking": 5.0,
}


def compute_calories(
    sport_type: str | None,
    distance_m: float | None,
    strava_kj: float | None,
    weight_kg: float | None,
    duration_s: float | None = None,
    avg_hr: float | None = None,
    max_hr: int | None = None,
    resting_hr: int | None = None,
    age: int | None = None,
    sex: str | None = None,
) -> float | None:
    """Compute kcal for an activity.

    Priority:
    1. HR-based (Keytel formula) — most accurate when HR data and athlete profile are available
    2. Power-based — cycling with power meter kJ ≈ kcal
    3. Distance-based — run/swim/hike with body-weight metabolic cost
    4. MET duration-based — gym/indoor sports without distance
    5. Strava kJ fallback
    """
    # 1. HR-based calorie estimate (Keytel formula)
    if (
        avg_hr and max_hr and resting_hr and weight_kg and age and sex
        and duration_s and avg_hr > resting_hr
    ):
        duration_min = duration_s / 60.0
        if sex == "M":
            kcal_per_min = (0.6309 * avg_hr + 0.1988 * weight_kg + 0.2017 * age - 55.0969) / 4.184
        else:
            kcal_per_min = (0.4472 * avg_hr - 0.1263 * weight_kg + 0.074 * age - 20.4022) / 4.184
        if kcal_per_min > 0:
            return kcal_per_min * duration_min

    # 2. Power-based for cycling
    if sport_type in ("Ride", "VirtualRide"):
        return strava_kj  # kJ from power meter ≈ kcal

    # 3. Distance-based for running/swimming/hiking
    if sport_type in KCAL_PER_KG_PER_KM and distance_m and weight_kg:
        distance_km = distance_m / 1000
        return distance_km * weight_kg * KCAL_PER_KG_PER_KM[sport_type]

    # 4. MET-based for gym/indoor sports
    if sport_type in MET_BY_SPORT and weight_kg and duration_s:
        hours = duration_s / 3600.0
        return MET_BY_SPORT[sport_type] * weight_kg * hours

    return strava_kj


def backfill_from_raw_json():
    """Re-extract all fields from stored raw_json and compute calories."""
    with get_session() as session:
        settings = session.get(AthleteSettings, 1)
        weight_kg = settings.weight_kg if settings else None
        max_hr = settings.max_hr if settings else None
        resting_hr = settings.resting_hr if settings else None
        age = settings.age if settings else None
        sex = settings.sex if settings else None

        if not weight_kg:
            console.print("[yellow]Warning: No weight set in athlete settings. Run/swim kcal will use Strava estimates.[/yellow]")

        activities = session.query(Activity).all()
        count = 0
        for act in activities:
            if not act.raw_json:
                continue
            raw = json.loads(act.raw_json)
            for key, value in _extract_from_raw(raw).items():
                setattr(act, key, value)

            act.computed_calories = compute_calories(
                sport_type=act.sport_type,
                distance_m=act.distance,
                strava_kj=act.kilojoules,
                weight_kg=weight_kg,
                duration_s=act.moving_time,
                avg_hr=act.average_heartrate,
                max_hr=max_hr,
                resting_hr=resting_hr,
                age=age,
                sex=sex,
            )
            count += 1
        session.commit()
        console.print(f"Backfilled {count} activities from raw_json.")


def sync_activities(include_streams: bool = False, stream_limit: int | None = None):
    """Fetch raw activity data from Strava API and store it. Then run backfill to extract fields."""
    client = get_authenticated_client()

    with get_session() as session:
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
            # Only store the raw JSON and minimal identifiers
            try:
                raw = act.model_dump() if hasattr(act, "model_dump") else act.dict() if hasattr(act, "dict") else {"id": act.id}
            except Exception:
                raw = {"id": act.id}

            existing = session.get(Activity, act.id)
            if existing:
                existing.raw_json = json.dumps(raw, default=str)
                existing.synced_at = datetime.now(timezone.utc)
                updated_count += 1
            else:
                session.add(Activity(
                    id=act.id,
                    raw_json=json.dumps(raw, default=str),
                    synced_at=datetime.now(timezone.utc),
                ))
                new_count += 1

        session.commit()
        console.print(f"Synced {new_count} new, {updated_count} updated activities.")

        if include_streams:
            _sync_streams(client, session, limit=stream_limit)

    # Extract fields from raw JSON
    backfill_from_raw_json()


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
