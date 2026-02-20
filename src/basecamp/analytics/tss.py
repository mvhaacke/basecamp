"""Training Stress Score computation for multi-sport activities."""

from dataclasses import dataclass
from math import exp


@dataclass
class AthleteThresholds:
    ftp: float | None = None
    run_threshold_pace: float | None = None  # seconds per km
    swim_css: float | None = None  # seconds per 100m
    max_hr: int | None = None
    resting_hr: int | None = None
    lthr: int | None = None


DURATION_TSS_PER_HOUR: dict[str, float] = {
    "Ride": 60,
    "VirtualRide": 60,
    "Run": 70,
    "TrailRun": 70,
    "Swim": 60,
    "WeightTraining": 50,
    "Rowing": 40,
    "Yoga": 20,
}
DEFAULT_TSS_PER_HOUR = 40.0


def power_tss(duration_s: float, normalized_power: float, ftp: float) -> float:
    intensity_factor = normalized_power / ftp
    return (duration_s * normalized_power * intensity_factor) / (ftp * 3600) * 100


def hr_tss(
    duration_s: float,
    avg_hr: float,
    max_hr: int,
    resting_hr: int,
    lthr: int,
) -> float:
    """Exponential heart rate-based TSS (TRIMP-style)."""
    hr_reserve = max_hr - resting_hr
    if hr_reserve <= 0:
        return 0.0

    hr_ratio = (avg_hr - resting_hr) / hr_reserve
    hr_ratio = max(0.0, min(1.0, hr_ratio))

    lthr_ratio = (lthr - resting_hr) / hr_reserve
    if lthr_ratio <= 0:
        return 0.0

    k = 1.92
    trimp = duration_s / 60.0 * hr_ratio * 0.64 * exp(k * hr_ratio)
    lthr_trimp = 60.0 * lthr_ratio * 0.64 * exp(k * lthr_ratio)

    if lthr_trimp <= 0:
        return 0.0

    return (trimp / lthr_trimp) * 100


def duration_tss(duration_s: float, tss_per_hour: float) -> float:
    return duration_s / 3600.0 * tss_per_hour


def pace_tss(duration_s: float, avg_speed_m_per_s: float, threshold_pace_s_per_km: float) -> float:
    """Running TSS: IF=1 at threshold pace gives 100 TSS/hr."""
    avg_pace_s_per_km = 1000 / avg_speed_m_per_s
    intensity_factor = threshold_pace_s_per_km / avg_pace_s_per_km  # slower pace → smaller IF
    return (duration_s / 3600) * intensity_factor**2 * 100


def css_tss(duration_s: float, distance_m: float, css_s_per_100m: float) -> float:
    """Swim TSS: IF=1 at CSS gives 100 TSS/hr."""
    avg_pace_s_per_100m = (duration_s / distance_m) * 100
    intensity_factor = css_s_per_100m / avg_pace_s_per_100m
    return (duration_s / 3600) * intensity_factor**2 * 100


TRI_SPORTS = {"Ride", "VirtualRide", "Run", "TrailRun", "Swim"}


def compute_activity_tss(
    sport_type: str,
    duration_s: float,
    weighted_average_watts: float | None,
    average_watts: float | None,
    average_heartrate: float | None,
    thresholds: AthleteThresholds,
    average_speed_m_per_s: float | None = None,
    distance_m: float | None = None,
) -> tuple[float | None, str]:
    """Returns (tss_value, method_used) for an activity.

    Priority for triathlon sports (Ride, Run, Swim):
    1. Power TSS — cycling with FTP and power data
    2. Pace TSS — running with threshold pace and speed
    3. CSS TSS  — swimming with CSS and distance
    4. Duration fallback

    Non-triathlon sports (WeightTraining, Rowing, Yoga, etc.):
    5. HR TSS   — TRIMP-style when HR thresholds are set
    6. Duration fallback
    """
    # Power-based TSS only for cycling (running power from Strava is unreliable)
    if sport_type in ("Ride", "VirtualRide") and thresholds.ftp:
        np = weighted_average_watts or average_watts
        if np and np > 0:
            return power_tss(duration_s, np, thresholds.ftp), "power"

    # Pace-based TSS for running
    if sport_type in ("Run", "TrailRun") and thresholds.run_threshold_pace and average_speed_m_per_s:
        if average_speed_m_per_s > 0:
            return pace_tss(duration_s, average_speed_m_per_s, thresholds.run_threshold_pace), "pace"

    # CSS-based TSS for swimming
    if sport_type == "Swim" and thresholds.swim_css and distance_m and distance_m > 0:
        return css_tss(duration_s, distance_m, thresholds.swim_css), "css"

    # For non-triathlon sports, try HR before falling back to duration
    if sport_type not in TRI_SPORTS and (
        average_heartrate
        and thresholds.max_hr
        and thresholds.resting_hr
        and thresholds.lthr
    ):
        value = hr_tss(
            duration_s,
            average_heartrate,
            thresholds.max_hr,
            thresholds.resting_hr,
            thresholds.lthr,
        )
        if value > 0:
            return value, "hr"

    # Duration-based fallback
    rate = DURATION_TSS_PER_HOUR.get(sport_type, DEFAULT_TSS_PER_HOUR)
    return duration_tss(duration_s, rate), "duration"
