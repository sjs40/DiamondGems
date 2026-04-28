"""Tests for configuration and constants layers."""

from pathlib import Path

from diamond_gems import config, constants


def test_config_paths_are_absolute_paths() -> None:
    """Configured paths should be absolute pathlib.Path instances."""
    path_values = [
        config.PROJECT_ROOT,
        config.DATA_RAW_DIR,
        config.DATA_PROCESSED_DIR,
        config.DATA_OUTPUTS_DIR,
        config.APP_DIR,
    ]

    for path_value in path_values:
        assert isinstance(path_value, Path)
        assert path_value.is_absolute()


def test_data_paths_exist_or_can_be_created() -> None:
    """Data directories should exist or be creatable."""
    for data_dir in [config.DATA_RAW_DIR, config.DATA_PROCESSED_DIR, config.DATA_OUTPUTS_DIR]:
        data_dir.mkdir(parents=True, exist_ok=True)
        assert data_dir.exists()
        assert data_dir.is_dir()


def test_constants_import_and_required_columns_non_empty() -> None:
    """Constants should import and required column lists should be non-empty."""
    assert constants.REQUIRED_RAW_STATCAST_COLUMNS
    assert constants.MVP_PITCH_EVENTS_COLUMNS


def test_threshold_constants_are_numeric() -> None:
    """Configured thresholds should be numeric values."""
    numeric_values = [
        constants.STARTER_MIN_PITCHES_FOR_ANALYSIS,
        constants.MIN_PITCH_TYPE_COUNT,
        constants.USAGE_SPIKE_THRESHOLD,
        constants.MAJOR_USAGE_SPIKE_THRESHOLD,
        constants.VELO_SPIKE_THRESHOLD,
        constants.STRONG_VELO_SPIKE_THRESHOLD,
        constants.NEW_PITCH_PREVIOUS_USAGE_MAX,
        constants.NEW_PITCH_CURRENT_USAGE_MIN,
        constants.NEW_PITCH_MIN_COUNT,
        constants.ROLLING_STARTS_WINDOW,
    ]

    for value in numeric_values:
        assert isinstance(value, (int, float))
