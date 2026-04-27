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

## End-to-end quickstart (everything you need)

1. Clone the repo and enter it.
2. Create/activate a virtual environment (see Windows section above).
3. Install dependencies:
   - `python -m pip install -e .`
4. Get pitch-level input data (see **Data download / input prep** below).
5. Put your CSV in `data/raw/` (example: `data/raw/example_statcast.csv`).
6. Run tests:
   - `python -m pytest`
7. Run the daily pipeline:
   - `python -m diamond_gems.run_daily --input-file data/raw/example_statcast.csv`
8. Open generated files under `data/outputs/`.
9. Launch Streamlit:
   - `python -m streamlit run app/streamlit_app.py`

## Data download / input prep

This repo does **not** currently auto-download MLB data. For MVP, you bring a Statcast-like CSV and place it in `data/raw/`.

### Option A: Manual CSV export (Baseball Savant UI)

1. Go to Baseball Savant search/export tools.
2. Choose a date range and filters you want.
3. Export pitch-level CSV.
4. Save it as `data/raw/example_statcast.csv`.

### Option B: Script your own download (example approach)

Use your preferred data tool (for example, `pybaseball`) to generate a CSV with the required columns.

```python
# Example only (run separately, not part of package runtime)
from pybaseball import statcast

df = statcast(start_dt="2024-04-01", end_dt="2024-04-07")
df.to_csv("data/raw/example_statcast.csv", index=False)
```

### Required columns in the input CSV

Your CSV should include the MVP-required raw fields (for example):

`game_pk, game_date, pitcher, batter, player_name, pitcher_throws, pitch_type, pitch_name, release_speed, release_spin_rate, release_extension, pfx_x, pfx_z, plate_x, plate_z, zone, description, events, launch_speed, launch_angle, estimated_woba_using_speedangle, woba_value, inning, inning_topbot, balls, strikes, outs_when_up, home_team, away_team, post_home_score, post_away_score`

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

## Major use cases (with short output examples)

### 1) Daily pitcher monitoring for notable changes

Use case: Identify pitchers whose velocity/usage/effectiveness changed meaningfully in the most recent outing.

Command:

```bash
python -m diamond_gems.run_daily --input-file data/raw/example_statcast.csv
```

Example output (`pitcher_flags.csv`):

```text
pitcher_name,signal_category,severity,confidence_score,flag_reason
Pitcher A,velocity,high,0.82,Fastball velo +1.6 mph vs baseline
Pitcher B,usage,medium,0.68,Slider usage +10 percentage points
```

### 2) Pitch-shape and mix review by pitch type

Use case: Review per outing + pitch type metrics for pitch planning or content notes.

Example output (`pitcher_pitch_type_summary.csv`):

```text
pitcher_name,game_date,pitch_type,pitch_count,usage_rate,avg_velocity,whiff_rate
Pitcher A,2024-04-07,FF,52,0.48,96.1,0.31
Pitcher A,2024-04-07,SL,28,0.26,86.4,0.42
```

### 3) Start-level performance recap

Use case: Summarize each pitcher start in one row for quick reporting.

Example output (`pitcher_start_summary.csv`):

```text
pitcher_name,game_date,opponent_team_id,pitches_thrown,batters_faced,k_rate,bb_rate,xwoba_allowed
Pitcher A,2024-04-07,BOS,94,25,0.32,0.08,0.281
```

### 4) Content planning workflow

Use case: Turn model-detected flags into publishable ideas.

Example output (`content_ideas.csv`):

```text
pitcher_name,content_format,confidence,status,headline
Pitcher A,video,high,draft,Why Pitcher A's slider is suddenly dominant
```

### 5) Analyst handoff workbook export

Use case: Share a single multi-sheet file with non-technical users.

Example output (`baseball_content_dashboard.xlsx` sheets):

```text
Start Summary
Pitch Type Summary
Velocity Deltas
Usage Deltas
Trend Scores
Flags
Content Ideas
```
