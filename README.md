# DiamondGems

DiamondGems is a Python analytics pipeline that identifies **content-worthy MLB pitcher signals** from pitch-level data.

## Project purpose

The goal of this MVP is to take raw Statcast-like pitch event data and produce:

- cleaned event-level analytics tables,
- pitcher-start and pitch-type summaries,
- signal/flag outputs for noteworthy pitcher changes,
- content ideas for downstream editorial workflows,
- and analyst-friendly artifacts (CSV, Parquet, and Excel dashboard workbook).

## What the system finds

The MVP computes pitcher-focused signals such as:

- velocity deltas,
- pitch usage deltas,
- pitch effectiveness deltas,
- arsenal concentration / pitch mix volatility,
- opponent-adjusted context,
- trend scoring,
- confidence/stability-supporting metrics,
- pitcher flags and content ideas.

## Scope (MVP)

- **Pitchers only** in the MVP.
- **Hitters will be added later** in a future version.
- Trend/flag scoring currently uses **manual placeholder weights** to keep the MVP transparent and testable; **learned/model-based weights are planned for a later version**.

## Project layout

```text
DiamondGems/
  AGENTS.md
  README.md
  pyproject.toml
  data/
    raw/
    processed/
    outputs/
  src/
    diamond_gems/
      __init__.py
      config.py
      constants.py
      validation.py
      run_daily.py
      ingest/
        __init__.py
      transform/
        __init__.py
        pitch_events.py
        pitcher_start_summary.py
        pitch_type_summary.py
      features/
        __init__.py
        *.py
      outputs/
        __init__.py
        export.py
        excel_export.py
        flags.py
        content_ideas.py
  app/
    streamlit_app.py
  tests/
    test_*.py
```

## Windows setup instructions

1. Create a virtual environment:
   - `python -m venv .venv`
2. Activate it (PowerShell):
   - `.venv\Scripts\Activate.ps1`
3. If execution policy blocks activation, run (PowerShell as needed):
   - `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
4. Upgrade pip (recommended):
   - `python -m pip install --upgrade pip`

If `python` is not found on your machine, use `py` instead of `python` in all commands below.

## Install dependencies

Install project dependencies:

```bash
python -m pip install -e .
```

Optional dev extras:

```bash
python -m pip install -e .[dev]
```

## Run tests

```bash
python -m pytest
```

## Run the daily pipeline

```bash
python -m diamond_gems.run_daily --input-file data/raw/example_statcast.csv
```

## Run Streamlit

```bash
python -m streamlit run app/streamlit_app.py
```

## Output files

After a successful daily run, `data/outputs/` includes (at minimum):

- `pitcher_start_summary.csv`
- `pitcher_start_summary.parquet`
- `pitcher_pitch_type_summary.csv`
- `pitcher_pitch_type_summary.parquet`
- `pitcher_velocity_deltas.csv`
- `pitcher_usage_deltas.csv`
- `pitcher_trend_scores.csv`
- `pitcher_flags.csv`
- `content_ideas.csv`
- `baseball_content_dashboard.xlsx`
