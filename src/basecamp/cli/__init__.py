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
def dashboard() -> None:
    """Launch the Streamlit training dashboard."""
    import subprocess
    import sys
    from pathlib import Path

    app_path = Path(__file__).parent.parent / "dashboard" / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])
