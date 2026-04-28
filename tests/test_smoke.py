"""Smoke tests for project scaffolding."""


def test_package_imports() -> None:
    """Ensure package modules can be imported."""
    import diamond_gems
    from diamond_gems import config, constants

    assert diamond_gems is not None
    assert config.PROJECT_ROOT.is_absolute()
    assert constants.REQUIRED_RAW_STATCAST_COLUMNS
