"""SQLAlchemy ORM models for the fantasy football data platform.

Seven core tables organized into three logical layers:
- Identity & Continuity: players, coaching_staff
- Role Signal (Baseline): player_season_baseline, target_competition
- Observation & Signal: player_week (Phase 2), qualitative_signals (Phase 3)
Plus: pipeline_id_map (bridge table for rankings pipeline integration)

Columns use SQLAlchemy 2.0 typed declarations (`Mapped[...]` + `mapped_column`):
non-optional annotations map to NOT NULL, `T | None` maps to nullable columns —
matching the legacy `Column(..., nullable=...)` schema exactly while giving the
type checker real attribute types.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Float,
    Integer,
    String,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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

    player_id: Mapped[str] = mapped_column(String, primary_key=True)  # Pipeline PLAYER ID (e.g., McCaCh01)
    pff_id: Mapped[str | None] = mapped_column(String)  # PFF player ID (secondary, for grade joins)
    gsis_id: Mapped[str | None] = mapped_column(String)
    sleeper_id: Mapped[str | None] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[str] = mapped_column(String, nullable=False)  # QB, RB, WR, TE, K
    position_group: Mapped[str | None] = mapped_column(String)  # PASS_CATCHER, BACKFIELD, QB
    route_tree_type: Mapped[str | None] = mapped_column(String)  # SLOT, OUTSIDE, FLEX, INLINE_TE, MOVE_TE
    team: Mapped[str | None] = mapped_column(String)
    jersey_number: Mapped[int | None] = mapped_column(Integer)
    age: Mapped[float | None] = mapped_column(Float)
    years_pro: Mapped[int | None] = mapped_column(Integer)
    draft_year: Mapped[int | None] = mapped_column(Integer)
    draft_round: Mapped[int | None] = mapped_column(Integer)
    draft_pick: Mapped[int | None] = mapped_column(Integer)
    college: Mapped[str | None] = mapped_column(String)
    height_inches: Mapped[int | None] = mapped_column(Integer)
    weight_lbs: Mapped[int | None] = mapped_column(Integer)
    forty_time: Mapped[float | None] = mapped_column(Float)
    athleticism_score: Mapped[float | None] = mapped_column(Float)
    speed_score: Mapped[float | None] = mapped_column(Float)
    team_change_flag: Mapped[int | None] = mapped_column(Integer, default=0)
    prev_team: Mapped[str | None] = mapped_column(String)
    contract_year_flag: Mapped[int | None] = mapped_column(Integer, default=0)
    injury_concern_flag: Mapped[int | None] = mapped_column(Integer, default=0)
    rookie_flag: Mapped[int | None] = mapped_column(Integer, default=0)
    is_active: Mapped[int | None] = mapped_column(Integer, default=1)
    created_at: Mapped[str | None] = mapped_column(String, default=_now_iso)
    updated_at: Mapped[str | None] = mapped_column(String, default=_now_iso, onupdate=_now_iso)

    baselines: Mapped[list["PlayerSeasonBaseline"]] = relationship(back_populates="player")

    __table_args__ = (
        Index("ix_players_team", "team"),
        Index("ix_players_position", "position"),
        Index("ix_players_name", "full_name"),
    )


class CoachingStaff(Base):
    """Offensive coaching continuity by team and season."""

    __tablename__ = "coaching_staff"

    staff_id: Mapped[str] = mapped_column(String, primary_key=True)  # team + season composite
    team: Mapped[str] = mapped_column(String, nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    head_coach: Mapped[str] = mapped_column(String, nullable=False)
    offensive_coordinator: Mapped[str | None] = mapped_column(String)
    # Who actually calls the offensive plays — often the HC rather than the OC.
    # This, not the OC title, is what oc_continuity_flag tracks when known;
    # NULL means unverified, and the flag falls back to the OC name.
    play_caller: Mapped[str | None] = mapped_column(String)
    quarterbacks_coach: Mapped[str | None] = mapped_column(String)
    hc_year_with_team: Mapped[int | None] = mapped_column(Integer)
    oc_year_with_team: Mapped[int | None] = mapped_column(Integer)
    hc_continuity_flag: Mapped[int | None] = mapped_column(Integer, default=0)
    oc_continuity_flag: Mapped[int | None] = mapped_column(Integer, default=0)
    starting_qb: Mapped[str | None] = mapped_column(String)  # Starting QB name (for audit/display)
    qb_continuity_flag: Mapped[int | None] = mapped_column(Integer, default=1)  # 0 = new starter vs prior season
    system_tag: Mapped[str | None] = mapped_column(String)  # MCVAY_TREE, SHANAHAN_ZONE, REID_WEST_COAST, etc.
    pass_rate_tendency: Mapped[float | None] = mapped_column(Float)
    te_usage_tendency: Mapped[float | None] = mapped_column(Float)
    rb_pass_usage_tendency: Mapped[float | None] = mapped_column(Float)
    tempo: Mapped[str | None] = mapped_column(String)  # FAST, MEDIUM, SLOW
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(String, default=_now_iso)
    updated_at: Mapped[str | None] = mapped_column(String, default=_now_iso, onupdate=_now_iso)

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

    baseline_id: Mapped[str] = mapped_column(String, primary_key=True)  # player_id + season composite
    player_id: Mapped[str] = mapped_column(String, ForeignKey("players.player_id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    team: Mapped[str | None] = mapped_column(String)
    games_played: Mapped[int | None] = mapped_column(Integer)
    games_started: Mapped[int | None] = mapped_column(Integer)
    data_trust_weight: Mapped[float | None] = mapped_column(Float)  # 0-1, computed from coaching joins
    hc_continuity: Mapped[int | None] = mapped_column(Integer)
    oc_continuity: Mapped[int | None] = mapped_column(Integer)
    seasons_in_system: Mapped[int | None] = mapped_column(Integer)

    # --- Opportunity Volume ---
    snap_share: Mapped[float | None] = mapped_column(Float)
    route_participation_rate: Mapped[float | None] = mapped_column(Float)
    target_share: Mapped[float | None] = mapped_column(Float)
    rz_target_share: Mapped[float | None] = mapped_column(Float)
    ez_target_share: Mapped[float | None] = mapped_column(Float)
    carries_per_game: Mapped[float | None] = mapped_column(Float)
    rz_carry_share: Mapped[float | None] = mapped_column(Float)
    total_touches_per_game: Mapped[float | None] = mapped_column(Float)

    # --- Opportunity Quality ---
    air_yards_share: Mapped[float | None] = mapped_column(Float)
    avg_depth_of_target: Mapped[float | None] = mapped_column(Float)
    avg_cushion: Mapped[float | None] = mapped_column(Float)
    avg_separation: Mapped[float | None] = mapped_column(Float)
    target_quality_rating: Mapped[float | None] = mapped_column(Float)
    route_grade_pff: Mapped[float | None] = mapped_column(Float)
    contested_target_rate: Mapped[float | None] = mapped_column(Float)

    # --- Efficiency & Conversion ---
    racr: Mapped[float | None] = mapped_column(Float)
    catch_rate: Mapped[float | None] = mapped_column(Float)
    expected_catch_rate: Mapped[float | None] = mapped_column(Float)
    catch_rate_over_expected: Mapped[float | None] = mapped_column(Float)
    yards_per_route_run: Mapped[float | None] = mapped_column(Float)
    yards_after_catch_per_rec: Mapped[float | None] = mapped_column(Float)
    broken_tackle_rate: Mapped[float | None] = mapped_column(Float)
    drop_rate: Mapped[float | None] = mapped_column(Float)
    pff_offense_grade: Mapped[float | None] = mapped_column(Float)
    pff_receiving_grade: Mapped[float | None] = mapped_column(Float)
    pff_pass_block_grade: Mapped[float | None] = mapped_column(Float)
    pff_run_blocking_grade: Mapped[float | None] = mapped_column(Float)
    pff_passing_grade: Mapped[float | None] = mapped_column(Float)  # QB only

    # --- Composite Demand ---
    wopr: Mapped[float | None] = mapped_column(Float)  # (1.5 * target_share) + (0.7 * air_yards_share)
    dominator_rating: Mapped[float | None] = mapped_column(Float)
    market_share_score: Mapped[float | None] = mapped_column(Float)

    # --- Backfield-Specific (RB) ---
    rb_role: Mapped[str | None] = mapped_column(String)  # WORKHORSE, COMMITTEE, PASS_DOWN, CHANGE_OF_PACE
    early_down_share: Mapped[float | None] = mapped_column(Float)
    third_down_carry_share: Mapped[float | None] = mapped_column(Float)
    third_down_target_share: Mapped[float | None] = mapped_column(Float)
    goal_line_carry_share: Mapped[float | None] = mapped_column(Float)
    pff_rush_grade: Mapped[float | None] = mapped_column(Float)
    yards_per_carry: Mapped[float | None] = mapped_column(Float)
    expected_yards_per_carry: Mapped[float | None] = mapped_column(Float)
    rush_yards_over_expected: Mapped[float | None] = mapped_column(Float)
    avg_box_count: Mapped[float | None] = mapped_column(Float)

    # --- Market Calibration ---
    adp_consensus: Mapped[float | None] = mapped_column(Float)
    adp_underdog: Mapped[float | None] = mapped_column(Float)
    adp_positional_rank: Mapped[int | None] = mapped_column(Integer)
    fp_projected_pts_ppr: Mapped[float | None] = mapped_column(Float)
    fp_projected_pts_std: Mapped[float | None] = mapped_column(Float)
    fp_positional_rank: Mapped[int | None] = mapped_column(Integer)
    sharp_pos_rank: Mapped[float | None] = mapped_column(
        Float
    )  # within-position sharp consensus (mean of 4 sharp POS RANKs)
    sharp_consensus_rank: Mapped[float | None] = mapped_column(
        Float
    )  # format-neutral overall rank (via ADP scarcity curve)
    adp_divergence_pos: Mapped[float | None] = mapped_column(Float)  # positional: adp_pos_rank - sharp_pos_rank
    adp_divergence_rank: Mapped[int | None] = mapped_column(Integer)  # overall: ADP rank - sharp_consensus_rank
    adp_divergence_flag: Mapped[int | None] = mapped_column(Integer, default=0)  # abs(adp_divergence_pos) >= 12
    projection_uncertain_flag: Mapped[int | None] = mapped_column(Integer, default=0)

    # --- Per-Source Rankings (from rankings pipeline) ---
    rankings_avg_overall: Mapped[float | None] = mapped_column(Float)
    rankings_avg_positional: Mapped[float | None] = mapped_column(Float)  # mean of ALL sources
    rankings_hw_positional: Mapped[int | None] = mapped_column(Integer)
    rankings_pff_positional: Mapped[int | None] = mapped_column(Integer)
    rankings_ds_positional: Mapped[int | None] = mapped_column(Integer)
    rankings_jj_positional: Mapped[int | None] = mapped_column(Integer)
    rankings_fpts_positional: Mapped[int | None] = mapped_column(Integer)
    rankings_source_count: Mapped[int | None] = mapped_column(Integer)
    ecr_adp_delta: Mapped[float | None] = mapped_column(Float)
    ecr_avg_rank_delta: Mapped[float | None] = mapped_column(Float)
    rankings_last_updated: Mapped[str | None] = mapped_column(String)

    # --- FTN Scheme Context (charting data, 2022+) ---
    play_action_target_pct: Mapped[float | None] = mapped_column(Float)  # % of targets on play-action
    screen_target_pct: Mapped[float | None] = mapped_column(Float)  # % of targets on screen passes
    contested_ball_pct: Mapped[float | None] = mapped_column(Float)  # % of targets that were contested (FTN)
    catchable_ball_pct: Mapped[float | None] = mapped_column(Float)  # % of targets that were catchable
    created_reception_pct: Mapped[float | None] = mapped_column(Float)  # % of catches WR-created (not schemed)
    true_drop_rate: Mapped[float | None] = mapped_column(Float)  # drops / catchable balls (FTN-charted)

    # --- Scoring & Fantasy Output ---
    fantasy_pts_ppr: Mapped[float | None] = mapped_column(Float)
    fantasy_pts_std: Mapped[float | None] = mapped_column(Float)
    fantasy_pts_half: Mapped[float | None] = mapped_column(Float)
    fpts_per_game_ppr: Mapped[float | None] = mapped_column(Float)
    fpts_per_game_std: Mapped[float | None] = mapped_column(Float)
    td_rate: Mapped[float | None] = mapped_column(Float)
    consistency_score: Mapped[float | None] = mapped_column(Float)
    boom_rate: Mapped[float | None] = mapped_column(Float)
    bust_rate: Mapped[float | None] = mapped_column(Float)

    player: Mapped["Player"] = relationship(back_populates="baselines")

    __table_args__ = (
        Index("ix_baseline_player", "player_id"),
        Index("ix_baseline_season", "season"),
        Index("ix_baseline_team", "team"),
        UniqueConstraint("player_id", "season", name="uq_baseline_player_season"),
    )


class TargetCompetition(Base):
    """Intra-team competition for targets and carries at route-tree level."""

    __tablename__ = "target_competition"

    competition_id: Mapped[str] = mapped_column(String, primary_key=True)  # player + season + competitor
    player_id: Mapped[str] = mapped_column(String, ForeignKey("players.player_id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    team: Mapped[str] = mapped_column(String, nullable=False)
    competitor_player_id: Mapped[str | None] = mapped_column(String, ForeignKey("players.player_id"))
    competitor_name: Mapped[str | None] = mapped_column(String)
    competitor_position: Mapped[str | None] = mapped_column(String)
    competitor_route_type: Mapped[str | None] = mapped_column(String)
    route_overlap_score: Mapped[float | None] = mapped_column(Float)  # 0-1
    competition_type: Mapped[str | None] = mapped_column(String)  # DIRECT, VOLUME, NONE
    competition_source: Mapped[str | None] = mapped_column(String)  # DRAFT, FREE_AGENT, TRADE, RETURNING
    competitor_draft_round: Mapped[int | None] = mapped_column(Integer)
    expected_role_impact: Mapped[float | None] = mapped_column(Float)  # -1 to 0
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(String, default=_now_iso)

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

    rp_id: Mapped[str] = mapped_column(String, primary_key=True)  # player_id + season
    player_id: Mapped[str] = mapped_column(String, ForeignKey("players.player_id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    is_prospect: Mapped[int | None] = mapped_column(Integer, default=0)  # 1 = draft prospect (college stats)

    # Coverage success rates (0-100 scale)
    routes_charted: Mapped[int | None] = mapped_column(Integer)
    success_rate_man: Mapped[float | None] = mapped_column(Float)
    success_rate_zone: Mapped[float | None] = mapped_column(Float)
    success_rate_press: Mapped[float | None] = mapped_column(Float)
    success_rate_double: Mapped[float | None] = mapped_column(Float)
    pct_man: Mapped[float | None] = mapped_column(Float)
    pct_zone: Mapped[float | None] = mapped_column(Float)
    pct_press: Mapped[float | None] = mapped_column(Float)
    pct_doubled: Mapped[float | None] = mapped_column(Float)

    # Route tree distribution (% of routes, 0-100)
    pct_screen: Mapped[float | None] = mapped_column(Float)
    pct_slant: Mapped[float | None] = mapped_column(Float)
    pct_curl: Mapped[float | None] = mapped_column(Float)
    pct_dig: Mapped[float | None] = mapped_column(Float)
    pct_post: Mapped[float | None] = mapped_column(Float)
    pct_nine: Mapped[float | None] = mapped_column(Float)
    pct_corner: Mapped[float | None] = mapped_column(Float)
    pct_out: Mapped[float | None] = mapped_column(Float)
    pct_comeback: Mapped[float | None] = mapped_column(Float)
    pct_flat: Mapped[float | None] = mapped_column(Float)

    # Alignment (% of snaps, 0-100)
    pct_outside: Mapped[float | None] = mapped_column(Float)
    pct_slot: Mapped[float | None] = mapped_column(Float)
    pct_inline: Mapped[float | None] = mapped_column(Float)
    pct_backfield: Mapped[float | None] = mapped_column(Float)

    # Target efficiency
    route_target_rate: Mapped[float | None] = mapped_column(Float)
    route_catch_rate: Mapped[float | None] = mapped_column(Float)
    catch_rate_rp: Mapped[float | None] = mapped_column(Float)
    drop_rate_rp: Mapped[float | None] = mapped_column(Float)

    # Contested catch
    contested_target_rate_rp: Mapped[float | None] = mapped_column(Float)
    contested_catch_rate_rp: Mapped[float | None] = mapped_column(Float)

    # Tackle breaking / YAC
    tackle_break_opportunities: Mapped[int | None] = mapped_column(Integer)
    first_contact_drop_pct: Mapped[float | None] = mapped_column(Float)
    one_broken_tackle_pct: Mapped[float | None] = mapped_column(Float)
    two_plus_broken_tackle_pct: Mapped[float | None] = mapped_column(Float)

    # Route-level success rates (best routes)
    success_rate_slant: Mapped[float | None] = mapped_column(Float)
    success_rate_curl: Mapped[float | None] = mapped_column(Float)
    success_rate_dig: Mapped[float | None] = mapped_column(Float)
    success_rate_post: Mapped[float | None] = mapped_column(Float)
    success_rate_nine: Mapped[float | None] = mapped_column(Float)
    success_rate_corner: Mapped[float | None] = mapped_column(Float)
    success_rate_out: Mapped[float | None] = mapped_column(Float)
    success_rate_screen: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[str | None] = mapped_column(String, default=_now_iso)

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

    week_id: Mapped[str] = mapped_column(String, primary_key=True)  # player_id + season + week
    player_id: Mapped[str] = mapped_column(String, ForeignKey("players.player_id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    team: Mapped[str | None] = mapped_column(String)
    opponent: Mapped[str | None] = mapped_column(String)
    game_id: Mapped[str | None] = mapped_column(String)
    snap_share_week: Mapped[float | None] = mapped_column(Float)
    target_share_week: Mapped[float | None] = mapped_column(Float)
    air_yards_share_week: Mapped[float | None] = mapped_column(Float)
    rz_target_share_week: Mapped[float | None] = mapped_column(Float)
    carries_week: Mapped[int | None] = mapped_column(Integer)
    routes_run_week: Mapped[int | None] = mapped_column(Integer)
    fantasy_pts_ppr_week: Mapped[float | None] = mapped_column(Float)
    fantasy_pts_std_week: Mapped[float | None] = mapped_column(Float)
    opponent_cb1_name: Mapped[str | None] = mapped_column(String)
    shadow_covered_flag: Mapped[int | None] = mapped_column(Integer, default=0)
    game_script: Mapped[str | None] = mapped_column(String)  # POSITIVE, NEGATIVE, NEUTRAL
    team_implied_total: Mapped[float | None] = mapped_column(Float)
    matchup_adjustment: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[str | None] = mapped_column(String, default=_now_iso)

    __table_args__ = (
        Index("ix_player_week_player", "player_id"),
        Index("ix_player_week_season_week", "season", "week"),
        UniqueConstraint("player_id", "season", "week", name="uq_player_week"),
    )


class QualitativeSignal(Base):
    """Expert qualitative signals. Phase 3 — schema defined, manual insert in Phase 1."""

    __tablename__ = "qualitative_signals"

    signal_id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID
    scope_type: Mapped[str] = mapped_column(String, nullable=False)  # PLAYER or TEAM_SCHEME
    player_id: Mapped[str | None] = mapped_column(String, ForeignKey("players.player_id"))
    team: Mapped[str] = mapped_column(String, nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week_applicable: Mapped[int | None] = mapped_column(Integer)
    signal_type: Mapped[str] = mapped_column(String, nullable=False)
    signal_direction: Mapped[str | None] = mapped_column(String)  # POSITIVE, NEGATIVE, NEUTRAL
    signal_summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw_excerpt: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String)
    source_episode: Mapped[str | None] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String)
    source_timestamp: Mapped[str | None] = mapped_column(String)
    analyst_name: Mapped[str | None] = mapped_column(String)
    credibility_tier: Mapped[int | None] = mapped_column(Integer)  # 1=core sharp, 2=reliable, 3=supplemental
    confidence_score: Mapped[float | None] = mapped_column(Float)
    recency_weight: Mapped[float | None] = mapped_column(Float)
    hypothesis_id: Mapped[str | None] = mapped_column(String)
    validated_flag: Mapped[int | None] = mapped_column(Integer, default=0)
    validation_result: Mapped[str | None] = mapped_column(String)  # CONFIRMED, REJECTED, INCONCLUSIVE, PENDING
    created_at: Mapped[str | None] = mapped_column(String, default=_now_iso)
    updated_at: Mapped[str | None] = mapped_column(String, default=_now_iso, onupdate=_now_iso)

    __table_args__ = (
        Index("ix_signal_player", "player_id"),
        Index("ix_signal_team_season", "team", "season"),
        Index("ix_signal_type", "signal_type"),
    )
