"""Streamlit dashboard — main entry point."""

import streamlit as st

from basecamp.database import init_db

st.set_page_config(page_title="Basecamp", page_icon="🏔️", layout="wide")

init_db()

# --- Global design system ---
# Colours are also defined here as a reference for all pages.
#
# Brand / UI chrome: #14B8A6  (teal)
# Sport:  Swim=#38BDF8  Bike=#FB923C  Run=#A78BFA  Other=#52525B
# Zones:  LIT=#4ADE80   MIT=#FACC15   HIT=#F87171
# PMC:    CTL=#14B8A6   ATL=#FB923C   TSB=#A78BFA
# HRV:    Balanced=#4ADE80  Unbalanced=#FACC15  Low=#F87171

st.markdown("""
<style>
/* ── Page background ─────────────────────────────────── */
body, .stApp {
    background-color: #0F1117 !important;
    color: #F0F2F6 !important;
}

/* ── Hide Streamlit chrome ───────────────────────────── */
[data-testid="stDeployButton"]       { display: none !important; }
[data-testid="stDecoration"]         { display: none !important; }
[data-testid="stMainMenuButton"]     { display: none !important; }
[data-testid="stToolbar"]            { display: none !important; }
[data-testid="stHeader"]             { background: transparent !important; border-bottom: none !important; }
.stAppHeader                         { background: transparent !important; display: none !important; }
/* Hide heading anchor links */
h1 a, h2 a, h3 a { display: none !important; }

/* ── Sidebar ─────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #1A1D27 !important;
    border-right: 1px solid #2D3748 !important;
}
[data-testid="stSidebarContent"] {
    padding-top: 1.5rem;
}

/* App name in sidebar */
.sidebar-title {
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #F0F2F6;
    padding: 0 1rem 1.5rem 1rem;
    text-transform: uppercase;
}

/* ── Nav links ───────────────────────────────────────── */
[data-testid="stSidebarNavLink"] {
    border-radius: 6px !important;
    padding: 9px 14px !important;
    margin: 1px 8px !important;
    color: #6B7280 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    text-decoration: none !important;
    transition: background 0.15s, color 0.15s;
}
[data-testid="stSidebarNavLink"]:hover {
    background-color: #2D3748 !important;
    color: #F0F2F6 !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background-color: rgba(20, 184, 166, 0.12) !important;
    color: #14B8A6 !important;
    border-left: 2px solid #14B8A6 !important;
}
/* Hide the emoji icon span, show only text */
[data-testid="stSidebarNavLink"] [data-testid="stSidebarNavLinkIconContainer"] {
    display: none !important;
}

/* ── Metric cards ────────────────────────────────────── */
[data-testid="stMetric"] {
    background-color: #1A1D27;
    border: 1px solid #2D3748;
    border-radius: 8px;
    padding: 18px 20px !important;
}
[data-testid="stMetricLabel"] p {
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    color: #6B7280 !important;
}
[data-testid="stMetricValue"] {
    font-size: 28px !important;
    color: #F0F2F6 !important;
}

/* ── Main content padding ────────────────────────────── */
[data-testid="stMainBlockContainer"] {
    padding-top: 2rem !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
}

/* ── Selectbox / dropdowns ───────────────────────────── */
[data-testid="stSelectbox"] label p {
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    color: #6B7280 !important;
}
[data-testid="stSelectbox"] > div > div {
    background-color: #1A1D27 !important;
    border-color: #2D3748 !important;
    color: #F0F2F6 !important;
}
[data-testid="stSelectbox"] > div > div > div {
    color: #F0F2F6 !important;
}

/* ── Number inputs ───────────────────────────────────── */
[data-testid="stNumberInput"] > div {
    background-color: #1A1D27 !important;
    border-color: #2D3748 !important;
}
[data-testid="stNumberInput"] input {
    color: #F0F2F6 !important;
    background-color: #1A1D27 !important;
}
[data-testid="stNumberInput"] label p {
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    color: #6B7280 !important;
}

/* ── Form container ──────────────────────────────────── */
[data-testid="stForm"] {
    background-color: transparent !important;
    border-color: #2D3748 !important;
}

/* ── Section divider helper ──────────────────────────── */
.section-header {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #6B7280;
    margin: 2rem 0 0.75rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #2D3748;
}
</style>
""", unsafe_allow_html=True)

overview   = st.Page("pages/dashboard.py",  title="Overview",    icon=":material/speed:")
training   = st.Page("pages/training.py",   title="Training",    icon=":material/bar_chart:")
calendar   = st.Page("pages/calendar.py",   title="Calendar",    icon=":material/calendar_month:")
activities = st.Page("pages/activities.py", title="Activities",  icon=":material/table_rows:")
settings   = st.Page("pages/settings.py",   title="Settings",    icon=":material/settings:")

pg = st.navigation([overview, training, calendar, activities, settings])
pg.run()
