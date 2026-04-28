# DiamondGems

## Goal
Build a Python analytics pipeline that identifies content-worthy MLB pitcher signals from pitch-level data.

The MVP is pitcher-focused. Hitters will be added later.

## Coding standards
- Use Python 3.11+
- Use pandas and numpy for MVP transformations
- Use pathlib for paths
- Keep functions small and testable
- Prefer explicit column names
- Validate required columns before transformations
- Do not silently drop required columns
- Do not mutate input DataFrames
- Store raw data separately from processed/output data
- Never overwrite raw input files
- Write pytest tests for every transformation and feature module
- Keep data grains clear:
  - pitch_events = one row per pitch
  - pitcher_appearances = one row per pitcher outing
  - pitcher_start_summary = one row per pitcher outing
  - pitcher_pitch_type_summary = one row per outing/pitch type
  - flags = one row per detected signal
  - content_ideas = one row per content idea

## MVP scope
Pitchers only.

MVP should support:
- pitch event cleaning
- pitcher appearance summaries
- pitcher start summaries
- pitch-type summaries
- velocity deltas
- usage deltas
- pitch effectiveness deltas
- sequencing/order effects
- times through the order splits
- rolling 3-start baselines
- new pitch detection
- pitch mix volatility
- arsenal concentration
- opponent adjustment
- opponent quality
- basic park factor fields
- basic game state context
- trend scores
- stability/consistency score
- confidence score
- pitcher flags
- content ideas
- CSV exports
- Parquet exports for core analytic tables
- basic Streamlit dashboard

## Important development rule
Implement one feature at a time. Do not add unrelated features.

Every prompt should end by running:
`python -m pytest`

If tests fail, fix them before stopping.
