-- Fantasy Data Platform — Schema DDL
-- All seven core tables + pipeline integration tables
-- Matches SQLAlchemy models in fantasy_data/models.py

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ---------------------------------------------------------------------------
-- Identity & Continuity
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS players (
    player_id   TEXT PRIMARY KEY,       -- Pipeline PLAYER ID (e.g., McCaCh01)
    pff_id      TEXT,                   -- PFF player ID (secondary, for grade joins)
    gsis_id     TEXT,
    sleeper_id  TEXT,
    full_name   TEXT NOT NULL,
    position    TEXT NOT NULL,           -- QB, RB, WR, TE, K
    position_group TEXT,                -- PASS_CATCHER, BACKFIELD, QB
    route_tree_type TEXT,               -- SLOT, OUTSIDE, FLEX, INLINE_TE, MOVE_TE
    team        TEXT,
    jersey_number INTEGER,
    age         REAL,
    years_pro   INTEGER,
    draft_year  INTEGER,
    draft_round INTEGER,
    draft_pick  INTEGER,
    college     TEXT,
    height_inches INTEGER,
    weight_lbs  INTEGER,
    forty_time  REAL,
    athleticism_score REAL,
    speed_score REAL,
    team_change_flag INTEGER DEFAULT 0,
    prev_team   TEXT,
    contract_year_flag INTEGER DEFAULT 0,
    injury_concern_flag INTEGER DEFAULT 0,
    rookie_flag INTEGER DEFAULT 0,
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT,
    updated_at  TEXT
);

CREATE INDEX IF NOT EXISTS ix_players_team ON players(team);
CREATE INDEX IF NOT EXISTS ix_players_position ON players(position);
CREATE INDEX IF NOT EXISTS ix_players_name ON players(full_name);


CREATE TABLE IF NOT EXISTS coaching_staff (
    staff_id    TEXT PRIMARY KEY,       -- team + season composite
    team        TEXT NOT NULL,
    season      INTEGER NOT NULL,
    head_coach  TEXT NOT NULL,
    offensive_coordinator TEXT,
    quarterbacks_coach TEXT,
    hc_year_with_team INTEGER,
    oc_year_with_team INTEGER,
    hc_continuity_flag INTEGER DEFAULT 0,
    oc_continuity_flag INTEGER DEFAULT 0,
    system_tag  TEXT,
    pass_rate_tendency REAL,
    te_usage_tendency REAL,
    rb_pass_usage_tendency REAL,
    tempo       TEXT,                   -- FAST, MEDIUM, SLOW
    notes       TEXT,
    created_at  TEXT,
    updated_at  TEXT,
    UNIQUE(team, season)
);

CREATE INDEX IF NOT EXISTS ix_coaching_team_season ON coaching_staff(team, season);


-- ---------------------------------------------------------------------------
-- Role Signal (Baseline)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS player_season_baseline (
    baseline_id TEXT PRIMARY KEY,       -- player_id + season composite
    player_id   TEXT NOT NULL REFERENCES players(player_id),
    season      INTEGER NOT NULL,
    team        TEXT,
    games_played INTEGER,
    games_started INTEGER,
    data_trust_weight REAL,
    hc_continuity INTEGER,
    oc_continuity INTEGER,
    seasons_in_system INTEGER,

    -- Opportunity Volume
    snap_share  REAL,
    route_participation_rate REAL,
    target_share REAL,
    rz_target_share REAL,
    ez_target_share REAL,
    carries_per_game REAL,
    rz_carry_share REAL,
    total_touches_per_game REAL,

    -- Opportunity Quality
    air_yards_share REAL,
    avg_depth_of_target REAL,
    avg_cushion REAL,
    avg_separation REAL,
    target_quality_rating REAL,
    route_grade_pff REAL,
    contested_target_rate REAL,

    -- Efficiency & Conversion
    racr        REAL,
    catch_rate  REAL,
    expected_catch_rate REAL,
    catch_rate_over_expected REAL,
    yards_per_route_run REAL,
    yards_after_catch_per_rec REAL,
    broken_tackle_rate REAL,
    drop_rate   REAL,
    pff_receiving_grade REAL,
    pff_run_blocking_grade REAL,

    -- Composite Demand
    wopr        REAL,
    dominator_rating REAL,
    market_share_score REAL,

    -- Backfield-Specific (RB)
    rb_role     TEXT,
    early_down_share REAL,
    third_down_carry_share REAL,
    third_down_target_share REAL,
    goal_line_carry_share REAL,
    pff_rush_grade REAL,
    yards_per_carry REAL,
    expected_yards_per_carry REAL,
    rush_yards_over_expected REAL,
    avg_box_count REAL,

    -- Market Calibration
    adp_consensus REAL,
    adp_underdog REAL,
    adp_positional_rank INTEGER,
    fp_projected_pts_ppr REAL,
    fp_projected_pts_std REAL,
    fp_positional_rank INTEGER,
    sharp_consensus_rank REAL,
    adp_divergence_rank INTEGER,
    adp_divergence_flag INTEGER DEFAULT 0,
    projection_uncertain_flag INTEGER DEFAULT 0,

    -- Per-Source Rankings
    rankings_avg_overall REAL,
    rankings_avg_positional REAL,
    rankings_hw_positional INTEGER,
    rankings_pff_positional INTEGER,
    rankings_ds_positional INTEGER,
    rankings_jj_positional INTEGER,
    rankings_fpts_positional INTEGER,
    rankings_source_count INTEGER,
    ecr_adp_delta REAL,
    ecr_avg_rank_delta REAL,
    rankings_last_updated TEXT,

    -- Scoring & Fantasy Output
    fantasy_pts_ppr REAL,
    fantasy_pts_std REAL,
    fantasy_pts_half REAL,
    fpts_per_game_ppr REAL,
    fpts_per_game_std REAL,
    td_rate     REAL,
    consistency_score REAL,
    boom_rate   REAL,
    bust_rate   REAL,

    UNIQUE(player_id, season)
);

