from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from basecamp.api.schemas import ActivityDetail, ActivityListItem, CalendarResponse, StatusSummary
from basecamp.api.services import (
    build_calendar_summary,
    build_status_summary,
    get_activity_detail,
    list_recent_activities,
)
from basecamp.api.sync import sync_manager
from basecamp.database import init_db

app = FastAPI(title="Basecamp API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    # Run sync automatically so non-technical users get fresh data on load.
    sync_manager.trigger(reason="startup", force=False)


@app.get("/api/status", response_model=StatusSummary)
def get_status() -> StatusSummary:
    return StatusSummary.model_validate(build_status_summary())


@app.get("/api/calendar", response_model=CalendarResponse)
def get_calendar(
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(..., description="End date (YYYY-MM-DD)"),
) -> CalendarResponse:
    return CalendarResponse.model_validate(build_calendar_summary(start, end))


@app.get("/api/activities", response_model=list[ActivityListItem])
def get_activities(limit: int = Query(50, ge=1, le=250)) -> list[ActivityListItem]:
    return [ActivityListItem.model_validate(item) for item in list_recent_activities(limit)]


@app.get("/api/activities/{activity_id}", response_model=ActivityDetail)
def get_activity(activity_id: int) -> ActivityDetail:
    detail = get_activity_detail(activity_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Activity not found")
    return ActivityDetail.model_validate(detail)


@app.get("/api/sync")
def get_sync_status() -> dict:
    return sync_manager.snapshot()


@app.post("/api/sync")
def start_sync(
    reason: str = Query("manual", description="Reason for sync trigger"),
    force: bool = Query(False, description="Force sync even if recently updated"),
) -> dict:
    started, message = sync_manager.trigger(reason=reason, force=force)
    return {"started": started, "message": message, "state": sync_manager.snapshot()}
