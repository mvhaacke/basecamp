"""Training Stress Score computation for multi-sport activities."""

from dataclasses import dataclass
from math import exp


@dataclass
class AthleteThresholds:
    ftp: float | None = None
    run_ftp: float | None = None
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


def compute_activity_tss(
    sport_type: str,
    duration_s: float,
    weighted_average_watts: float | None,
    average_watts: float | None,
    average_heartrate: float | None,
    thresholds: AthleteThresholds,
) -> tuple[float | None, str]:
    """Returns (tss_value, method_used) for an activity."""
    ftp = thresholds.run_ftp if sport_type in ("Run", "TrailRun") else thresholds.ftp
    np = weighted_average_watts or average_watts

    if ftp and np and np > 0:
        return power_tss(duration_s, np, ftp), "power"

    if (
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

    rate = DURATION_TSS_PER_HOUR.get(sport_type, DEFAULT_TSS_PER_HOUR)
    return duration_tss(duration_s, rate), "duration"
