# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow

Always invoke the `/workflow` skill at the start of every task.

## Learning-First Approach

The user is building this project to learn. Explain concepts, trade-offs, and the "why" behind decisions. Point out interesting code sections after implementing something new. When introducing a new pattern or library feature, briefly explain what it does and why we're using it.

## Project

Personal triathlon training analysis tool. Syncs activity data from Strava and wellness data from Garmin Connect into a local SQLite database for custom analysis. Python 3.13 (Homebrew), installed as an editable package.

## Setup & Commands

```bash
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .

basecamp strava auth          # OAuth2 flow with Strava
basecamp strava sync          # Sync activities (--streams to also fetch time-series data)
basecamp strava backfill      # Re-extract fields from stored raw_json
basecamp garmin auth          # Garmin Connect login
basecamp garmin sync          # Sync wellness data (--days N, --start/--end date range)
basecamp garmin backfill      # Re-extract Garmin fields
basecamp dashboard            # Launch FastAPI backend (port 8000)
cd web && npm run dev         # Launch React dev server (port 5173)
basecamp activities           # List activities (--limit N, --sport TYPE)
basecamp weekly               # Weekly training summary
basecamp wellness             # Garmin recovery overview
```

## Architecture

```
cli/                    Typer CLI — entry point for all commands
config.py               Loads .env (Strava credentials), defines DATABASE_URL
models.py               SQLAlchemy models: Token, Activity, Stream, AthleteSettings, GarminDailySummary
database.py             Session factory and init_db()
strava/auth.py          OAuth2 flow (local HTTP callback on :8000), token persistence & auto-refresh
strava/sync.py          Incremental activity fetch, upserts into DB, optional stream sync; compute_calories()
garmin/sync.py          Garmin Connect wellness sync
analytics/tss.py        TSS: power (cycling), pace (running), CSS (swim), HR (non-tri), duration fallback
analytics/pmc.py        PMC: CTL/ATL/TSB via pandas EWMA
analytics/wellness.py   HRV data loading with baseline zones
api/
    app.py          FastAPI app — CORS, 6 endpoints, startup hook
    services.py     Business logic (queries DB, builds response dicts)
    schemas.py      Pydantic response models (validates/documents API shapes)
    sync.py         Background SyncManager (thread-safe, rate-limited)
web/                React frontend (Vite + TypeScript)
    src/App.tsx     Main shell: sync state, tab navigation
    src/components/ StatusView, CalendarView, ActivityView, Card
    src/types.ts    Shared TypeScript types (mirrors API schemas)
    src/utils.ts    Pure helper functions (formatting, date math)
```

## Key Patterns

- stravalib returns pint Quantity objects — use `_safe_float()`/`_safe_int()` in sync.py to extract `.magnitude`
- `raw_json` stores the full API response per record as source of truth; `backfill` re-derives all other fields from it
- Incremental sync: only fetches activities newer than the most recent `start_date` in DB
- Schema changes require manual `ALTER TABLE` — `create_all()` only creates new tables, never adds columns to existing ones

## Analytics

**TSS priority** (sport-aware):
1. Power — Ride/VirtualRide + FTP + watts
2. Pace — Run/TrailRun + `run_threshold_pace` + speed
3. CSS — Swim + `swim_css` + distance
4. HR/TRIMP — non-tri sports with HR thresholds set
5. Duration fallback

**Calories priority:**
1. Keytel HR formula (requires `avg_hr`, `max_hr`, `resting_hr`, `weight_kg`, `age`, `sex`)
2. Power — Ride/VirtualRide (Strava kJ ≈ kcal)
3. Distance-based — Run/Swim/Hike (`KCAL_PER_KG_PER_KM`)
4. MET duration-based — WeightTraining/Rowing/Yoga/etc. (`MET_BY_SPORT`)
5. Strava kJ fallback

## Configuration

`.env` (gitignored): `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`. Database: `basecamp.db` at project root.

## Coding Style

- Type hints on all function signatures
- Good naming over inline comments; docstrings only for high-level context
