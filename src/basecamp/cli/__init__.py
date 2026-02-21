import typer

from basecamp.database import init_db

app = typer.Typer(help="Basecamp — personal triathlon training analysis")


@app.callback()
def startup() -> None:
    init_db()


from basecamp.cli.garmin import garmin_app
from basecamp.cli.strava import strava_app

app.add_typer(strava_app, name="strava")
app.add_typer(garmin_app, name="garmin")

from basecamp.cli import views  # noqa: F401


@app.command()
def dashboard(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Launch the FastAPI backend for the React dashboard."""
    import uvicorn

    uvicorn.run("basecamp.api.app:app", host=host, port=port, reload=False)
