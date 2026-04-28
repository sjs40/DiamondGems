"""Enhanced Streamlit dashboard for DiamondGems outputs."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
from diamond_gems.features.baseline_archetypes import add_baseline_recent_features, assign_pitcher_archetypes, build_what_changed_today_summary

if importlib.util.find_spec("streamlit") is not None:  # pragma: no cover
    import streamlit as st  # type: ignore
else:  # pragma: no cover
    st = None

OUTPUTS_DIR = Path("data/outputs")


def apply_min_numeric_filter(df: pd.DataFrame, column: str, minimum: float) -> pd.DataFrame:
    if column not in df.columns:
        return df
    return df[pd.to_numeric(df[column], errors="coerce") >= minimum].copy()


def apply_date_range_filter(df: pd.DataFrame, column: str, start_date, end_date) -> pd.DataFrame:
    if column not in df.columns:
        return df
    s = pd.to_datetime(df[column], errors="coerce")
    return df[s.between(pd.to_datetime(start_date), pd.to_datetime(end_date), inclusive="both")].copy()


@st.cache_data(show_spinner=False) if st else (lambda f: f)
def load_output_csv(filename: str) -> tuple[pd.DataFrame | None, str | None]:
    path = OUTPUTS_DIR / filename
    if not path.exists():
        return None, f"{filename} was not found in {OUTPUTS_DIR}. Run: python -m diamond_gems.run_daily --input-file data/raw/example_statcast.csv"
    if path.stat().st_size == 0:
        return None, f"{filename} is empty."
    try:
        return pd.read_csv(path), None
    except pd.errors.EmptyDataError:
        return None, f"{filename} has no columns/data yet."


def main() -> None:
    if st is None:
        raise ModuleNotFoundError("streamlit is not installed. Install with: python -m pip install -e .[ui]")
    st.set_page_config(page_title="DiamondGems Dashboard", layout="wide")
    st.title("DiamondGems Dashboard")

    tabs = st.tabs(["Today's Gems", "What Changed Today", "Pitcher Detail", "Arsenal Changes", "Archetypes", "Flags", "Content Ideas"])
    trend, _ = load_output_csv("pitcher_trend_scores.csv")
    starts, _ = load_output_csv("pitcher_start_summary.csv")
    pitch_types, _ = load_output_csv("pitcher_pitch_type_summary.csv")
    flags, flags_message = load_output_csv("pitcher_flags.csv")
    ideas, ideas_message = load_output_csv("content_ideas.csv")

    enriched = pd.DataFrame()
    what_changed = pd.DataFrame()
    what_changed_text = ""
    if starts is not None and not starts.empty:
        enriched = assign_pitcher_archetypes(add_baseline_recent_features(starts, pitch_types if pitch_types is not None else None))
        what_changed, what_changed_text = build_what_changed_today_summary(enriched, ideas)

    with tabs[0]:
        st.subheader("Today's Gems")
        if trend is None:
            st.warning("pitcher_trend_scores.csv is required")
        else:
            st.dataframe(trend, use_container_width=True)
            if not enriched.empty:
                st.dataframe(enriched[[c for c in ["pitcher_name", "game_date", "primary_archetype", "archetype_confidence", "baseline_recent_summary", "velo_delta_vs_season", "usage_delta_vs_season", "whiff_delta_vs_season", "csw_delta_vs_season", "kbb_delta_vs_season"] if c in enriched.columns]], use_container_width=True)

    with tabs[1]:
        st.subheader("What Changed Today")
        if what_changed.empty:
            st.warning("No baseline change summary available.")
        else:
            a, b, c, d = st.columns(4)
            a.metric("Total pitchers", len(enriched))
            b.metric("Meaningful changes", int((enriched.get("baseline_sample_warning", "") == "OK").sum()))
            c.metric("High confidence", int((enriched.get("archetype_confidence", "") == "HIGH").sum()))
            d.metric("Actionable", int((enriched.get("archetype_confidence", "").isin(["HIGH", "MEDIUM"])).sum()))
            st.info(what_changed_text)
            st.dataframe(what_changed, use_container_width=True)

    with tabs[2]:
        st.subheader("Pitcher Detail")
        if pitch_types is None:
            st.warning("pitcher_pitch_type_summary.csv is required.")
        else:
            st.dataframe(pitch_types, use_container_width=True)

    with tabs[3]:
        st.subheader("Arsenal Changes")
        if pitch_types is None:
            st.warning("pitcher_pitch_type_summary.csv is required.")
        else:
            for col in ["usage_delta", "velocity_delta", "whiff_rate", "csw_rate"]:
                if col in pitch_types.columns:
                    st.markdown(f"**Top {col}**")
                    st.dataframe(pitch_types.sort_values(col, ascending=False).head(20), use_container_width=True)

    with tabs[4]:
        st.subheader("Archetypes")
        if enriched.empty:
            st.warning("Archetype layer requires pitcher_start_summary.csv")
        else:
            st.dataframe(enriched[[c for c in ["pitcher_name", "game_date", "primary_archetype", "secondary_archetypes", "archetype_confidence", "archetype_reason"] if c in enriched.columns]], use_container_width=True)

    with tabs[5]:
        st.subheader("Flags")
        if flags is None:
            st.warning(flags_message)
        else:
            st.dataframe(flags, use_container_width=True)

    with tabs[6]:
        st.subheader("Content Ideas")
        if ideas is None:
            st.warning(ideas_message)
        else:
            st.dataframe(ideas, use_container_width=True)


if __name__ == "__main__":
    main()
