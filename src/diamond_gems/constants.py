"""Project-wide constants for MVP pitcher analytics."""

REQUIRED_RAW_STATCAST_COLUMNS = [
    "game_pk",
    "game_date",
    "pitcher",
    "batter",
    "player_name",
    "pitcher_throws",
    "pitch_type",
    "pitch_name",
    "release_speed",
    "release_spin_rate",
    "release_extension",
    "pfx_x",
    "pfx_z",
    "plate_x",
    "plate_z",
    "zone",
    "description",
    "events",
    "launch_speed",
    "launch_angle",
    "estimated_woba_using_speedangle",
    "woba_value",
    "inning",
    "inning_topbot",
    "balls",
    "strikes",
    "outs_when_up",
    "home_team",
    "away_team",
    "post_home_score",
    "post_away_score",
]

MVP_PITCH_EVENTS_COLUMNS = [
    "game_pk",
    "game_date",
    "pitcher",
    "pitch_type",
    "pitch_name",
    "release_speed",
    "release_spin_rate",
    "release_extension",
    "pfx_x",
    "pfx_z",
    "plate_x",
    "plate_z",
    "zone",
    "description",
    "events",
    "inning",
    "inning_topbot",
    "balls",
    "strikes",
    "outs_when_up",
]

FASTBALL_PITCH_TYPES = {"FF", "SI", "FC"}
STARTER_MIN_PITCHES_FOR_ANALYSIS = 50
MIN_PITCH_TYPE_COUNT = 8
USAGE_SPIKE_THRESHOLD = 0.08
MAJOR_USAGE_SPIKE_THRESHOLD = 0.15
VELO_SPIKE_THRESHOLD = 1.0
STRONG_VELO_SPIKE_THRESHOLD = 1.5
NEW_PITCH_PREVIOUS_USAGE_MAX = 0.05
NEW_PITCH_CURRENT_USAGE_MIN = 0.15
NEW_PITCH_MIN_COUNT = 8
ROLLING_STARTS_WINDOW = 3
