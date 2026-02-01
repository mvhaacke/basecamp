import json
import time
from datetime import date, datetime, timedelta, timezone

from rich.console import Console

from ..db import GarminDailySummary, get_session, init_db
from ..garmin.auth import get_client

console = Console()


def _fetch_sleep(client, display_name: str, date_str: str) -> dict | None:
    try:
        return client.connectapi(
            f"/wellness-service/wellness/dailySleepData/{display_name}",
            params={"date": date_str},
        )
    except Exception as e:
        console.print(f"    [dim]sleep: {e}[/dim]")
        return None


def _fetch_hrv(client, date_str: str) -> dict | None:
    try:
        return client.connectapi(f"/hrv-service/hrv/{date_str}")
    except Exception as e:
        console.print(f"    [dim]hrv: {e}[/dim]")
        return None


def _fetch_body_battery(client, date_str: str) -> dict | list | None:
    try:
        return client.connectapi(
            "/wellness-service/wellness/bodyBattery/reports/daily",
            params={"startDate": date_str, "endDate": date_str},
        )
    except Exception as e:
        console.print(f"    [dim]body battery: {e}[/dim]")
        return None


def _fetch_stress(client, date_str: str) -> dict | None:
    try:
        return client.connectapi(f"/wellness-service/wellness/dailyStress/{date_str}")
    except Exception as e:
        console.print(f"    [dim]stress: {e}[/dim]")
        return None


def _fetch_training_readiness(client, date_str: str) -> dict | list | None:
    try:
        return client.connectapi(f"/metrics-service/metrics/trainingreadiness/{date_str}")
    except Exception as e:
        console.print(f"    [dim]training readiness: {e}[/dim]")
        return None


def _fetch_spo2(client, date_str: str) -> dict | None:
    try:
        return client.connectapi(f"/wellness-service/wellness/daily/spo2/{date_str}")
    except Exception as e:
        console.print(f"    [dim]spo2: {e}[/dim]")
        return None


def _fetch_user_summary(client, display_name: str, date_str: str) -> dict | None:
    try:
        return client.connectapi(
            f"/usersummary-service/usersummary/daily/{display_name}",
            params={"calendarDate": date_str},
        )
    except Exception as e:
        console.print(f"    [dim]user summary: {e}[/dim]")
        return None


def _extract_sleep(data: dict | None) -> dict:
    if not data:
        return {}
    daily = data.get("dailySleepDTO", data)
    return {
        "sleep_score": daily.get("sleepScores", {}).get("overall", {}).get("value")
            if isinstance(daily.get("sleepScores"), dict) else None,
        "sleep_duration": daily.get("sleepTimeSeconds"),
        "sleep_deep": daily.get("deepSleepSeconds"),
        "sleep_light": daily.get("lightSleepSeconds"),
        "sleep_rem": daily.get("remSleepSeconds"),
        "sleep_awake": daily.get("awakeSleepSeconds"),
    }


def _extract_hrv(data: dict | None) -> dict:
    if not data:
        return {}
    summary = data.get("hrvSummary", data)
    return {
        "hrv_weekly_avg": summary.get("weeklyAvg"),
        "hrv_last_night": summary.get("lastNightAvg"),
        "hrv_status": summary.get("status"),
    }


def _extract_body_battery(data: dict | list | None) -> dict:
    if not data:
        return {}
    entry = data[0] if isinstance(data, list) and data else data
    if not isinstance(entry, dict):
        return {}
    values = entry.get("bodyBatteryValuesArray", [])
    bb_levels = [v[1] for v in values if isinstance(v, list) and len(v) > 1 and v[1] is not None]
    return {
        "body_battery_high": max(bb_levels) if bb_levels else None,
        "body_battery_low": min(bb_levels) if bb_levels else None,
        "body_battery_charged": entry.get("charged"),
        "body_battery_drained": entry.get("drained"),
    }


def _extract_stress(data: dict | None) -> dict:
    if not data:
        return {}
    return {
        "stress_avg": data.get("avgStressLevel"),
        "stress_max": data.get("maxStressLevel"),
        "stress_rest": None,
    }


def _extract_spo2(data: dict | None) -> dict:
    if not data:
        return {}
    return {
        "spo2_avg": data.get("averageSpO2"),
        "spo2_low": data.get("lowestSpO2"),
    }


def _extract_training_readiness(data: dict | list | None) -> dict:
    if not data:
        return {}
    entry = data[0] if isinstance(data, list) and data else data
    if not isinstance(entry, dict):
        return {}
    return {
        "training_readiness_score": entry.get("score"),
    }


