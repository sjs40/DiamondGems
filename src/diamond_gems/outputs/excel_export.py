"""Excel dashboard export utilities."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from diamond_gems.config import DATA_OUTPUTS_DIR

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - project depends on pandas
    pd = None

SHEET_NAME_BY_TABLE = {
    "pitcher_start_summary": "Start Summary",
    "pitcher_pitch_type_summary": "Pitch Type Summary",
    "pitcher_velocity_deltas": "Velocity Deltas",
    "pitcher_usage_deltas": "Usage Deltas",
    "pitcher_trend_scores": "Trend Scores",
    "pitcher_flags": "Flags",
    "content_ideas": "Content Ideas",
}


def _to_records(table) -> list[dict]:
    if pd is not None and isinstance(table, pd.DataFrame):
        return table.to_dict("records")
    if hasattr(table, "to_dict"):
        return table.to_dict("records")
    return deepcopy(table)


def _to_pandas_df(table):
    if pd is None:  # pragma: no cover - guarded by project dependency
        raise ModuleNotFoundError("pandas is required for Excel export.")
    if isinstance(table, pd.DataFrame):
        return table.copy(deep=True)
    return pd.DataFrame.from_records(_to_records(table))


def _auto_adjust_column_widths(worksheet) -> None:
    for col_cells in worksheet.columns:
        values = ["" if cell.value is None else str(cell.value) for cell in col_cells]
        if not values:
            continue
        width = min(max(len(v) for v in values) + 2, 60)
        worksheet.column_dimensions[col_cells[0].column_letter].width = max(width, 10)


def export_excel_dashboard(
    tables: dict[str, "pd.DataFrame"],
    filename: str = "baseball_content_dashboard.xlsx",
) -> Path:
    """Export dashboard tables to a multi-sheet Excel workbook."""
    if pd is None:  # pragma: no cover - guarded by project dependency
        raise ModuleNotFoundError("pandas is required for Excel export.")

    output_dir = Path(DATA_OUTPUTS_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for table_key, sheet_name in SHEET_NAME_BY_TABLE.items():
            table = tables.get(table_key)
            if table is None:
                continue
            df = _to_pandas_df(table)
            if df.empty:
                continue
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = "A2"
            _auto_adjust_column_widths(worksheet)

    return output_path

