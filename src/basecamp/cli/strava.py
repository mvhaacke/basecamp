import typer
from rich.console import Console

strava_app = typer.Typer(help="Strava integration")
console = Console()


@strava_app.command("auth")
def auth() -> None:
    """Authenticate with Strava via OAuth2."""
    from basecamp.strava.auth import authenticate

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


@strava_app.command("sync")
def sync(
    streams: bool = typer.Option(False, "--streams", help="Also fetch time-series stream data"),
    stream_limit: int = typer.Option(None, "--stream-limit", help="Max number of activities to fetch streams for"),
) -> None:
    """Sync activities from Strava to local database."""
    from basecamp.strava.sync import sync_activities

    try:
        sync_activities(include_streams=streams, stream_limit=stream_limit)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@strava_app.command("backfill")
def backfill() -> None:
    """Re-extract all fields from stored raw_json (useful after adding new columns)."""
    from basecamp.strava.sync import backfill_from_raw_json

    try:
        backfill_from_raw_json()
    except Exception as e:
        console.print(f"[red]Backfill failed: {e}[/red]")
        raise typer.Exit(1)
