from datetime import timedelta

import typer
from rich.console import Console
from rich.table import Table

from basecamp.db import Activity, get_session, init_db
from basecamp.strava.auth import authenticate
from basecamp.strava.sync import sync_activities

app = typer.Typer(help="Basecamp — personal triathlon training analysis")
console = Console()


@app.command()
def auth():
    """Authenticate with Strava via OAuth2."""
    try:
        token_response = authenticate()
        console.print("[green]Successfully authenticated with Strava![/green]")
        athlete = token_response.get("athlete")
        if athlete and isinstance(athlete, dict):
            name = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
            if name:
                console.print(f"Athlete: {name}")
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def sync(
    streams: bool = typer.Option(False, "--streams", help="Also fetch time-series stream data"),
):
    """Sync activities from Strava to local database."""
    try:
        sync_activities(include_streams=streams)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@app.command()
def activities(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of activities to show"),
    sport: str = typer.Option(None, "--sport", "-s", help="Filter by sport type (e.g. Run, Ride, Swim)"),
):
    """List synced activities."""
    init_db()
    session = get_session()
    try:
        query = session.query(Activity).order_by(Activity.start_date.desc())
        if sport:
            query = query.filter(Activity.sport_type.ilike(f"%{sport}%"))
        rows = query.limit(limit).all()

        if not rows:
            console.print("No activities found. Run 'basecamp sync' first.")
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
            date = a.start_date.strftime("%Y-%m-%d") if a.start_date else "-"
            has_streams = "[green]✓[/green]" if a.has_streams else ""

            table.add_row(str(a.id), date, a.sport_type or "-", a.name or "-", dist, duration, hr, has_streams)

        console.print(table)
    finally:
        session.close()


@app.command()
def activity(
    activity_id: int = typer.Argument(help="Strava activity ID"),
):
    """Show details for a single activity."""
    init_db()
    session = get_session()
    try:
        act = session.get(Activity, activity_id)
        if not act:
            console.print(f"[red]Activity {activity_id} not found. Run 'basecamp sync' first.[/red]")
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
    finally:
        session.close()
