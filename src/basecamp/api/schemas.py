from datetime import date

from pydantic import BaseModel


class StatusSummary(BaseModel):
    readiness_score: float | None
    sleep_score: int | None
    hrv_last_night: float | None
    body_battery_high: int | None
    weekly_hours: float
    weekly_sessions: int
    weekly_tss: float
    ctl: float | None
    atl: float | None
    tsb: float | None
    nudge: str


class CalendarDay(BaseModel):
    date: date
    sessions: int
    duration_hours: float
    tss: float


class CalendarTotals(BaseModel):
    sessions: int
    duration_hours: float
    tss: float


class ActivityListItem(BaseModel):
    id: int
    start_date: str
    sport_type: str | None
    name: str | None


class ActivityDetail(BaseModel):
    id: int
    sport_type: str | None
    name: str | None
    start_date: str
    duration_s: int
    distance_m: float | None
    average_heartrate: float | None
    average_watts: float | None
    calories: float | None
    stream_time: list[float]
    stream_heartrate: list[float]
    stream_watts: list[float]
    wellness: dict[str, float | int | str | None]
