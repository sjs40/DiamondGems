# DiamondGems

DiamondGems is a starter Python project for building a daily baseball data pipeline and lightweight dashboard.

This repository currently includes only project scaffolding, configuration, and placeholders. No baseball-specific data logic has been implemented yet.

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
      run_daily.py
      ingest/
        __init__.py
      transform/
        __init__.py
      features/
        __init__.py
      outputs/
        __init__.py
  app/
    streamlit_app.py
  tests/
```

## Quick start

1. Create and activate your virtual environment:
   - `python -m venv .venv`
   - Windows: `.venv\\Scripts\\activate`
2. Install the project (and dev tools if desired):
   - `python -m pip install -e .`
   - `python -m pip install -e .[dev]`

If `python` is not available on your system (common on some Windows setups), use the same commands with `py`.

## Common commands

Use `python` first:

- Run tests:
  - `python -m pytest`
- Run the daily entrypoint:
  - `python -m diamond_gems.run_daily`
- Launch the Streamlit app:
  - `python -m streamlit run app/streamlit_app.py`

If `python` is not found, retry with `py`:

- `py -m pytest`
- `py -m diamond_gems.run_daily`
- `py -m streamlit run app/streamlit_app.py`
