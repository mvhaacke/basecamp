from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from basecamp.config import DATABASE_URL


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
    gear_id = Column(String)
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


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()
