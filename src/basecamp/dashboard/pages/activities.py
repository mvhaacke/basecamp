"""Activities page — browse and filter activities."""

import streamlit as st
from sqlalchemy import func, select

from basecamp.database import get_session
from basecamp.models import Activity

# --- Filters ---

with get_session() as session:
    sport_types = session.execute(
        select(Activity.sport_type).distinct().where(Activity.sport_type.isnot(None)).order_by(Activity.sport_type)
    ).scalars().all()

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    selected_sport = st.selectbox("Sport", ["All"] + list(sport_types))

with col2:
    limit = st.selectbox("Show", [25, 50, 100, 250], index=0)

with col3:
    with get_session() as session:
        total_count = session.execute(select(func.count(Activity.id))).scalar()
    st.metric("Total Activities", total_count)

# --- Load activities ---

with get_session() as session:
    query = select(Activity).order_by(Activity.start_date.desc()).limit(limit)
    if selected_sport != "All":
        query = query.where(Activity.sport_type == selected_sport)
    activities = session.execute(query).scalars().all()

if not activities:
    st.info("No activities found. Go to Settings to sync from Strava.")
else:
    rows = []
    for act in activities:
        date_str = act.start_date_local.strftime("%Y-%m-%d") if act.start_date_local else ""
        duration_min = (act.moving_time or 0) // 60
        duration_str = f"{duration_min // 60}:{duration_min % 60:02d}"
        distance_km = (act.distance or 0) / 1000
        rows.append({
            "Date": date_str,
            "Sport": act.sport_type or "",
            "Name": act.name or "",
            "Duration": duration_str,
            "Distance (km)": f"{distance_km:.1f}" if distance_km else "",
            "Avg HR": int(act.average_heartrate) if act.average_heartrate else None,
            "kcal": int(act.computed_calories) if act.computed_calories else None,
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)