CREATE INDEX IF NOT EXISTS ix_baseline_player ON player_season_baseline(player_id);
CREATE INDEX IF NOT EXISTS ix_baseline_season ON player_season_baseline(season);
CREATE INDEX IF NOT EXISTS ix_baseline_team ON player_season_baseline(team);


CREATE TABLE IF NOT EXISTS target_competition (
    competition_id TEXT PRIMARY KEY,
    player_id   TEXT NOT NULL REFERENCES players(player_id),
    season      INTEGER NOT NULL,
    team        TEXT NOT NULL,
    competitor_player_id TEXT REFERENCES players(player_id),
    competitor_name TEXT,
    competitor_position TEXT,
    competitor_route_type TEXT,
    route_overlap_score REAL,
    competition_type TEXT,
    competition_source TEXT,
    competitor_draft_round INTEGER,
    expected_role_impact REAL,
    notes       TEXT,
    created_at  TEXT
);

CREATE INDEX IF NOT EXISTS ix_competition_player ON target_competition(player_id);
CREATE INDEX IF NOT EXISTS ix_competition_team_season ON target_competition(team, season);


-- ---------------------------------------------------------------------------
-- Phase 2 & 3 Hooks
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS player_week (
    week_id     TEXT PRIMARY KEY,
    player_id   TEXT NOT NULL REFERENCES players(player_id),
    season      INTEGER NOT NULL,
    week        INTEGER NOT NULL,
    team        TEXT,
    opponent    TEXT,
    game_id     TEXT,
    snap_share_week REAL,
    target_share_week REAL,
    air_yards_share_week REAL,
    rz_target_share_week REAL,
    carries_week INTEGER,
    routes_run_week INTEGER,
    fantasy_pts_ppr_week REAL,
    fantasy_pts_std_week REAL,
    opponent_cb1_name TEXT,
    shadow_covered_flag INTEGER DEFAULT 0,
    game_script TEXT,
    team_implied_total REAL,
    matchup_adjustment REAL,
    created_at  TEXT,
    UNIQUE(player_id, season, week)
);

CREATE INDEX IF NOT EXISTS ix_player_week_player ON player_week(player_id);
CREATE INDEX IF NOT EXISTS ix_player_week_season_week ON player_week(season, week);


CREATE TABLE IF NOT EXISTS qualitative_signals (
    signal_id   TEXT PRIMARY KEY,
    scope_type  TEXT NOT NULL,
    player_id   TEXT REFERENCES players(player_id),
    team        TEXT NOT NULL,
    season      INTEGER NOT NULL,
    week_applicable INTEGER,
    signal_type TEXT NOT NULL,
    signal_direction TEXT,
    signal_summary TEXT NOT NULL,
    raw_excerpt TEXT,
    source_name TEXT,
    source_episode TEXT,
    source_url  TEXT,
    source_timestamp TEXT,
    analyst_name TEXT,
    credibility_tier INTEGER,
    confidence_score REAL,
    recency_weight REAL,
    hypothesis_id TEXT,
    validated_flag INTEGER DEFAULT 0,
    validation_result TEXT,
    created_at  TEXT,
    updated_at  TEXT
);

CREATE INDEX IF NOT EXISTS ix_signal_player ON qualitative_signals(player_id);
CREATE INDEX IF NOT EXISTS ix_signal_team_season ON qualitative_signals(team, season);
CREATE INDEX IF NOT EXISTS ix_signal_type ON qualitative_signals(signal_type);


