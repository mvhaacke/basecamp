from datetime import date, datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table

from basecamp.cli import app
from basecamp.cli.formatting import format_duration, sport_group
from basecamp.database import get_session
from basecamp.models import Activity, GarminDailySummary

console = Console()


@app.command()
def activities(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of activities to show"),
    sport: str = typer.Option(None, "--sport", "-s", help="Filter by sport type (e.g. Run, Ride, Swim)"),
) -> None:
    """List synced activities."""
    with get_session() as session:
        query = session.query(Activity).order_by(Activity.start_date.desc())
        if sport:
            query = query.filter(Activity.sport_type.ilike(f"%{sport}%"))
        rows = query.limit(limit).all()

        if not rows:
            console.print("No activities found. Run 'basecamp strava sync' first.")
            return

        table = Table(title=f"Activities (showing {len(rows)})")
        table.add_column("ID", style="dim")
        table.add_column("Date")
        table.add_column("Sport")
        table.add_column("Name")
        table.add_column("Distance", justify="right")
        table.add_column("Time", justify="right")
        table.add_column("Avg HR", justify="right")
        table.add_column("Streams", justify="center")

        for a in rows:
            dist = f"{a.distance / 1000:.1f} km" if a.distance else "-"
            duration = str(timedelta(seconds=a.moving_time)) if a.moving_time else "-"
            hr = f"{a.average_heartrate:.0f}" if a.average_heartrate else "-"
            dt = a.start_date.strftime("%Y-%m-%d") if a.start_date else "-"
            has_streams = "[green]✓[/green]" if a.has_streams else ""

            table.add_row(str(a.id), dt, a.sport_type or "-", a.name or "-", dist, duration, hr, has_streams)

        console.print(table)


