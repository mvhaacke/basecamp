"""Overview page — daily check-in: PMC and HRV."""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dateutil.relativedelta import relativedelta

from basecamp.analytics.pmc import compute_pmc
from basecamp.analytics.wellness import load_hrv_data

# Shared dark-theme plotly layout defaults
_PLOTLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#6B7280", size=12),
    hovermode="x unified",
    hoverlabel=dict(bgcolor="#1A1D27", bordercolor="#2D3748", font_color="#F0F2F6"),
)
_AXIS = dict(gridcolor="#2D3748", linecolor="#2D3748", tickcolor="#2D3748")

time_range = st.selectbox(
    "Time range",
    ["3 months", "6 months", "12 months", "24 months", "All time"],
    index=2,
)
range_months = {"3 months": 3, "6 months": 6, "12 months": 12, "24 months": 24}
cutoff = None
if time_range in range_months:
    cutoff = date.today() - relativedelta(months=range_months[time_range])

# ── PMC ──────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">Performance Management</div>', unsafe_allow_html=True)

df = compute_pmc()

if df.empty:
    st.info("No activities found. Go to Settings to sync from Strava.")
else:
    if cutoff:
        df = df[df["date"] >= cutoff]

    if df.empty:
        st.info("No activities in the selected time range.")
    else:
        latest = df.iloc[-1]
        prev   = df.iloc[-8] if len(df) >= 8 else df.iloc[0]

        cols = st.columns(3)
        cols[0].metric("CTL — Fitness",  f"{latest['ctl']:.0f}", f"{latest['ctl']-prev['ctl']:+.1f}")
        cols[1].metric("ATL — Fatigue",  f"{latest['atl']:.0f}", f"{latest['atl']-prev['atl']:+.1f}")
        cols[2].metric("TSB — Form",     f"{latest['tsb']:.0f}", f"{latest['tsb']-prev['tsb']:+.1f}")

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=df["date"], y=df["tss"],
            name="Daily TSS",
            marker_color="rgba(255,255,255,0.07)",
            yaxis="y2",
        ))
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["ctl"], name="CTL",
            line=dict(color="#14B8A6", width=2.5),
        ))
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["atl"], name="ATL",
            line=dict(color="#FB923C", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["tsb"], name="TSB",
            line=dict(color="#A78BFA", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(167,139,250,0.07)",
        ))

        fig.update_layout(
            **_PLOTLY_BASE,
            margin=dict(l=40, r=40, t=10, b=40),
            height=420,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(color="#9CA3AF")),
            xaxis=_AXIS,
            yaxis=dict(title="CTL / ATL / TSB", **_AXIS),
            yaxis2=dict(title="TSS", side="right", overlaying="y", showgrid=False, linecolor="#2D3748"),
            shapes=[dict(
                type="line", y0=0, y1=0,
                x0=df["date"].iloc[0], x1=df["date"].iloc[-1],
                xref="x", yref="y",
                line=dict(color="#4B5563", width=1, dash="dot"),
            )],
        )
        st.plotly_chart(fig, use_container_width=True)


# ── HRV ──────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">HRV Status</div>', unsafe_allow_html=True)

hrv_df = load_hrv_data()

if hrv_df.empty:
    st.info("No HRV data found. Go to Settings to sync from Garmin.")
else:
    if cutoff:
        hrv_df = hrv_df[hrv_df["date"] >= cutoff]

    if hrv_df.empty:
        st.info("No HRV data in the selected time range.")
    else:
        all_vals = hrv_df[["weekly_avg", "last_night"]].values.flatten()
        all_vals = all_vals[~pd.isna(all_vals)]
        y_min = max(0, all_vals.min() - 15)
        y_max = all_vals.max() + 15

        hrv_fig = go.Figure()

        # Baseline bands
        has_bands = (
            "baseline_low_upper" in hrv_df.columns
            and "baseline_balanced_low" in hrv_df.columns
            and "baseline_balanced_upper" in hrv_df.columns
            and hrv_df["baseline_balanced_low"].notna().any()
        )
        if has_bands:
            b = hrv_df.dropna(subset=["baseline_balanced_low"])
            # Low zone (below low_upper) — red tint
            hrv_fig.add_trace(go.Scatter(x=b["date"], y=b["baseline_low_upper"],    mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
            hrv_fig.add_trace(go.Scatter(x=b["date"], y=[y_min]*len(b),             mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(248,113,113,0.07)", showlegend=False, hoverinfo="skip"))
            # Mid zone (low_upper → balanced_low) — amber tint
            hrv_fig.add_trace(go.Scatter(x=b["date"], y=b["baseline_balanced_low"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
            hrv_fig.add_trace(go.Scatter(x=b["date"], y=b["baseline_low_upper"],    mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(250,204,21,0.06)",  showlegend=False, hoverinfo="skip"))
            # Balanced zone — green tint
            hrv_fig.add_trace(go.Scatter(x=b["date"], y=b["baseline_balanced_upper"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
            hrv_fig.add_trace(go.Scatter(x=b["date"], y=b["baseline_balanced_low"],   mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(74,222,128,0.07)",  showlegend=False, hoverinfo="skip"))

        # Nightly dots
        hrv_fig.add_trace(go.Scatter(
            x=hrv_df["date"], y=hrv_df["last_night"],
            mode="markers", name="Nightly",
            marker=dict(color="rgba(255,255,255,0.2)", size=4),
            hovertemplate="%{y:.0f} ms<extra>Nightly</extra>",
        ))

        # Weekly avg coloured by status
        STATUS_COLORS = {"BALANCED": "#4ADE80", "LOW": "#F87171", "UNBALANCED": "#FACC15"}
        for status, color in STATUS_COLORS.items():
            mask = hrv_df["status"] == status
            if mask.any():
                hrv_fig.add_trace(go.Scatter(
                    x=hrv_df[mask]["date"], y=hrv_df[mask]["weekly_avg"],
                    mode="markers", name=status.capitalize(),
                    marker=dict(color=color, size=7),
                    hovertemplate="%{y:.0f} ms<extra>Weekly avg</extra>",
                ))

        hrv_fig.update_layout(
            **_PLOTLY_BASE,
            margin=dict(l=40, r=40, t=10, b=40),
            height=260,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(color="#9CA3AF")),
            xaxis=_AXIS,
            yaxis=dict(title="HRV (ms)", range=[y_min, y_max], **_AXIS),
        )
        st.plotly_chart(hrv_fig, use_container_width=True)
