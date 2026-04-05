"""SQLAlchemy ORM models for the fantasy football data platform.

Seven core tables organized into three logical layers:
- Identity & Continuity: players, coaching_staff
- Role Signal (Baseline): player_season_baseline, target_competition
- Observation & Signal: player_week (Phase 2), qualitative_signals (Phase 3)
Plus: pipeline_id_map (bridge table for rankings pipeline integration)
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Identity & Continuity
# ---------------------------------------------------------------------------


class Player(Base):
    """Master identity table. Every downstream table references player_id."""

    __tablename__ = "players"

    player_id = Column(String, primary_key=True)  # Pipeline PLAYER ID (e.g., McCaCh01)
    pff_id = Column(String)  # PFF player ID (secondary, for grade joins)
    gsis_id = Column(String)
    sleeper_id = Column(String)
    full_name = Column(String, nullable=False)
    position = Column(String, nullable=False)  # QB, RB, WR, TE, K
    position_group = Column(String)  # PASS_CATCHER, BACKFIELD, QB
    route_tree_type = Column(String)  # SLOT, OUTSIDE, FLEX, INLINE_TE, MOVE_TE
    team = Column(String)
    jersey_number = Column(Integer)
    age = Column(Float)
    years_pro = Column(Integer)
    draft_year = Column(Integer)
    draft_round = Column(Integer)
    draft_pick = Column(Integer)
    college = Column(String)
    height_inches = Column(Integer)
    weight_lbs = Column(Integer)
    forty_time = Column(Float)
    athleticism_score = Column(Float)
    speed_score = Column(Float)
    team_change_flag = Column(Integer, default=0)
    prev_team = Column(String)
    contract_year_flag = Column(Integer, default=0)
    injury_concern_flag = Column(Integer, default=0)
    rookie_flag = Column(Integer, default=0)
    is_active = Column(Integer, default=1)
    created_at = Column(String, default=_now_iso)
    updated_at = Column(String, default=_now_iso, onupdate=_now_iso)

    baselines = relationship("PlayerSeasonBaseline", back_populates="player")

    __table_args__ = (
        Index("ix_players_team", "team"),
        Index("ix_players_position", "position"),
        Index("ix_players_name", "full_name"),
    )


class CoachingStaff(Base):
    """Offensive coaching continuity by team and season."""

    __tablename__ = "coaching_staff"

    staff_id = Column(String, primary_key=True)  # team + season composite
    team = Column(String, nullable=False)
    season = Column(Integer, nullable=False)
    head_coach = Column(String, nullable=False)
    offensive_coordinator = Column(String)
    quarterbacks_coach = Column(String)
    hc_year_with_team = Column(Integer)
    oc_year_with_team = Column(Integer)
    hc_continuity_flag = Column(Integer, default=0)
    oc_continuity_flag = Column(Integer, default=0)
    starting_qb = Column(String)  # Starting QB name (for audit/display)
    qb_continuity_flag = Column(Integer, default=1)  # 0 = new starter vs prior season
    system_tag = Column(String)  # MCVAY_TREE, SHANAHAN_ZONE, REID_WEST_COAST, etc.
    pass_rate_tendency = Column(Float)
    te_usage_tendency = Column(Float)
    rb_pass_usage_tendency = Column(Float)
    tempo = Column(String)  # FAST, MEDIUM, SLOW
    notes = Column(Text)
    created_at = Column(String, default=_now_iso)
    updated_at = Column(String, default=_now_iso, onupdate=_now_iso)

    __table_args__ = (
        Index("ix_coaching_team_season", "team", "season"),
        UniqueConstraint("team", "season", name="uq_coaching_team_season"),
    )


# ---------------------------------------------------------------------------
# Role Signal (Baseline)
# ---------------------------------------------------------------------------


class PlayerSeasonBaseline(Base):
    """Core role signal table. Each row = one player-season observation."""

    __tablename__ = "player_season_baseline"

    baseline_id = Column(String, primary_key=True)  # player_id + season composite
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False)
    season = Column(Integer, nullable=False)
    team = Column(String)
    games_played = Column(Integer)
    games_started = Column(Integer)
    data_trust_weight = Column(Float)  # 0-1, computed from coaching joins
    hc_continuity = Column(Integer)
    oc_continuity = Column(Integer)
    seasons_in_system = Column(Integer)

    # --- Opportunity Volume ---
    snap_share = Column(Float)
    route_participation_rate = Column(Float)
    target_share = Column(Float)
    rz_target_share = Column(Float)
    ez_target_share = Column(Float)
    carries_per_game = Column(Float)
    rz_carry_share = Column(Float)
    total_touches_per_game = Column(Float)

    # --- Opportunity Quality ---
    air_yards_share = Column(Float)
    avg_depth_of_target = Column(Float)
    avg_cushion = Column(Float)
    avg_separation = Column(Float)
    target_quality_rating = Column(Float)
    route_grade_pff = Column(Float)
    contested_target_rate = Column(Float)

    # --- Efficiency & Conversion ---
    racr = Column(Float)
    catch_rate = Column(Float)
    expected_catch_rate = Column(Float)
    catch_rate_over_expected = Column(Float)
    yards_per_route_run = Column(Float)
    yards_after_catch_per_rec = Column(Float)
    broken_tackle_rate = Column(Float)
    drop_rate = Column(Float)
    pff_offense_grade = Column(Float)
    pff_receiving_grade = Column(Float)
    pff_pass_block_grade = Column(Float)
    pff_run_blocking_grade = Column(Float)
    pff_passing_grade = Column(Float)  # QB only

    # --- Composite Demand ---
    wopr = Column(Float)  # (1.5 * target_share) + (0.7 * air_yards_share)
    dominator_rating = Column(Float)
    market_share_score = Column(Float)

    # --- Backfield-Specific (RB) ---
    rb_role = Column(String)  # WORKHORSE, COMMITTEE, PASS_DOWN, CHANGE_OF_PACE
    early_down_share = Column(Float)
    third_down_carry_share = Column(Float)
    third_down_target_share = Column(Float)
    goal_line_carry_share = Column(Float)
    pff_rush_grade = Column(Float)
    yards_per_carry = Column(Float)
    expected_yards_per_carry = Column(Float)
    rush_yards_over_expected = Column(Float)
    avg_box_count = Column(Float)

    # --- Market Calibration ---
    adp_consensus = Column(Float)
    adp_underdog = Column(Float)
    adp_positional_rank = Column(Integer)
    fp_projected_pts_ppr = Column(Float)
    fp_projected_pts_std = Column(Float)
    fp_positional_rank = Column(Integer)
    sharp_pos_rank = Column(Float)  # within-position sharp consensus (mean of 4 sharp POS RANKs)
    sharp_consensus_rank = Column(Float)  # format-neutral overall rank (via ADP scarcity curve)
    adp_divergence_pos = Column(Float)  # positional: adp_pos_rank - sharp_pos_rank
    adp_divergence_rank = Column(Integer)  # overall: ADP rank - sharp_consensus_rank
    adp_divergence_flag = Column(Integer, default=0)  # abs(adp_divergence_pos) >= 12
    projection_uncertain_flag = Column(Integer, default=0)

    # --- Per-Source Rankings (from rankings pipeline) ---
    rankings_avg_overall = Column(Float)
    rankings_avg_positional = Column(Float)  # mean of ALL sources
    rankings_hw_positional = Column(Integer)
    rankings_pff_positional = Column(Integer)
    rankings_ds_positional = Column(Integer)
    rankings_jj_positional = Column(Integer)
    rankings_fpts_positional = Column(Integer)
    rankings_source_count = Column(Integer)
    ecr_adp_delta = Column(Float)
    ecr_avg_rank_delta = Column(Float)
    rankings_last_updated = Column(String)

    # --- FTN Scheme Context (charting data, 2022+) ---
    play_action_target_pct = Column(Float)  # % of targets on play-action
    screen_target_pct = Column(Float)  # % of targets on screen passes
    contested_ball_pct = Column(Float)  # % of targets that were contested (FTN)
    catchable_ball_pct = Column(Float)  # % of targets that were catchable
    created_reception_pct = Column(Float)  # % of catches WR-created (not schemed)
    true_drop_rate = Column(Float)  # drops / catchable balls (FTN-charted)

    # --- Scoring & Fantasy Output ---
    fantasy_pts_ppr = Column(Float)
    fantasy_pts_std = Column(Float)
    fantasy_pts_half = Column(Float)
    fpts_per_game_ppr = Column(Float)
    fpts_per_game_std = Column(Float)
    td_rate = Column(Float)
    consistency_score = Column(Float)
    boom_rate = Column(Float)
    bust_rate = Column(Float)

    player = relationship("Player", back_populates="baselines")

    __table_args__ = (
        Index("ix_baseline_player", "player_id"),
        Index("ix_baseline_season", "season"),
        Index("ix_baseline_team", "team"),
        UniqueConstraint("player_id", "season", name="uq_baseline_player_season"),
    )


class TargetCompetition(Base):
    """Intra-team competition for targets and carries at route-tree level."""

    __tablename__ = "target_competition"

    competition_id = Column(String, primary_key=True)  # player + season + competitor
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False)
    season = Column(Integer, nullable=False)
    team = Column(String, nullable=False)
    competitor_player_id = Column(String, ForeignKey("players.player_id"))
    competitor_name = Column(String)
    competitor_position = Column(String)
    competitor_route_type = Column(String)
    route_overlap_score = Column(Float)  # 0-1
    competition_type = Column(String)  # DIRECT, VOLUME, NONE
    competition_source = Column(String)  # DRAFT, FREE_AGENT, TRADE, RETURNING
    competitor_draft_round = Column(Integer)
    expected_role_impact = Column(Float)  # -1 to 0
    notes = Column(Text)
    created_at = Column(String, default=_now_iso)

    __table_args__ = (
        Index("ix_competition_player", "player_id"),
        Index("ix_competition_team_season", "team", "season"),
    )


class WrReceptionPerception(Base):
    """Reception Perception film-graded WR metrics (Matt Harmon).

    Charted from 8-game film samples per season. Covers route win rates,
    coverage-type splits, alignment, contested catch, and YAC profile.
    WR-only table — joins to players via player_id + season.
    """

    __tablename__ = "wr_reception_perception"

    rp_id = Column(String, primary_key=True)  # player_id + season
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False)
    season = Column(Integer, nullable=False)
    is_prospect = Column(Integer, default=0)  # 1 = draft prospect (college stats)

    # Coverage success rates (0-100 scale)
    routes_charted = Column(Integer)
    success_rate_man = Column(Float)
    success_rate_zone = Column(Float)
    success_rate_press = Column(Float)
    success_rate_double = Column(Float)
    pct_man = Column(Float)
    pct_zone = Column(Float)
    pct_press = Column(Float)
    pct_doubled = Column(Float)

    # Route tree distribution (% of routes, 0-100)
    pct_screen = Column(Float)
    pct_slant = Column(Float)
    pct_curl = Column(Float)
    pct_dig = Column(Float)
    pct_post = Column(Float)
    pct_nine = Column(Float)
    pct_corner = Column(Float)
    pct_out = Column(Float)
    pct_comeback = Column(Float)
    pct_flat = Column(Float)

    # Alignment (% of snaps, 0-100)
    pct_outside = Column(Float)
    pct_slot = Column(Float)
    pct_inline = Column(Float)
    pct_backfield = Column(Float)

    # Target efficiency
    route_target_rate = Column(Float)
    route_catch_rate = Column(Float)
    catch_rate_rp = Column(Float)
    drop_rate_rp = Column(Float)

    # Contested catch
    contested_target_rate_rp = Column(Float)
    contested_catch_rate_rp = Column(Float)

    # Tackle breaking / YAC
    tackle_break_opportunities = Column(Integer)
    first_contact_drop_pct = Column(Float)
    one_broken_tackle_pct = Column(Float)
    two_plus_broken_tackle_pct = Column(Float)

    # Route-level success rates (best routes)
    success_rate_slant = Column(Float)
    success_rate_curl = Column(Float)
    success_rate_dig = Column(Float)
    success_rate_post = Column(Float)
    success_rate_nine = Column(Float)
    success_rate_corner = Column(Float)
    success_rate_out = Column(Float)
    success_rate_screen = Column(Float)

    created_at = Column(String, default=_now_iso)

    __table_args__ = (
        Index("ix_rp_player", "player_id"),
        Index("ix_rp_season", "season"),
        UniqueConstraint("player_id", "season", name="uq_rp_player_season"),
    )


# ---------------------------------------------------------------------------
# Phase 2 & 3 Hooks (schema defined now, populated later)
# ---------------------------------------------------------------------------


class PlayerWeek(Base):
    """Weekly observation layer. Phase 2 — schema defined, not populated."""

    __tablename__ = "player_week"

    week_id = Column(String, primary_key=True)  # player_id + season + week
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False)
    season = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    team = Column(String)
    opponent = Column(String)
    game_id = Column(String)
    snap_share_week = Column(Float)
    target_share_week = Column(Float)
    air_yards_share_week = Column(Float)
    rz_target_share_week = Column(Float)
    carries_week = Column(Integer)
    routes_run_week = Column(Integer)
    fantasy_pts_ppr_week = Column(Float)
    fantasy_pts_std_week = Column(Float)
    opponent_cb1_name = Column(String)
    shadow_covered_flag = Column(Integer, default=0)
    game_script = Column(String)  # POSITIVE, NEGATIVE, NEUTRAL
    team_implied_total = Column(Float)
    matchup_adjustment = Column(Float)
    created_at = Column(String, default=_now_iso)

    __table_args__ = (
        Index("ix_player_week_player", "player_id"),
        Index("ix_player_week_season_week", "season", "week"),
        UniqueConstraint("player_id", "season", "week", name="uq_player_week"),
    )


class QualitativeSignal(Base):
    """Expert qualitative signals. Phase 3 — schema defined, manual insert in Phase 1."""

    __tablename__ = "qualitative_signals"

    signal_id = Column(String, primary_key=True)  # UUID
    scope_type = Column(String, nullable=False)  # PLAYER or TEAM_SCHEME
    player_id = Column(String, ForeignKey("players.player_id"))
    team = Column(String, nullable=False)
    season = Column(Integer, nullable=False)
    week_applicable = Column(Integer)
    signal_type = Column(String, nullable=False)
    signal_direction = Column(String)  # POSITIVE, NEGATIVE, NEUTRAL
    signal_summary = Column(Text, nullable=False)
    raw_excerpt = Column(Text)
    source_name = Column(String)
    source_episode = Column(String)
    source_url = Column(String)
    source_timestamp = Column(String)
    analyst_name = Column(String)
    credibility_tier = Column(Integer)  # 1=core sharp, 2=reliable, 3=supplemental
    confidence_score = Column(Float)
    recency_weight = Column(Float)
    hypothesis_id = Column(String)
    validated_flag = Column(Integer, default=0)
    validation_result = Column(String)  # CONFIRMED, REJECTED, INCONCLUSIVE, PENDING
    created_at = Column(String, default=_now_iso)
    updated_at = Column(String, default=_now_iso, onupdate=_now_iso)

    __table_args__ = (
        Index("ix_signal_player", "player_id"),
        Index("ix_signal_team_season", "team", "season"),
        Index("ix_signal_type", "signal_type"),
    )


