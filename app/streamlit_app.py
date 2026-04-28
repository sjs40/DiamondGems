"""Basic Streamlit dashboard for DiamondGems outputs."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

if importlib.util.find_spec("streamlit") is not None:  # pragma: no cover - optional UI dependency
    import streamlit as st  # type: ignore
else:  # pragma: no cover - optional UI dependency
    st = None

OUTPUTS_DIR = Path("data/outputs")


def load_output_csv(filename: str) -> tuple[pd.DataFrame | None, str | None]:
    """Load a CSV from data/outputs and return (dataframe, message)."""
    path = OUTPUTS_DIR / filename
    if not path.exists():
        return None, f"{filename} was not found in {OUTPUTS_DIR}."
    if path.stat().st_size == 0:
        return None, f"{filename} is empty. Run the daily pipeline to populate this table."
    try:
        return pd.read_csv(path), None
    except pd.errors.EmptyDataError:
        return None, f"{filename} has no columns/data yet. Run the daily pipeline to populate this table."


def apply_min_numeric_filter(df: pd.DataFrame, column: str, minimum: float) -> pd.DataFrame:
    """Apply a minimum numeric filter if the column exists."""
    if column not in df.columns:
        return df
    numeric_series = pd.to_numeric(df[column], errors="coerce")
    return df[numeric_series >= minimum].copy()


def apply_date_range_filter(
    df: pd.DataFrame,
    column: str,
    start_date,
    end_date,
) -> pd.DataFrame:
    """Apply a date range filter if the column exists."""
    if column not in df.columns:
        return df
    date_series = pd.to_datetime(df[column], errors="coerce")
    keep = date_series.between(pd.to_datetime(start_date), pd.to_datetime(end_date), inclusive="both")
    return df[keep].copy()


def _multiselect_filter(df: pd.DataFrame, label: str, column: str) -> pd.DataFrame:
    if column not in df.columns:
        st.caption(f"Column `{column}` not available; skipping filter.")
        return df
    options = sorted(df[column].dropna().astype(str).unique().tolist())
    selected = st.multiselect(label, options=options, default=options)
    if not selected:
        return df.iloc[0:0].copy()
    return df[df[column].astype(str).isin(selected)].copy()


def _show_overview(flags_df: pd.DataFrame | None, ideas_df: pd.DataFrame | None, starts_df: pd.DataFrame | None) -> None:
    st.header("Overview")
    start_count = 0 if starts_df is None else len(starts_df)
    flag_count = 0 if flags_df is None else len(flags_df)
    idea_count = 0 if ideas_df is None else len(ideas_df)

    c1, c2, c3 = st.columns(3)
    c1.metric("Pitcher Starts", start_count)
    c2.metric("Flags", flag_count)
    c3.metric("Content Ideas", idea_count)


def _show_flags_section() -> pd.DataFrame | None:
    st.header("Pitcher Flags")
    flags_df, message = load_output_csv("pitcher_flags.csv")
    if flags_df is None:
        st.info(message)
        return None

    flags_df = _multiselect_filter(flags_df, "Pitcher Name", "pitcher_name")
    flags_df = _multiselect_filter(flags_df, "Signal Category", "signal_category")
    flags_df = _multiselect_filter(flags_df, "Severity", "severity")
    min_conf = st.slider("Minimum confidence_score", 0.0, 1.0, 0.0, 0.05)
    flags_df = apply_min_numeric_filter(flags_df, "confidence_score", min_conf)
    st.dataframe(flags_df, use_container_width=True)
    return flags_df


def _show_content_ideas_section() -> pd.DataFrame | None:
    st.header("Content Ideas")
    ideas_df, message = load_output_csv("content_ideas.csv")
    if ideas_df is None:
        st.info(message)
        return None

    ideas_df = _multiselect_filter(ideas_df, "Status", "status")
    ideas_df = _multiselect_filter(ideas_df, "Confidence", "confidence")
    ideas_df = _multiselect_filter(ideas_df, "Content Format", "content_format")
    st.dataframe(ideas_df, use_container_width=True)
    return ideas_df


def _show_start_summary_section() -> pd.DataFrame | None:
    st.header("Raw Start Summary")
    starts_df, message = load_output_csv("pitcher_start_summary.csv")
    if starts_df is None:
        st.info(message)
        return None

    starts_df = _multiselect_filter(starts_df, "Pitcher (Start Summary)", "pitcher_name")
    starts_df = _multiselect_filter(starts_df, "Opponent Team", "opponent_team_id")

    if "game_date" in starts_df.columns:
        parsed = pd.to_datetime(starts_df["game_date"], errors="coerce")
        valid_dates = parsed.dropna()
        if not valid_dates.empty:
            default_start = valid_dates.min().date()
            default_end = valid_dates.max().date()
            selected_range = st.date_input(
                "Date range",
                value=(default_start, default_end),
            )
            if isinstance(selected_range, tuple) and len(selected_range) == 2:
                starts_df = apply_date_range_filter(starts_df, "game_date", selected_range[0], selected_range[1])
    else:
        st.caption("Column `game_date` not available; skipping date filter.")

    st.dataframe(starts_df, use_container_width=True)
    return starts_df


def _show_pitch_type_summary_section() -> None:
    st.header("Pitch Type Summary")
    pitch_type_df, message = load_output_csv("pitcher_pitch_type_summary.csv")
    if pitch_type_df is None:
        st.info(message)
        return

    pitch_type_df = _multiselect_filter(pitch_type_df, "Pitcher (Pitch Type Summary)", "pitcher_name")
    pitch_type_df = _multiselect_filter(pitch_type_df, "Pitch Type", "pitch_type")
    min_pitch_count = st.number_input("Min pitch_count", min_value=0, value=0, step=1)
    pitch_type_df = apply_min_numeric_filter(pitch_type_df, "pitch_count", float(min_pitch_count))
    st.dataframe(pitch_type_df, use_container_width=True)


def _show_trend_scores_section() -> None:
    st.header("Trend Scores")
    trend_df, message = load_output_csv("pitcher_trend_scores.csv")
    if trend_df is None:
        st.info(message)
        return

    sort_col = "pitcher_change_score_percentile"
    if sort_col in trend_df.columns:
        trend_df = trend_df.sort_values(sort_col, ascending=False)
    else:
        st.caption(f"Column `{sort_col}` not available; showing unsorted table.")
    st.dataframe(trend_df, use_container_width=True)


def main() -> None:
    if st is None:
        raise ModuleNotFoundError("streamlit is not installed. Install with: python -m pip install -e .[ui]")
    st.set_page_config(page_title="DiamondGems Dashboard", layout="wide")
    st.title("DiamondGems Dashboard")
    st.caption("Basic MVP dashboard for pitcher starts, flags, and content ideas.")

    flags_df, _ = load_output_csv("pitcher_flags.csv")
    ideas_df, _ = load_output_csv("content_ideas.csv")
    starts_df, _ = load_output_csv("pitcher_start_summary.csv")

    _show_overview(flags_df, ideas_df, starts_df)
    _show_flags_section()
    _show_content_ideas_section()
    _show_start_summary_section()
    _show_pitch_type_summary_section()
    _show_trend_scores_section()


if __name__ == "__main__":
    main()
