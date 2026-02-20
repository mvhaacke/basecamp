"""Heart rate and power zone calculations using a 3-zone model (LIT/MIT/HIT)."""

import json
from dataclasses import dataclass

from basecamp.database import get_session
from basecamp.models import Activity, AthleteSettings, Stream


@dataclass
class ZoneThresholds:
    lthr: int | None = None
    ftp: float | None = None


# Zone boundaries as fraction of threshold
# LIT < 80%, MIT 80-100%, HIT > 100%
HR_LIT_UPPER = 0.80
HR_HIT_LOWER = 1.00

# Power zones slightly different: LIT < 75%, MIT 75-100%, HIT > 100%
POWER_LIT_UPPER = 0.75
POWER_HIT_LOWER = 1.00


def load_zone_thresholds() -> ZoneThresholds:
    with get_session() as session:
        settings = session.get(AthleteSettings, 1)
        if not settings:
            return ZoneThresholds()
        return ZoneThresholds(
            lthr=settings.lthr,
            ftp=settings.ftp,
        )


def compute_time_in_zones_from_stream(
    stream_data: list[int | float],
    threshold: float,
    lit_upper_frac: float,
    hit_lower_frac: float,
    sample_interval_s: float = 1.0,
) -> dict[str, float]:
    """Compute seconds spent in each zone from a stream (HR or power)."""
    lit_seconds = 0.0
    mit_seconds = 0.0
    hit_seconds = 0.0

    lit_boundary = threshold * lit_upper_frac
    hit_boundary = threshold * hit_lower_frac

    for value in stream_data:
        if value is None:
            continue
        if value < lit_boundary:
            lit_seconds += sample_interval_s
        elif value >= hit_boundary:
            hit_seconds += sample_interval_s
        else:
            mit_seconds += sample_interval_s

    return {"lit": lit_seconds, "mit": mit_seconds, "hit": hit_seconds}


def compute_time_in_zones_from_average(
    duration_s: float,
    avg_value: float,
    threshold: float,
    lit_upper_frac: float,
    hit_lower_frac: float,
) -> dict[str, float]:
    """Estimate zone from average value (fallback when no stream data)."""
    lit_boundary = threshold * lit_upper_frac
    hit_boundary = threshold * hit_lower_frac

    if avg_value < lit_boundary:
        return {"lit": duration_s, "mit": 0.0, "hit": 0.0}
    elif avg_value >= hit_boundary:
        return {"lit": 0.0, "mit": 0.0, "hit": duration_s}
    else:
        return {"lit": 0.0, "mit": duration_s, "hit": 0.0}


def compute_activity_zones(
    activity: Activity,
    stream: Stream | None,
    thresholds: ZoneThresholds,
) -> dict[str, float] | None:
    """Compute time in zones for an activity. Returns None if no threshold available."""
    duration_s = float(activity.moving_time or 0)
    if duration_s == 0:
        return None

    sport = activity.sport_type or ""
    use_power = sport in ("Ride", "VirtualRide") and thresholds.ftp
    use_hr = thresholds.lthr is not None

    # Try power for cycling
    if use_power:
        if stream and stream.watts:
            try:
                power_data = json.loads(stream.watts)
                if power_data:
                    return compute_time_in_zones_from_stream(
                        power_data, thresholds.ftp, POWER_LIT_UPPER, POWER_HIT_LOWER
                    )
            except (json.JSONDecodeError, TypeError):
                pass
        # Fall back to average power
        if activity.average_watts:
            return compute_time_in_zones_from_average(
                duration_s, activity.average_watts, thresholds.ftp,
                POWER_LIT_UPPER, POWER_HIT_LOWER
            )

    # Try HR for all sports
    if use_hr:
        if stream and stream.heartrate:
            try:
                hr_data = json.loads(stream.heartrate)
                if hr_data:
                    return compute_time_in_zones_from_stream(
                        hr_data, thresholds.lthr, HR_LIT_UPPER, HR_HIT_LOWER
                    )
            except (json.JSONDecodeError, TypeError):
                pass
        # Fall back to average HR
        if activity.average_heartrate:
            return compute_time_in_zones_from_average(
                duration_s, activity.average_heartrate, thresholds.lthr,
                HR_LIT_UPPER, HR_HIT_LOWER
            )

    return None