@app.command()
def activity(
    activity_id: int = typer.Argument(help="Strava activity ID"),
) -> None:
    """Show details for a single activity."""
    with get_session() as session:
        act = session.get(Activity, activity_id)
        if not act:
            console.print(f"[red]Activity {activity_id} not found. Run 'basecamp strava sync' first.[/red]")
            raise typer.Exit(1)

        dist = f"{act.distance / 1000:.2f} km" if act.distance else "-"
        moving = str(timedelta(seconds=act.moving_time)) if act.moving_time else "-"
        elapsed = str(timedelta(seconds=act.elapsed_time)) if act.elapsed_time else "-"
        pace = ""
        if act.average_speed and act.average_speed > 0 and act.sport_type and "run" in act.sport_type.lower():
            pace_sec = 1000 / act.average_speed
            pace = f"{int(pace_sec // 60)}:{int(pace_sec % 60):02d} /km"

        table = Table(title=act.name or "Activity", show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("ID", str(act.id))
        table.add_row("Sport", act.sport_type or "-")
        table.add_row("Date", act.start_date.strftime("%Y-%m-%d %H:%M") if act.start_date else "-")
        table.add_row("Distance", dist)
        table.add_row("Moving Time", moving)
        table.add_row("Elapsed Time", elapsed)
        if pace:
            table.add_row("Avg Pace", pace)
        table.add_row("Elevation", f"{act.total_elevation_gain:.0f} m" if act.total_elevation_gain else "-")
        table.add_row("Avg Speed", f"{act.average_speed:.2f} m/s" if act.average_speed else "-")
        table.add_row("Avg HR", f"{act.average_heartrate:.0f} bpm" if act.average_heartrate else "-")
        table.add_row("Max HR", f"{act.max_heartrate:.0f} bpm" if act.max_heartrate else "-")
        if act.average_watts:
            table.add_row("Avg Power", f"{act.average_watts:.0f} W")
        if act.weighted_average_watts:
            table.add_row("Normalized Power", f"{act.weighted_average_watts:.0f} W")
        if act.average_cadence:
            table.add_row("Avg Cadence", f"{act.average_cadence:.0f}")
        if act.calories:
            table.add_row("Calories", f"{act.calories:.0f}")
        table.add_row("Streams", "[green]✓[/green]" if act.has_streams else "[dim]not synced[/dim]")

        console.print(table)


@app.command()
def weekly(
    weeks: int = typer.Option(8, "--weeks", "-w", help="Number of weeks to show"),
) -> None:
    """Show weekly training summary: hours per sport and kilojoules."""
    with get_session() as session:
        all_activities = (
            session.query(Activity)
            .filter(Activity.start_date.isnot(None))
            .order_by(Activity.start_date.desc())
            .all()
        )

        if not all_activities:
            console.print("No activities found. Run 'basecamp strava sync' first.")
            return

        weekly_data: dict[str, dict] = {}
        for a in all_activities:
            iso = a.start_date.isocalendar()
            week_key = f"{iso[0]}-W{iso[1]:02d}"
            week_start = date.fromisocalendar(iso[0], iso[1], 1)

            if week_key not in weekly_data:
                weekly_data[week_key] = {
                    "start": week_start,
                    "Ride": 0, "Run": 0, "Swim": 0, "Other": 0,
                    "total_seconds": 0,
                    "kj": 0.0,
                    "count": 0,
                }

            group = sport_group(a.sport_type or "")
            seconds = a.moving_time or 0
            weekly_data[week_key][group] += seconds
            weekly_data[week_key]["total_seconds"] += seconds
            weekly_data[week_key]["count"] += 1

            kj = a.estimated_kilojoules or a.kilojoules
            if kj:
                weekly_data[week_key]["kj"] += kj

        sorted_weeks = sorted(weekly_data.items(), reverse=True)[:weeks]

        table = Table(title=f"Weekly Summary (last {len(sorted_weeks)} weeks)")
        table.add_column("Week")
        table.add_column("Ride", justify="right")
        table.add_column("Run", justify="right")
        table.add_column("Swim", justify="right")
        table.add_column("Other", justify="right")
        table.add_column("Total", justify="right", style="bold")
        table.add_column("kJ", justify="right")
        table.add_column("#", justify="right", style="dim")

        for week_key, d in sorted_weeks:
            def fmt_hours(secs: int) -> str:
                if secs == 0:
                    return "[dim]-[/dim]"
                h, m = divmod(secs, 3600)
                return f"{h}:{m // 60:02d}"

            total_h, total_m = divmod(d["total_seconds"], 3600)
            kj_str = f"{d['kj']:,.0f}" if d["kj"] > 0 else "-"

            table.add_row(
                week_key,
                fmt_hours(d["Ride"]),
                fmt_hours(d["Run"]),
                fmt_hours(d["Swim"]),
                fmt_hours(d["Other"]),
                f"{total_h}:{total_m // 60:02d}",
                kj_str,
                str(d["count"]),
            )

        console.print(table)


@app.command()
def wellness(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to show"),
    date_str: str = typer.Option(None, "--date", help="Show a specific date (YYYY-MM-DD)"),
) -> None:
    """Show Garmin wellness/recovery data."""
    with get_session() as session:
        query = session.query(GarminDailySummary).order_by(GarminDailySummary.date.desc())

        if date_str:
            target = datetime.strptime(date_str, "%Y-%m-%d").date()
            row = session.get(GarminDailySummary, target)
            if not row:
                console.print(f"No wellness data for {date_str}. Run 'basecamp garmin sync' first.")
                return

            detail = Table(title=f"Wellness — {date_str}", show_header=False, box=None, padding=(0, 2))
            detail.add_column("Metric", style="bold")
            detail.add_column("Value")

            detail.add_row("Sleep Score", str(row.sleep_score) if row.sleep_score else "-")
            detail.add_row("Sleep Duration", format_duration(row.sleep_duration))
            detail.add_row("Deep Sleep", format_duration(row.sleep_deep))
            detail.add_row("Light Sleep", format_duration(row.sleep_light))
            detail.add_row("REM Sleep", format_duration(row.sleep_rem))
            detail.add_row("Awake", format_duration(row.sleep_awake))
            detail.add_row("HRV (last night)", f"{row.hrv_last_night:.0f} ms" if row.hrv_last_night else "-")
            detail.add_row("HRV (weekly avg)", f"{row.hrv_weekly_avg:.0f} ms" if row.hrv_weekly_avg else "-")
            detail.add_row("HRV Status", row.hrv_status or "-")
            detail.add_row("Body Battery High", str(row.body_battery_high) if row.body_battery_high is not None else "-")
            detail.add_row("Body Battery Low", str(row.body_battery_low) if row.body_battery_low is not None else "-")
            detail.add_row("Stress Avg", str(row.stress_avg) if row.stress_avg is not None else "-")
            detail.add_row("Resting HR", f"{row.resting_hr} bpm" if row.resting_hr else "-")
            detail.add_row("SpO2 Avg", f"{row.spo2_avg:.1f}%" if row.spo2_avg else "-")
            detail.add_row("Training Readiness", f"{row.training_readiness_score:.0f}" if row.training_readiness_score else "-")

            console.print(detail)
            return

        rows = query.limit(days).all()

        if not rows:
            console.print("No wellness data found. Run 'basecamp garmin sync' first.")
            return

        table = Table(title=f"Wellness ({len(rows)} days)")
        table.add_column("Date")
        table.add_column("Sleep", justify="right")
        table.add_column("Sleep Dur", justify="right")
        table.add_column("HRV", justify="right")
        table.add_column("BB High", justify="right")
        table.add_column("Stress", justify="right")
        table.add_column("RHR", justify="right")
        table.add_column("Readiness", justify="right")

        for r in rows:
            table.add_row(
                r.date.isoformat() if r.date else "-",
                str(r.sleep_score) if r.sleep_score else "-",
                format_duration(r.sleep_duration),
                f"{r.hrv_last_night:.0f}" if r.hrv_last_night else "-",
                str(r.body_battery_high) if r.body_battery_high is not None else "-",
                str(r.stress_avg) if r.stress_avg is not None else "-",
                str(r.resting_hr) if r.resting_hr else "-",
                f"{r.training_readiness_score:.0f}" if r.training_readiness_score else "-",
            )

        console.print(table)
