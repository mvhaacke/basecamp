from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock, Thread
from typing import Any


@dataclass
class SyncState:
    running: bool = False
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    status_message: str = "Idle"
    last_trigger: str | None = None
    runs: int = 0


class SyncManager:
    def __init__(self, min_interval_minutes: int = 15) -> None:
        self._state = SyncState()
        self._lock = Lock()
        self._min_interval = timedelta(minutes=min_interval_minutes)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._state.running,
                "last_started_at": _iso(self._state.last_started_at),
                "last_finished_at": _iso(self._state.last_finished_at),
                "last_success_at": _iso(self._state.last_success_at),
                "last_error": self._state.last_error,
                "status_message": self._state.status_message,
                "last_trigger": self._state.last_trigger,
                "runs": self._state.runs,
            }

    def trigger(self, reason: str = "manual", force: bool = False) -> tuple[bool, str]:
        now = datetime.now(timezone.utc)
        with self._lock:
            if self._state.running:
                return False, "Sync already running"

            if (
                not force
                and self._state.last_started_at is not None
                and now - self._state.last_started_at < self._min_interval
            ):
                return False, "Sync skipped: recently updated"

            self._state.running = True
            self._state.last_started_at = now
            self._state.last_trigger = reason
            self._state.last_error = None
            self._state.status_message = "Sync in progress"

        Thread(target=self._run, args=(reason,), daemon=True).start()
        return True, "Sync started"

    def _run(self, reason: str) -> None:
        errors: list[str] = []

        try:
            from basecamp.garmin.sync import sync_wellness
            from basecamp.strava.sync import sync_activities

            try:
                sync_activities(include_streams=False)
            except Exception as exc:
                errors.append(f"Strava sync: {exc}")

            try:
                sync_wellness(days=30)
            except Exception as exc:
                errors.append(f"Garmin sync: {exc}")
        except Exception as exc:
            errors.append(f"Sync bootstrap failed: {exc}")

        finished = datetime.now(timezone.utc)
        with self._lock:
            self._state.running = False
            self._state.last_finished_at = finished
            self._state.runs += 1

            if errors:
                self._state.last_error = " | ".join(errors)
                self._state.status_message = f"Completed with warnings ({reason})"
            else:
                self._state.last_error = None
                self._state.last_success_at = finished
                self._state.status_message = f"Synced ({reason})"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


sync_manager = SyncManager()

