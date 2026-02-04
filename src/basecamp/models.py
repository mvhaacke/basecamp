from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expires_at = Column(Integer, nullable=False)
    athlete_id = Column(Integer)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)  # Strava activity ID
    sport_type = Column(String)
    name = Column(String)
    description = Column(Text)
    start_date = Column(DateTime)
    timezone = Column(String)
    distance = Column(Float)
    moving_time = Column(Integer)
    elapsed_time = Column(Integer)
    total_elevation_gain = Column(Float)
    average_speed = Column(Float)
    max_speed = Column(Float)
    average_heartrate = Column(Float)
    max_heartrate = Column(Float)
    average_watts = Column(Float)
    max_watts = Column(Float)
    weighted_average_watts = Column(Float)
    average_cadence = Column(Float)
    calories = Column(Float)
    kilojoules = Column(Float)
    gear_id = Column(String)
    elev_high = Column(Float)
    elev_low = Column(Float)
    start_date_local = Column(DateTime)
    device_watts = Column(Boolean)
    trainer = Column(Boolean)
    workout_type = Column(Integer)
    has_heartrate = Column(Boolean)
    estimated_kilojoules = Column(Float)
    computed_calories = Column(Float)
    has_streams = Column(Boolean, default=False)
    raw_json = Column(Text)
    synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    streams = relationship("Stream", back_populates="activity", uselist=False)


class Stream(Base):
    __tablename__ = "streams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), unique=True, nullable=False)
    time = Column(Text)  # JSON array
    heartrate = Column(Text)
    watts = Column(Text)
    cadence = Column(Text)
    velocity_smooth = Column(Text)
    altitude = Column(Text)
    distance = Column(Text)
    latlng = Column(Text)
    grade_smooth = Column(Text)
    synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    activity = relationship("Activity", back_populates="streams")


class GarminDailySummary(Base):
    __tablename__ = "garmin_daily_summaries"

    date = Column(Date, primary_key=True)

    # Sleep
    sleep_score = Column(Integer)
    sleep_duration = Column(Integer)
    sleep_deep = Column(Integer)
    sleep_light = Column(Integer)
    sleep_rem = Column(Integer)
    sleep_awake = Column(Integer)

    # HRV
    hrv_weekly_avg = Column(Float)
    hrv_last_night = Column(Float)
    hrv_status = Column(String)

    # Body Battery
    body_battery_high = Column(Integer)
    body_battery_low = Column(Integer)
    body_battery_charged = Column(Integer)
    body_battery_drained = Column(Integer)

    # Stress
    stress_avg = Column(Integer)
    stress_max = Column(Integer)
    stress_rest = Column(Integer)

    # Heart Rate
    resting_hr = Column(Integer)

    # SpO2
    spo2_avg = Column(Float)
    spo2_low = Column(Float)

    # Training
    training_readiness_score = Column(Float)

    # Raw API responses
    raw_sleep = Column(Text)
    raw_hrv = Column(Text)
    raw_body_battery = Column(Text)
    raw_stress = Column(Text)
    raw_summary = Column(Text)
    raw_training_readiness = Column(Text)
    raw_spo2 = Column(Text)

    synced_at = Column(DateTime)


class AthleteSettings(Base):
    __tablename__ = "athlete_settings"

    id = Column(Integer, primary_key=True, default=1)
    ftp = Column(Float)
    run_threshold_pace = Column(Float)  # seconds per km
    swim_css = Column(Float)  # seconds per 100m
    max_hr = Column(Integer)
    resting_hr = Column(Integer)
    lthr = Column(Integer)
    weight_kg = Column(Float)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
