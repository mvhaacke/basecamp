# Basecamp

Personal triathlon training analysis tool. Syncs activity data from Strava and wellness data from Garmin Connect into a local SQLite database for custom analysis.

## Setup

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create a `.env` file with your Strava API credentials (get them at https://www.strava.com/settings/api):

```
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
```

## Commands

### Strava

```bash
# Authenticate with Strava (opens browser for OAuth2 flow)
basecamp strava auth

# Sync activities from Strava
basecamp strava sync

# Also fetch time-series stream data (heart rate, power, GPS, etc.)
basecamp strava sync --streams

# Limit how many activities get streams fetched
basecamp strava sync --streams --stream-limit 10

# Re-extract fields from stored raw JSON (useful after adding new DB columns)
basecamp strava backfill
```

### Garmin

```bash
# Authenticate with Garmin Connect (prompts for email/password)
basecamp garmin auth

# Sync wellness data (sleep, HRV, body battery, stress, etc.)
basecamp garmin sync

# Sync a specific number of days
basecamp garmin sync --days 60

# Sync a specific date range
basecamp garmin sync --start 2025-01-01 --end 2025-01-31

# Re-extract fields from stored raw JSON
basecamp garmin backfill
```

### Views

```bash
# List recent activities
basecamp activities

# Show more activities
basecamp activities --limit 50

# Filter by sport type
basecamp activities --sport Run

# Show details for a specific activity
basecamp activity 1234567890

# Weekly training summary (hours per sport + kilojoules)
basecamp weekly

# Show more weeks
basecamp weekly --weeks 12

# Garmin wellness/recovery overview
basecamp wellness

# Show more days
basecamp wellness --days 14

# Show a specific date
basecamp wellness --date 2025-06-15
```

### Dashboard

```bash
# Launch the Streamlit training dashboard (PMC chart)
basecamp dashboard
```

The dashboard shows a Performance Management Chart (PMC) with Chronic Training Load (CTL), Acute Training Load (ATL), and Training Stress Balance (TSB). Configure your athlete thresholds (FTP, max HR, LTHR, etc.) in the sidebar to enable power- and HR-based TSS computation.

## Data Storage

All data is stored in `basecamp.db` (SQLite) at the project root. Each synced activity and wellness day retains the full raw API response, so fields can be re-extracted with the `backfill` commands after schema changes.