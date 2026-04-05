"""Shared test fixtures — in-memory SQLite database."""

import pytest
import pandas as pd
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from fantasy_data.models import (
    Base, Player, CoachingStaff, PlayerSeasonBaseline,
)


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine with all tables."""
    eng = create_engine("sqlite:///:memory:")

    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    """Create a database session for testing."""
    factory = sessionmaker(bind=engine)
    sess = factory()
    yield sess
    sess.close()


@pytest.fixture
def seed_players(session):
    """Seed the players table with pipeline-style PLAYER IDs."""
    players = [
        Player(
            player_id="MahomPa01", full_name="Patrick Mahomes",
            position="QB", team="KC", age=28.5, years_pro=7,
            draft_year=2017, draft_round=1, draft_pick=10,
            rookie_flag=0, team_change_flag=0, injury_concern_flag=0,
        ),
        Player(
            player_id="HillTy01", full_name="Tyreek Hill",
            position="WR", team="MIA", age=30.0, years_pro=8,
            draft_year=2016, draft_round=5, draft_pick=165,
            rookie_flag=0, team_change_flag=0, injury_concern_flag=0,
        ),
        Player(
            player_id="ChasJa01", full_name="Ja'Marr Chase",
            position="WR", team="CIN", age=24.0, years_pro=3,
            draft_year=2021, draft_round=1, draft_pick=5,
            rookie_flag=0, team_change_flag=0, injury_concern_flag=0,
        ),
        Player(
            player_id="RobiBi01", full_name="Bijan Robinson",
            position="RB", team="ATL", age=22.0, years_pro=2,
            draft_year=2023, draft_round=1, draft_pick=8,
            rookie_flag=0, team_change_flag=0, injury_concern_flag=0,
        ),
        Player(
            player_id="WillCa01", full_name="Caleb Williams",
            position="QB", team="CHI", age=22.0, years_pro=1,
            draft_year=2024, draft_round=1, draft_pick=1,
            rookie_flag=1, team_change_flag=1, injury_concern_flag=0,
        ),
    ]
    session.add_all(players)
    session.commit()
    return players


@pytest.fixture
def seed_coaching(session):
    """Seed coaching_staff with test data."""
    staff = [
        CoachingStaff(
            staff_id="KC_2024", team="KC", season=2024,
            head_coach="Andy Reid", offensive_coordinator="Matt Nagy",
            hc_continuity_flag=1, oc_continuity_flag=0,
            qb_continuity_flag=1,
            hc_year_with_team=12, oc_year_with_team=1,
            system_tag="REID_WEST_COAST",
        ),
        CoachingStaff(
            staff_id="MIA_2024", team="MIA", season=2024,
            head_coach="Mike McDaniel", offensive_coordinator="Frank Smith",
            hc_continuity_flag=1, oc_continuity_flag=1,
            qb_continuity_flag=1,
            hc_year_with_team=3, oc_year_with_team=3,
            system_tag="SHANAHAN_ZONE",
        ),
        CoachingStaff(
            staff_id="CIN_2024", team="CIN", season=2024,
            head_coach="Zac Taylor", offensive_coordinator="Brian Callahan",
            hc_continuity_flag=1, oc_continuity_flag=0,
            qb_continuity_flag=1,
            hc_year_with_team=6, oc_year_with_team=1,
            system_tag="MCVAY_TREE",
        ),
        CoachingStaff(
            staff_id="ATL_2024", team="ATL", season=2024,
            head_coach="Raheem Morris", offensive_coordinator="Zac Robinson",
            hc_continuity_flag=1, oc_continuity_flag=1,
            qb_continuity_flag=1,
            hc_year_with_team=2, oc_year_with_team=2,
            system_tag="SHANAHAN_ZONE",
        ),
        CoachingStaff(
            staff_id="CHI_2024", team="CHI", season=2024,
            head_coach="Ben Johnson", offensive_coordinator="Ben Johnson",
            hc_continuity_flag=0, oc_continuity_flag=0,
            qb_continuity_flag=1,
            hc_year_with_team=1, oc_year_with_team=1,
            system_tag="OTHER",
        ),
    ]
    session.add_all(staff)
    session.commit()
    return staff


@pytest.fixture
def seed_baselines(session, seed_players):
    """Seed player_season_baseline with test data."""
    baselines = [
        PlayerSeasonBaseline(
            baseline_id="MahomPa01_2024", player_id="MahomPa01", season=2024,
            team="KC", games_played=17,
            snap_share=0.98, target_share=0.0, air_yards_share=0.0,
            fantasy_pts_ppr=350.0, fpts_per_game_ppr=20.6,
            adp_consensus=2.5, adp_positional_rank=1,
            rankings_fpts_positional=1, rankings_jj_positional=2,
            rankings_hw_positional=1, rankings_pff_positional=2,
            rankings_ds_positional=1, rankings_source_count=5,
        ),
        PlayerSeasonBaseline(
            baseline_id="HillTy01_2024", player_id="HillTy01", season=2024,
            team="MIA", games_played=16,
            snap_share=0.92, target_share=0.28, air_yards_share=0.35,
            fantasy_pts_ppr=280.0, fpts_per_game_ppr=17.5,
            adp_consensus=15.0, adp_positional_rank=5,
            rankings_fpts_positional=3, rankings_jj_positional=4,
            rankings_hw_positional=2, rankings_pff_positional=3,
            rankings_ds_positional=8, rankings_source_count=5,
        ),
        PlayerSeasonBaseline(
            baseline_id="ChasJa01_2024", player_id="ChasJa01", season=2024,
            team="CIN", games_played=17,
            snap_share=0.95, target_share=0.30, air_yards_share=0.38,
            fantasy_pts_ppr=310.0, fpts_per_game_ppr=18.2,
            adp_consensus=8.0, adp_positional_rank=3,
            rankings_fpts_positional=1, rankings_jj_positional=1,
            rankings_hw_positional=1, rankings_pff_positional=2,
            rankings_ds_positional=2, rankings_source_count=5,
        ),
        PlayerSeasonBaseline(
            baseline_id="RobiBi01_2024", player_id="RobiBi01", season=2024,
            team="ATL", games_played=17,
            snap_share=0.82, target_share=0.10, carries_per_game=18.5,
            fantasy_pts_ppr=290.0, fpts_per_game_ppr=17.1,
            adp_consensus=4.0, adp_positional_rank=1,
            rankings_fpts_positional=2, rankings_jj_positional=1,
            rankings_hw_positional=1, rankings_pff_positional=1,
            rankings_ds_positional=3, rankings_source_count=5,
        ),
        PlayerSeasonBaseline(
            baseline_id="WillCa01_2024", player_id="WillCa01", season=2024,
            team="CHI", games_played=17,
            snap_share=0.99,
            adp_consensus=45.0, adp_positional_rank=8,
            rankings_fpts_positional=5, rankings_jj_positional=6,
            rankings_hw_positional=4, rankings_pff_positional=7,
            rankings_ds_positional=10, rankings_source_count=5,
        ),
    ]
    session.add_all(baselines)
    session.commit()
    return baselines


@pytest.fixture
def sample_rankings_df():
    """Sample DataFrame mimicking RankingsProcessor output."""
    return pd.DataFrame({
        "PLAYER NAME": ["Patrick Mahomes", "Tyreek Hill", "New Player"],
        "PLAYER ID": ["MahomPa01", "HillTy01", "NewPPl01"],
        "POS": ["QB", "WR", "RB"],
        "TEAM": ["KC", "MIA", "DAL"],
        "avg_RK": [2.0, 12.0, 50.0],
        "avg_POS RANK": [1.0, 4.0, 25.0],
        "fpts_POS RANK": [1, 3, None],
        "jj_POS RANK": [2, 4, None],
        "hw_POS RANK": [1, 2, None],
        "pff_POS RANK": [2, 3, None],
        "ds_POS RANK": [1, 8, None],
        "ADP": [2.5, 15.0, 80.0],
        "POS ADP": [1, 5, 30],
        "fp_POS RANK": [1, 5, 28],
        "ECR ADP Delta": [-0.5, 3.0, 10.0],
        "ECR Delta": [1.0, -2.0, 5.0],
    })


@pytest.fixture
def sample_pff_df():
    """Sample DataFrame mimicking PFF CSV export — players must already exist."""
    return pd.DataFrame({
        "player_id": ["PFF_EXT_001", "PFF_EXT_002"],
        "player": ["Patrick Mahomes", "Tyreek Hill"],
        "position": ["QB", "WR"],
        "team_abbr": ["KC", "MIA"],
        "jersey_number": [15, 10],
        "age": [28.5, 30.0],
        "years_exp": [7, 8],
        "receiving_grade": [None, 85.5],
        "route_grade": [None, 82.0],
        "rushing_grade": [None, None],
        "games": [17, 16],
        "games_started": [17, 16],
    })
