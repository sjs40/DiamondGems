"""Opponent context and opponent-adjusted pitcher metrics."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

from diamond_gems.validation import safe_divide, validate_required_columns

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    pd = None

CONTEXT_REQUIRED = [
    "game_date",
    "pitcher_throws",
    "inning_topbot",
    "home_team",
    "away_team",
    "swing_flag",
    "whiff_flag",
    "chase_flag",
    "pa_terminal_flag",
]


def _to_records(df) -> list[dict]:
    if pd is not None and isinstance(df, pd.DataFrame):
        return df.to_dict("records")
    if hasattr(df, "to_dict"):
        return df.to_dict("records")
    return deepcopy(df)


def _from_records(records: list[dict], template):
    if pd is not None and isinstance(template, pd.DataFrame):
        return pd.DataFrame.from_records(records)
    frame_cls = template.__class__
    if hasattr(frame_cls, "from_records"):
        return frame_cls.from_records(records)
    return records


def _parse_date(value):
    if hasattr(value, "date") and not isinstance(value, str):
        return value.date() if hasattr(value, "hour") else value
    return datetime.fromisoformat(str(value)).date()


def _is_valid(value) -> bool:
    return value is not None and value == value


def _mean(values: list[float]):
    vals = [float(v) for v in values if _is_valid(v)]
    if not vals:
        return float("nan")
    return sum(vals) / len(vals)


def _infer_offense_team(row: dict):
    return row.get("away_team") if str(row.get("inning_topbot")).lower() == "top" else row.get("home_team")


def _zscore(value, all_values: list[float]):
    valid = [v for v in all_values if _is_valid(v)]
    if not _is_valid(value) or len(valid) < 2:
        return float("nan")
    mean = sum(valid) / len(valid)
    var = sum((v - mean) ** 2 for v in valid) / len(valid)
    std = var ** 0.5
    if std == 0:
        return 0.0
    return (value - mean) / std


def build_opponent_team_context(pitch_events):
    """Build team offensive context by as-of-date, window, and handedness."""
    validate_required_columns(pitch_events, CONTEXT_REQUIRED, df_name="pitch_events")

    raw_rows = _to_records(pitch_events)
    rows = []
    for row in raw_rows:
        row_copy = deepcopy(row)
        row_copy["game_date"] = _parse_date(row_copy.get("game_date"))
        row_copy["offense_team"] = _infer_offense_team(row_copy)
        row_copy["handedness_split"] = "vs_RHP" if row_copy.get("pitcher_throws") == "R" else "vs_LHP"
        row_copy["csw_flag"] = bool(row_copy.get("whiff_flag")) or bool(row_copy.get("called_strike_flag"))
        rows.append(row_copy)

    as_of_dates = sorted({row["game_date"] for row in rows})
    teams = sorted({row.get("offense_team") for row in rows})

    output_rows: list[dict] = []

    for as_of_date in as_of_dates:
        for window in ["season_to_date", "last_30"]:
            for split in ["vs_RHP", "vs_LHP"]:
                for team in teams:
                    candidates = [
                        row
                        for row in rows
                        if row.get("offense_team") == team
                        and row.get("handedness_split") == split
                        and row.get("game_date") < as_of_date
                    ]
                    if window == "last_30":
                        lower = as_of_date - timedelta(days=30)
                        candidates = [row for row in candidates if row.get("game_date") >= lower]

                    if not candidates:
                        continue

                    swings = sum(1 for r in candidates if bool(r.get("swing_flag")))
                    whiffs = sum(1 for r in candidates if bool(r.get("whiff_flag")))
                    chases = sum(1 for r in candidates if bool(r.get("chase_flag")))
                    in_zone = sum(1 for r in candidates if bool(r.get("in_zone_flag")))
                    pitches = len(candidates)
                    out_of_zone = pitches - in_zone
                    pa_terminal = [r for r in candidates if bool(r.get("pa_terminal_flag"))]
                    qualified_pa = len(pa_terminal)

                    k_count = sum(1 for r in pa_terminal if bool(r.get("strikeout_flag")))
                    bb_count = sum(1 for r in pa_terminal if bool(r.get("walk_flag")))

                    batted = [r for r in candidates if bool(r.get("batted_ball_flag"))]

                    output_rows.append(
                        {
                            "team_id": team,
                            "team_abbr": team,
                            "as_of_date": str(as_of_date),
                            "season": as_of_date.year,
                            "window": window,
                            "handedness_split": split,
                            "qualified_pa": qualified_pa,
                            "pitches_seen": pitches,
                            "swing_rate": safe_divide(swings, pitches),
                            "whiff_rate": safe_divide(whiffs, swings),
                            "contact_rate": safe_divide(max(swings - whiffs, 0), swings),
                            "chase_rate": safe_divide(chases, out_of_zone),
                            "k_rate": safe_divide(k_count, qualified_pa),
                            "bb_rate": safe_divide(bb_count, qualified_pa),
                            "k_minus_bb_rate": safe_divide(k_count, qualified_pa) - safe_divide(bb_count, qualified_pa),
                            "woba": _mean([r.get("woba_value") for r in pa_terminal]),
                            "xwoba": _mean([r.get("estimated_woba_using_speedangle") for r in pa_terminal]),
                            "hard_hit_rate": safe_divide(
                                sum(1 for r in batted if bool(r.get("hard_hit_flag"))),
                                len(batted),
                            ),
                            "opponent_quality_score": float("nan"),
                            "low_sample_flag": qualified_pa < 20,
                        }
                    )

    # z-score placeholder quality score per as_of_date/window/split
    grouped: dict[tuple, list[dict]] = {}
    for row in output_rows:
        grouped.setdefault((row["as_of_date"], row["window"], row["handedness_split"]), []).append(row)

    for group_rows in grouped.values():
        woba_vals = [r.get("woba") for r in group_rows]
        xwoba_vals = [r.get("xwoba") for r in group_rows]
        contact_vals = [r.get("contact_rate") for r in group_rows]
        hard_vals = [r.get("hard_hit_rate") for r in group_rows]
        k_vals = [r.get("k_rate") for r in group_rows]
        whiff_vals = [r.get("whiff_rate") for r in group_rows]

        for row in group_rows:
            if row.get("low_sample_flag"):
                row["opponent_quality_score"] = float("nan")
                continue
            score = (
                _zscore(row.get("woba"), woba_vals)
                + _zscore(row.get("xwoba"), xwoba_vals)
                + _zscore(row.get("contact_rate"), contact_vals)
                + _zscore(row.get("hard_hit_rate"), hard_vals)
                - _zscore(row.get("k_rate"), k_vals)
                - _zscore(row.get("whiff_rate"), whiff_vals)
            )
            row["opponent_quality_score"] = score

    return _from_records(output_rows, pitch_events)


def build_pitcher_opponent_adjusted_metrics(
    pitcher_start_summary,
    opponent_team_context,
    appearances,
):
    """Build one-row-per-appearance opponent-adjusted pitcher metrics."""
    start_rows = _to_records(pitcher_start_summary)
    context_rows = _to_records(opponent_team_context)
    appearance_rows = _to_records(appearances)

    start_lookup = {row.get("appearance_id"): row for row in start_rows}
    context_lookup: dict[tuple, dict] = {}
    for row in context_rows:
        context_lookup[(row.get("team_id"), row.get("as_of_date"), row.get("window"), row.get("handedness_split"))] = row

    output_rows: list[dict] = []
    for app in appearance_rows:
        appearance_id = app.get("appearance_id")
        start = start_lookup.get(appearance_id, {})

        team_id = app.get("opponent_team_id")
        game_date = str(app.get("game_date"))
        split = "vs_RHP" if app.get("pitcher_throws") == "R" else "vs_LHP"

        ctx_last30 = context_lookup.get((team_id, game_date, "last_30", split))
        ctx_season = context_lookup.get((team_id, game_date, "season_to_date", split))

        chosen = None
        window = None
        if ctx_last30 and not bool(ctx_last30.get("low_sample_flag")):
            chosen = ctx_last30
            window = "last_30"
        elif ctx_season:
            chosen = ctx_season
            window = "season_to_date"

        opp_pa = chosen.get("qualified_pa") if chosen else float("nan")
        low_context = bool(chosen.get("low_sample_flag")) if chosen else True

        raw_whiff = start.get("whiff_rate")
        raw_csw = start.get("csw_rate")
        raw_k = start.get("k_rate")
        raw_chase = start.get("chase_rate")
        raw_contact = start.get("contact_rate")
        raw_hard_hit = start.get("hard_hit_rate_allowed")
        raw_xwoba = start.get("xwoba_allowed")

        opp_whiff = chosen.get("whiff_rate") if chosen else float("nan")
        opp_contact = chosen.get("contact_rate") if chosen else float("nan")
        opp_k = chosen.get("k_rate") if chosen else float("nan")
        opp_chase = chosen.get("chase_rate") if chosen else float("nan")
        opp_woba = chosen.get("woba") if chosen else float("nan")
        opp_xwoba = chosen.get("xwoba") if chosen else float("nan")
        opp_csw = (opp_whiff + opp_k) / 2 if _is_valid(opp_whiff) and _is_valid(opp_k) else float("nan")

        output_rows.append(
            {
                "appearance_id": appearance_id,
                "pitcher_id": app.get("pitcher_id"),
                "pitcher_name": app.get("pitcher_name"),
                "game_date": app.get("game_date"),
                "opponent_team_id": team_id,
                "opponent_team_abbr": app.get("opponent_team_abbr") or team_id,
                "pitcher_throws": app.get("pitcher_throws"),
                "opponent_context_window": window,
                "opponent_qualified_pa": opp_pa,
                "raw_whiff_rate": raw_whiff,
                "raw_csw_rate": raw_csw,
                "raw_k_rate": raw_k,
                "raw_chase_rate": raw_chase,
                "raw_contact_rate_allowed": raw_contact,
                "raw_hard_hit_rate_allowed": raw_hard_hit,
                "raw_xwoba_allowed": raw_xwoba,
                "opponent_whiff_rate_baseline": opp_whiff,
                "opponent_csw_rate_baseline": opp_csw,
                "opponent_k_rate_baseline": opp_k,
                "opponent_chase_rate_baseline": opp_chase,
                "opponent_contact_rate_baseline": opp_contact,
                "opponent_woba_baseline": opp_woba,
                "opponent_xwoba_baseline": opp_xwoba,
                "adjusted_whiff_rate_diff": raw_whiff - opp_whiff if _is_valid(raw_whiff) and _is_valid(opp_whiff) else float("nan"),
                "adjusted_whiff_rate_index": safe_divide(raw_whiff, opp_whiff),
                "adjusted_k_rate_diff": raw_k - opp_k if _is_valid(raw_k) and _is_valid(opp_k) else float("nan"),
                "adjusted_k_rate_index": safe_divide(raw_k, opp_k),
                "adjusted_chase_rate_diff": raw_chase - opp_chase if _is_valid(raw_chase) and _is_valid(opp_chase) else float("nan"),
                "adjusted_contact_rate_index": safe_divide(raw_contact, opp_contact),
                "adjusted_xwoba_allowed_diff": raw_xwoba - opp_xwoba if _is_valid(raw_xwoba) and _is_valid(opp_xwoba) else float("nan"),
                "opponent_quality_score": chosen.get("opponent_quality_score") if chosen else float("nan"),
                "opponent_adjustment_confidence": min(max((opp_pa or 0) / 200.0, 0.0), 1.0) if _is_valid(opp_pa) else 0.0,
                "low_context_sample_flag": low_context,
            }
        )

    return _from_records(output_rows, appearances)
