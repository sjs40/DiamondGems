"""Daily MVP pipeline runner."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from diamond_gems.config import DATA_OUTPUTS_DIR, RAW_DIR
from diamond_gems.features.arsenal import build_arsenal_concentration, build_pitch_mix_volatility
from diamond_gems.features.confidence import build_confidence_scores
from diamond_gems.features.context import add_basic_park_context, build_game_state_context
from diamond_gems.features.new_pitch_detector import build_new_pitch_detector
from diamond_gems.features.opponent_context import (
    build_opponent_team_context,
    build_pitcher_opponent_adjusted_metrics,
)
from diamond_gems.features.pitch_effectiveness_deltas import build_pitch_effectiveness_deltas
from diamond_gems.features.primary_pitch_quality import build_primary_pitch_quality_gap
from diamond_gems.features.sequencing import build_pitch_sequencing_summary
from diamond_gems.features.stability import build_stability_scores
from diamond_gems.features.times_through_order import (
    build_times_through_order_splits,
    build_tto_penalty_summary,
)
from diamond_gems.features.trend_scores import build_pitcher_trend_scores
from diamond_gems.features.usage_deltas import build_pitcher_usage_deltas
from diamond_gems.features.velocity_deltas import build_pitcher_velocity_deltas
from diamond_gems.ingest.statcast_download import download_statcast_csv_for_date
from diamond_gems.outputs.content_ideas import build_content_ideas
from diamond_gems.outputs.excel_export import export_excel_dashboard
from diamond_gems.outputs.export import export_table
from diamond_gems.outputs.flags import build_pitcher_flags
from diamond_gems.transform.pitch_events import clean_pitch_events
from diamond_gems.transform.pitch_type_summary import build_pitcher_pitch_type_summary
from diamond_gems.transform.pitcher_start_summary import build_pitcher_start_summary

PITCH_NAME_TO_TYPE = {
    "4-seam fastball": "FF",
    "sinker": "SI",
    "cutter": "FC",
    "slider": "SL",
    "sweeper": "ST",
    "curveball": "CU",
    "knuckle curve": "KC",
    "changeup": "CH",
    "splitter": "FS",
    "forkball": "FO",
    "knuckleball": "KN",
    "eephus": "EP",
    "slurve": "SV",
}


class RecordFrame:
    """Minimal DataFrame-like container compatible with project helpers."""

    def __init__(self, records: list[dict]):
        self._records = [dict(r) for r in records]

    @property
    def columns(self) -> list[str]:
        keys = set()
        for row in self._records:
            keys.update(row.keys())
        return sorted(keys)

    def to_dict(self, orient: str):
        if orient != "records":
            raise ValueError("Only records orient is supported")
        return [dict(r) for r in self._records]

    @classmethod
    def from_records(cls, records: list[dict]):
        return cls(records)


def _read_csv(path: Path) -> RecordFrame:
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
    return RecordFrame(rows)


def _coerce_basic_types(frame: RecordFrame) -> RecordFrame:
    out = []
    for row in frame.to_dict("records"):
        rc = {}
        for k, v in row.items():
            if v == "":
                rc[k] = None
                continue
            if k in {"game_pk", "pitcher", "batter", "inning", "balls", "strikes", "outs_when_up", "post_home_score", "post_away_score", "zone"}:
                try:
                    rc[k] = int(float(v))
                    continue
                except Exception:
                    pass
            if k in {"release_speed", "release_spin_rate", "release_extension", "pfx_x", "pfx_z", "plate_x", "plate_z", "launch_speed", "launch_angle", "estimated_woba_using_speedangle", "woba_value"}:
                try:
                    rc[k] = float(v)
                    continue
                except Exception:
                    pass
            rc[k] = v
        out.append(rc)
    return RecordFrame(out)


def _normalize_raw_schema(frame: RecordFrame) -> RecordFrame:
    """Normalize common source column aliases from external downloads."""
    normalized = []
    for row in frame.to_dict("records"):
        row_copy = dict(row)

        if row_copy.get("pitcher_throws") is None and row_copy.get("p_throws") is not None:
            row_copy["pitcher_throws"] = row_copy.get("p_throws")

        if row_copy.get("pitch_type") is None:
            pitch_name = row_copy.get("pitch_name")
            if isinstance(pitch_name, str):
                row_copy["pitch_type"] = PITCH_NAME_TO_TYPE.get(pitch_name.strip().lower())

        normalized.append(row_copy)
    return RecordFrame(normalized)


def build_pitcher_appearances(pitch_events) -> RecordFrame:
    """Simple MVP appearance builder (one row per appearance_id)."""
    rows = pitch_events.to_dict("records")
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row.get("appearance_id")].append(row)

    appearances = []
    for appearance_id, group in grouped.items():
        g0 = group[0]
        terminal = [r for r in group if bool(r.get("pa_terminal_flag"))]
        batters_faced = len(terminal)
        opponent = None
        if str(g0.get("inning_topbot", "")).lower() == "top":
            opponent = g0.get("away_team")
        elif str(g0.get("inning_topbot", "")).lower() == "bot":
            opponent = g0.get("home_team")

        appearances.append(
            {
                "appearance_id": appearance_id,
                "pitcher_id": g0.get("pitcher_id"),
                "pitcher_name": g0.get("player_name"),
                "game_id": g0.get("game_id"),
                "game_date": g0.get("game_date"),
                "season": g0.get("season"),
                "opponent_team_id": opponent,
                "opponent_team_abbr": opponent,
                "pitcher_throws": g0.get("pitcher_throws"),
                "role": "SP",
                "start_number_season": 1,
                "pitches_thrown": len(group),
                "batters_faced": batters_faced,
                "innings_pitched": 0.0,
            }
        )

    return RecordFrame(appearances)


def _find_latest_csv(raw_dir: Path) -> Path | None:
    files = sorted(raw_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _attach_appearance_ids(pitch_events: RecordFrame) -> RecordFrame:
    """Attach one appearance_id per game/pitcher/half inning group."""
    enriched = []
    for row in pitch_events.to_dict("records"):
        game_id = row.get("game_id")
        pitcher_id = row.get("pitcher_id")
        inning_topbot = row.get("inning_topbot")
        appearance_id = f"{game_id}_{pitcher_id}_{inning_topbot}"
        row_copy = dict(row)
        row_copy["appearance_id"] = appearance_id
        enriched.append(row_copy)
    return RecordFrame(enriched)


def _restore_pitch_columns(raw: RecordFrame, pitch_events: RecordFrame) -> RecordFrame:
    """Restore pitch identifiers that are needed downstream."""
    raw_rows = raw.to_dict("records")
    cleaned_rows = pitch_events.to_dict("records")
    if len(raw_rows) != len(cleaned_rows):
        raise ValueError("Raw and cleaned pitch row counts differ; cannot restore pitch columns.")

    merged = []
    for raw_row, cleaned_row in zip(raw_rows, cleaned_rows):
        row = dict(cleaned_row)
        row["pitch_type"] = raw_row.get("pitch_type")
        row["pitch_name"] = raw_row.get("pitch_name")
        merged.append(row)
    return RecordFrame(merged)


def _filter_table_by_game_date(table: RecordFrame, target_date: str) -> RecordFrame:
    rows = [r for r in table.to_dict("records") if str(r.get("game_date")) == target_date]
    return RecordFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run DiamondGems MVP daily pipeline")
    parser.add_argument("--input-file", type=str, default=None)
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--download-date", type=str, default=None)
    parser.add_argument("--download-provider", type=str, default="auto")
    parser.add_argument("--download-lookback-days", type=int, default=30)
    args = parser.parse_args(argv)

    if args.download_date and args.input_file:
        raise ValueError("Use either --input-file or --download-date, not both.")

    if args.download_date:
        input_path = download_statcast_csv_for_date(
            args.download_date,
            output_dir=RAW_DIR,
            provider=args.download_provider,
            lookback_days=args.download_lookback_days,
        )
    else:
        input_path = Path(args.input_file) if args.input_file else _find_latest_csv(RAW_DIR)
    if input_path is None or not input_path.exists():
        raise FileNotFoundError("No input CSV found. Provide --input-file or place CSV in data/raw.")

    raw = _normalize_raw_schema(_coerce_basic_types(_read_csv(input_path)))
    if not raw.to_dict("records"):
        raise ValueError("Input CSV has no rows for processing.")
    target_output_date = args.date or args.download_date

    pitch_events = clean_pitch_events(raw)
    pitch_events = _restore_pitch_columns(raw, pitch_events)
    pitch_events = _attach_appearance_ids(pitch_events)
    appearances = build_pitcher_appearances(pitch_events)
    pitcher_start_summary = build_pitcher_start_summary(pitch_events, appearances)
    pitcher_pitch_type_summary = build_pitcher_pitch_type_summary(pitch_events, appearances)
    pitcher_velocity_deltas = build_pitcher_velocity_deltas(pitcher_pitch_type_summary)
    pitcher_usage_deltas = build_pitcher_usage_deltas(pitcher_pitch_type_summary)
    pitch_effectiveness_deltas = build_pitch_effectiveness_deltas(pitcher_pitch_type_summary)
    arsenal_concentration = build_arsenal_concentration(pitcher_pitch_type_summary)
    pitch_mix_volatility = build_pitch_mix_volatility(pitcher_usage_deltas)
    stability_scores = build_stability_scores(pitcher_velocity_deltas, pitcher_usage_deltas, pitch_effectiveness_deltas)
    _ = build_pitch_sequencing_summary(pitch_events)
    tto_splits = build_times_through_order_splits(pitch_events)
    _ = build_tto_penalty_summary(tto_splits)
    primary_pitch_quality_gap = build_primary_pitch_quality_gap(pitcher_pitch_type_summary)
    new_pitch_detections = build_new_pitch_detector(pitcher_usage_deltas, pitcher_pitch_type_summary)
    opponent_team_context = build_opponent_team_context(pitch_events)
    opponent_adjusted_metrics = build_pitcher_opponent_adjusted_metrics(
        pitcher_start_summary, opponent_team_context, appearances
    )
    pitcher_start_summary = add_basic_park_context(pitcher_start_summary)
    _ = build_game_state_context(pitch_events)
    confidence_scores = build_confidence_scores(
        appearances, pitcher_start_summary, pitcher_pitch_type_summary, opponent_adjusted_metrics
    )
    pitcher_trend_scores = build_pitcher_trend_scores(
        pitcher_start_summary,
        pitcher_velocity_deltas,
        pitcher_usage_deltas,
        pitch_effectiveness_deltas,
        opponent_adjusted_metrics,
        arsenal_concentration,
        pitch_mix_volatility,
        stability_scores,
        confidence_scores,
    )
    pitcher_flags = build_pitcher_flags(
        pitcher_start_summary,
        pitcher_velocity_deltas,
        pitcher_usage_deltas,
        pitch_effectiveness_deltas,
        new_pitch_detections,
        opponent_adjusted_metrics,
        pitcher_trend_scores,
        confidence_scores,
        stability_scores,
        primary_pitch_quality_gap,
    )
    content_ideas = build_content_ideas(pitcher_flags)

    if target_output_date:
        pitch_events = _filter_table_by_game_date(pitch_events, target_output_date)
        appearances = _filter_table_by_game_date(appearances, target_output_date)
        pitcher_start_summary = _filter_table_by_game_date(pitcher_start_summary, target_output_date)
        pitcher_pitch_type_summary = _filter_table_by_game_date(pitcher_pitch_type_summary, target_output_date)
        pitcher_velocity_deltas = _filter_table_by_game_date(pitcher_velocity_deltas, target_output_date)
        pitcher_usage_deltas = _filter_table_by_game_date(pitcher_usage_deltas, target_output_date)
        pitcher_trend_scores = _filter_table_by_game_date(pitcher_trend_scores, target_output_date)
        pitcher_flags = _filter_table_by_game_date(pitcher_flags, target_output_date)
        content_ideas = _filter_table_by_game_date(content_ideas, target_output_date)

    if args.output_dir:
        import diamond_gems.outputs.export as export_mod
        import diamond_gems.outputs.excel_export as excel_export_mod

        export_mod.DATA_OUTPUTS_DIR = Path(args.output_dir)
        excel_export_mod.DATA_OUTPUTS_DIR = Path(args.output_dir)

    written = {}
    written["pitch_events"] = export_table(pitch_events, "pitch_events", include_csv=False, include_parquet=True)
    written["pitcher_appearances"] = export_table(appearances, "pitcher_appearances", include_csv=True, include_parquet=True)
    written["pitcher_start_summary"] = export_table(pitcher_start_summary, "pitcher_start_summary", include_csv=True, include_parquet=True)
    written["pitcher_pitch_type_summary"] = export_table(pitcher_pitch_type_summary, "pitcher_pitch_type_summary", include_csv=True, include_parquet=True)
    written["pitcher_velocity_deltas"] = export_table(pitcher_velocity_deltas, "pitcher_velocity_deltas", include_csv=True, include_parquet=True)
    written["pitcher_usage_deltas"] = export_table(pitcher_usage_deltas, "pitcher_usage_deltas", include_csv=True, include_parquet=True)
    written["pitcher_trend_scores"] = export_table(pitcher_trend_scores, "pitcher_trend_scores", include_csv=True, include_parquet=True)
    written["pitcher_flags"] = export_table(pitcher_flags, "pitcher_flags", include_csv=True, include_parquet=False)
    written["content_ideas"] = export_table(content_ideas, "content_ideas", include_csv=True, include_parquet=False)
    try:
        written["excel_dashboard"] = export_excel_dashboard(
            {
                "pitcher_start_summary": pitcher_start_summary,
                "pitcher_pitch_type_summary": pitcher_pitch_type_summary,
                "pitcher_velocity_deltas": pitcher_velocity_deltas,
                "pitcher_usage_deltas": pitcher_usage_deltas,
                "pitcher_trend_scores": pitcher_trend_scores,
                "pitcher_flags": pitcher_flags,
                "content_ideas": content_ideas,
            }
        )
    except ModuleNotFoundError:
        written["excel_dashboard"] = None

    print("Export summary:")
    for name, table in [
        ("pitch_events", pitch_events),
        ("pitcher_appearances", appearances),
        ("pitcher_start_summary", pitcher_start_summary),
        ("pitcher_pitch_type_summary", pitcher_pitch_type_summary),
        ("pitcher_velocity_deltas", pitcher_velocity_deltas),
        ("pitcher_usage_deltas", pitcher_usage_deltas),
        ("pitcher_trend_scores", pitcher_trend_scores),
        ("pitcher_flags", pitcher_flags),
        ("content_ideas", content_ideas),
    ]:
        print(f"- {name}: {len(table.to_dict('records'))} rows")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
