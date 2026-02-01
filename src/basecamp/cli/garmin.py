from datetime import datetime

import typer
from rich.console import Console

garmin_app = typer.Typer(help="Garmin Connect integration")
console = Console()


@garmin_app.command("auth")
def auth() -> None:
    """Authenticate with Garmin Connect."""
    from basecamp.garmin.auth import login

    try:
        login()
        console.print("[green]Successfully authenticated with Garmin Connect![/green]")
    except Exception as e:
        console.print(f"[red]Garmin authentication failed: {e}[/red]")
        raise typer.Exit(1)


@garmin_app.command("sync")
def sync(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to sync"),
    start: str = typer.Option(None, "--start", help="Start date (YYYY-MM-DD), overrides --days"),
    end: str = typer.Option(None, "--end", help="End date (YYYY-MM-DD), defaults to yesterday"),
) -> None:
    """Sync wellness data from Garmin Connect."""
    from basecamp.garmin.sync import sync_wellness

    start_date = datetime.strptime(start, "%Y-%m-%d").date() if start else None
    end_date = datetime.strptime(end, "%Y-%m-%d").date() if end else None

    try:
        sync_wellness(days=days, start=start_date, end=end_date)
    except Exception as e:
        console.print(f"[red]Garmin sync failed: {e}[/red]")
        raise typer.Exit(1)


@garmin_app.command("backfill")
def backfill() -> None:
    """Re-extract all fields from stored raw JSON (useful after fixing extraction logic)."""
    from basecamp.garmin.sync import backfill_wellness

    try:
        backfill_wellness()
    except Exception as e:
        console.print(f"[red]Garmin backfill failed: {e}[/red]")
        raise typer.Exit(1)
