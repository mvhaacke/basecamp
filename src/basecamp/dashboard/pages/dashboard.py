"""Dashboard page — PMC and HRV charts."""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dateutil.relativedelta import relativedelta

from basecamp.analytics.pmc import compute_pmc
from basecamp.analytics.wellness import load_hrv_data

st.title("Dashboard")

time_range = st.selectbox(
    "Time range",
    ["3 months", "6 months", "12 months", "24 months", "All time"],
    index=2,
)

range_months = {"3 months": 3, "6 months": 6, "12 months": 12, "24 months": 24}
cutoff = None
if time_range in range_months:
    cutoff = date.today() - relativedelta(months=range_months[time_range])

# --- PMC Chart ---

st.subheader("Performance Management Chart")

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
        cols = st.columns(3)
        cols[0].metric("CTL (Fitness)", f"{latest['ctl']:.0f}")
        cols[1].metric("ATL (Fatigue)", f"{latest['atl']:.0f}")
        cols[2].metric("TSB (Form)", f"{latest['tsb']:.0f}")

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=df["date"],
            y=df["tss"],
            name="Daily TSS",
            marker_color="rgba(180, 180, 180, 0.4)",
            yaxis="y2",
        ))

        fig.add_trace(go.Scatter(
            x=df["date"], y=df["ctl"], name="CTL (Fitness)",
            line=dict(color="#1f77b4", width=2),
        ))

        fig.add_trace(go.Scatter(
            x=df["date"], y=df["atl"], name="ATL (Fatigue)",
            line=dict(color="#d62728", width=2),
        ))

        fig.add_trace(go.Scatter(
            x=df["date"], y=df["tsb"], name="TSB (Form)",
            line=dict(color="#2ca02c", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(44, 160, 44, 0.1)",
        ))

        fig.update_layout(
            height=500,
            margin=dict(l=40, r=40, t=30, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            yaxis=dict(title="CTL / ATL / TSB", side="left"),
            yaxis2=dict(title="TSS", side="right", overlaying="y", showgrid=False),
            hovermode="x unified",
            shapes=[dict(
                type="line", y0=0, y1=0, x0=df["date"].iloc[0], x1=df["date"].iloc[-1],
                xref="x", yref="y", line=dict(color="gray", width=1, dash="dot"),
            )],
        )

        st.plotly_chart(fig, width="stretch")


# --- HRV Chart ---

st.subheader("HRV Status")

hrv_df = load_hrv_data()

if hrv_df.empty:
    st.info("No HRV data found. Go to Settings to sync from Garmin.")
else:
    if cutoff:
        hrv_df = hrv_df[hrv_df["date"] >= cutoff]

    if hrv_df.empty:
        st.info("No HRV data in the selected time range.")
    else:
        all_hrv_values = hrv_df[["weekly_avg", "last_night"]].values.flatten()
        all_hrv_values = all_hrv_values[~pd.isna(all_hrv_values)]
        y_min = max(0, all_hrv_values.min() - 15)
        y_max = all_hrv_values.max() + 15

        hrv_fig = go.Figure()

        has_baseline_cols = (
            "baseline_low_upper" in hrv_df.columns
            and "baseline_balanced_low" in hrv_df.columns
            and "baseline_balanced_upper" in hrv_df.columns
            and hrv_df["baseline_balanced_low"].notna().any()
        )
        if has_baseline_cols:
            baseline_df = hrv_df.dropna(subset=["baseline_balanced_low"])
            hrv_fig.add_trace(go.Scatter(
                x=baseline_df["date"], y=baseline_df["baseline_low_upper"],
                mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
            ))
            hrv_fig.add_trace(go.Scatter(
                x=baseline_df["date"], y=[y_min] * len(baseline_df),
                mode="lines", line=dict(width=0), fill="tonexty",
                fillcolor="rgba(214, 39, 40, 0.08)", showlegend=False, hoverinfo="skip",
            ))
            hrv_fig.add_trace(go.Scatter(
                x=baseline_df["date"], y=baseline_df["baseline_balanced_low"],
                mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
            ))
            hrv_fig.add_trace(go.Scatter(
                x=baseline_df["date"], y=baseline_df["baseline_low_upper"],
                mode="lines", line=dict(width=0), fill="tonexty",
                fillcolor="rgba(255, 127, 14, 0.08)", showlegend=False, hoverinfo="skip",
            ))
            hrv_fig.add_trace(go.Scatter(
                x=baseline_df["date"], y=baseline_df["baseline_balanced_upper"],
                mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
            ))
            hrv_fig.add_trace(go.Scatter(
                x=baseline_df["date"], y=baseline_df["baseline_balanced_low"],
                mode="lines", line=dict(width=0), fill="tonexty",
                fillcolor="rgba(44, 160, 44, 0.08)", showlegend=False, hoverinfo="skip",
            ))
            hrv_fig.add_trace(go.Scatter(
                x=baseline_df["date"], y=[y_max] * len(baseline_df),
                mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
            ))
            hrv_fig.add_trace(go.Scatter(
                x=baseline_df["date"], y=baseline_df["baseline_balanced_upper"],
                mode="lines", line=dict(width=0), fill="tonexty",
                fillcolor="rgba(255, 127, 14, 0.08)", showlegend=False, hoverinfo="skip",
            ))

        hrv_fig.add_trace(go.Scatter(
            x=hrv_df["date"],
            y=hrv_df["last_night"],
            mode="markers",
            name="Nightly HRV",
            marker=dict(color="rgba(150, 150, 150, 0.4)", size=5),
            hovertemplate="%{y:.0f} ms<extra>Nightly</extra>",
        ))

        for status, color in [("BALANCED", "#2ca02c"), ("LOW", "#d62728"), ("UNBALANCED", "#ff7f0e")]:
            mask = hrv_df["status"] == status
            if mask.any():
                subset = hrv_df[mask]
                hrv_fig.add_trace(go.Scatter(
                    x=subset["date"],
                    y=subset["weekly_avg"],
                    mode="markers",
                    name=f"Weekly Avg ({status.capitalize()})",
                    marker=dict(color=color, size=8),
                    hovertemplate="%{y:.0f} ms<extra>Weekly Avg</extra>",
                ))

        hrv_fig.update_layout(
            height=300,
            margin=dict(l=40, r=40, t=10, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            yaxis=dict(title="HRV (ms)", range=[y_min, y_max]),
            hovermode="x unified",
            showlegend=True,
        )

        st.plotly_chart(hrv_fig, width="stretch")