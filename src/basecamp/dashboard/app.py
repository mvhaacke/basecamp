"""Streamlit dashboard — main entry point."""

import streamlit as st

from basecamp.database import init_db

st.set_page_config(page_title="Basecamp", page_icon="🏔️", layout="wide")

init_db()

dashboard = st.Page("pages/dashboard.py", title="Dashboard", icon="📊", default=True)
training = st.Page("pages/training.py", title="Training", icon="📈")
activities = st.Page("pages/activities.py", title="Activities", icon="🏃")
settings = st.Page("pages/settings.py", title="Settings", icon="⚙️")

pg = st.navigation([dashboard, training, activities, settings])
pg.run()