def _extract_user_summary(data: dict | None) -> dict:
    if not data:
        return {}
    return {
        "resting_hr": data.get("restingHeartRate"),
    }


def _get_display_name(client) -> str:
    """Fetch the Garmin display name needed for some API endpoints."""
    profile = client.connectapi("/userprofile-service/socialProfile")
    return profile.get("displayName", "")


def sync_wellness(days: int = 30, start: date | None = None, end: date | None = None) -> None:
    """Fetch daily wellness data from Garmin and upsert to DB."""
    init_db()
    client = get_client()
    display_name = _get_display_name(client)
    session = get_session()

    try:
        today = date.today()
        yesterday = today - timedelta(days=1)

        if start:
            start_date = start
            end_date = end or yesterday
        else:
            latest = (
                session.query(GarminDailySummary)
                .order_by(GarminDailySummary.date.desc())
                .first()
            )
            earliest = today - timedelta(days=days)

            if latest and latest.date:
                incremental_start = latest.date + timedelta(days=1)
                start_date = max(earliest, incremental_start)
            else:
                start_date = earliest
            end_date = yesterday

        if start_date > end_date:
            console.print("Already up to date.")
            return

        total_days = (end_date - start_date).days + 1
        console.print(f"Syncing {total_days} days of wellness data ({start_date} to {end_date})...")

        current = start_date
        count = 0
        while current <= end_date:
            date_str = current.isoformat()
            console.print(f"  [{count + 1}/{total_days}] {date_str}...")

            sleep_data = _fetch_sleep(client, display_name, date_str)
            hrv_data = _fetch_hrv(client, date_str)
            bb_data = _fetch_body_battery(client, date_str)
            stress_data = _fetch_stress(client, date_str)
            tr_data = _fetch_training_readiness(client, date_str)
            spo2_data = _fetch_spo2(client, date_str)
            summary_data = _fetch_user_summary(client, display_name, date_str)

            fields: dict = {"synced_at": datetime.now(timezone.utc)}
            fields.update(_extract_sleep(sleep_data))
            fields.update(_extract_hrv(hrv_data))
            fields.update(_extract_body_battery(bb_data))
            fields.update(_extract_stress(stress_data))
            fields.update(_extract_spo2(spo2_data))
            fields.update(_extract_training_readiness(tr_data))
            fields.update(_extract_user_summary(summary_data))

            fields["raw_sleep"] = json.dumps(sleep_data, default=str) if sleep_data else None
            fields["raw_hrv"] = json.dumps(hrv_data, default=str) if hrv_data else None
            fields["raw_body_battery"] = json.dumps(bb_data, default=str) if bb_data else None
            fields["raw_stress"] = json.dumps(stress_data, default=str) if stress_data else None
            fields["raw_training_readiness"] = json.dumps(tr_data, default=str) if tr_data else None
            fields["raw_spo2"] = json.dumps(spo2_data, default=str) if spo2_data else None
            fields["raw_summary"] = json.dumps(summary_data, default=str) if summary_data else None

            existing = session.get(GarminDailySummary, current)
            if existing:
                for key, value in fields.items():
                    setattr(existing, key, value)
            else:
                session.add(GarminDailySummary(date=current, **fields))

            count += 1
            current += timedelta(days=1)

            if count % 10 == 0:
                session.commit()

            time.sleep(1)

        session.commit()
        console.print(f"Synced {count} days of wellness data.")
    finally:
        session.close()


def backfill_wellness() -> None:
    """Re-extract all fields from stored raw JSON for every GarminDailySummary row."""
    init_db()
    session = get_session()
    try:
        rows = session.query(GarminDailySummary).all()
        count = 0
        for row in rows:
            fields: dict = {}
            if row.raw_sleep:
                fields.update(_extract_sleep(json.loads(row.raw_sleep)))
            if row.raw_hrv:
                fields.update(_extract_hrv(json.loads(row.raw_hrv)))
            if row.raw_body_battery:
                fields.update(_extract_body_battery(json.loads(row.raw_body_battery)))
            if row.raw_stress:
                fields.update(_extract_stress(json.loads(row.raw_stress)))
            if row.raw_spo2:
                fields.update(_extract_spo2(json.loads(row.raw_spo2)))
            if row.raw_training_readiness:
                fields.update(_extract_training_readiness(json.loads(row.raw_training_readiness)))
            if row.raw_summary:
                fields.update(_extract_user_summary(json.loads(row.raw_summary)))
            for key, value in fields.items():
                setattr(row, key, value)
            count += 1
        session.commit()
        console.print(f"Backfilled {count} wellness rows from raw JSON.")
    finally:
        session.close()
