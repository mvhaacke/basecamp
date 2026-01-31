# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Basecamp is a personal triathlon training analysis tool that syncs activity data from Strava into a local SQLite database for custom analysis. Python 3.11+, installed as an editable package.

## Setup & Commands

```bash
# Create venv and install (uses Python 3.13 via Homebrew)
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .

# CLI commands (after install)
basecamp auth              # OAuth2 flow with Strava
basecamp sync              # Sync activities from Strava
basecamp sync --streams    # Also fetch time-series stream data
basecamp activities        # List activities (--limit N, --sport TYPE)
basecamp activity <id>     # Show single activity detail
```

No tests or linting configured yet.

## Architecture

```
cli.py                  Typer CLI — entry point for all commands
config.py               Loads .env (Strava credentials), defines DATABASE_URL
db.py                   SQLAlchemy models: Token, Activity, Stream + session factory
strava/auth.py          OAuth2 flow (local HTTP callback on :8000), token persistence & auto-refresh
strava/sync.py          Incremental activity fetch, upserts into DB, optional stream sync
```

**Data flow:** CLI → auth/sync modules → Strava API (via stravalib) → SQLAlchemy → SQLite (basecamp.db at project root)

**Key patterns:**
- stravalib returns pint Quantity objects (not plain numbers) — use `_safe_float()`/`_safe_int()` in sync.py to extract values via `.magnitude`
- `get_activities()` returns `SummaryActivity` (fewer fields than `DetailedActivity`) — all field access uses `getattr()` with defaults
- `raw_json` column stores the full Strava response per activity as the source of truth
- Incremental sync: only fetches activities newer than the most recent `start_date` in the DB

## Configuration

Strava API credentials stored in `.env` (gitignored). Required variables: `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`. Database is SQLite at `basecamp.db` in the project root.

## Coding Style
- Use type hints on all function signatures
- Use good naming and abstractions to avoid inline comments
- Use docstrings only for high-level context, not for parameter description etc.