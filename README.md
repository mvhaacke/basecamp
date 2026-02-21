# Basecamp

Personal triathlon training analysis tool. Syncs activities from Strava and wellness data from Garmin Connect into a local SQLite database for custom analysis and a React + FastAPI dashboard.

## Setup

```bash
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create `.env` with your Strava API credentials (from https://www.strava.com/settings/api):

```
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
```

## Commands

```bash
# Strava
basecamp strava auth                             # OAuth2 login
basecamp strava sync                             # Sync activities
basecamp strava sync --streams                   # Also fetch HR/power/GPS streams
basecamp strava backfill                         # Re-extract fields from stored raw JSON

# Garmin
basecamp garmin auth                             # Login with email/password
basecamp garmin sync                             # Sync wellness data
basecamp garmin sync --days 60                   # Sync last N days
basecamp garmin sync --start 2025-01-01          # Sync from a specific date
basecamp garmin backfill

# Views
basecamp activities                              # Recent activities (--limit N, --sport TYPE)
basecamp weekly                                  # Weekly training summary
basecamp wellness                                # Garmin recovery overview (--days N, --date YYYY-MM-DD)
basecamp dashboard                               # Launch FastAPI backend for dashboard
```

## Dashboard (React + FastAPI)

Run the API:

```bash
basecamp dashboard
```

Run the React app in a second terminal:

```bash
cd web
npm install
npm run dev
```

The MVP dashboard includes:
- Status page (readiness, weekly load, and quick nudge)
- Calendar page (month totals + daily load trend)
- Activity deep dive (Strava activity streams + Garmin wellness context)

All data is stored in `basecamp.db` (SQLite) at the project root.
