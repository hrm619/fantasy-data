"""Tests for ORM models and database schema."""

import pytest
from sqlalchemy.exc import IntegrityError

from fantasy_data.models import (
    Player, CoachingStaff, PlayerSeasonBaseline, TargetCompetition,
    PlayerWeek, QualitativeSignal, PipelineIdMap, UnmatchedPlayer,
)


class TestPlayerModel:
    def test_create_player(self, session):
        p = Player(player_id="PFF999", full_name="Test Player", position="WR", team="DAL")
        session.add(p)
        session.commit()
        assert session.get(Player, "PFF999").full_name == "Test Player"

    def test_player_requires_name(self, session):
        p = Player(player_id="PFF998", full_name=None, position="QB")
        session.add(p)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_player_requires_position(self, session):
        session.rollback()
        p = Player(player_id="PFF997", full_name="Test", position=None)
        session.add(p)
        with pytest.raises(IntegrityError):
            session.commit()


class TestCoachingStaff:
    def test_create_staff(self, session):
        s = CoachingStaff(
            staff_id="DAL_2024", team="DAL", season=2024,
            head_coach="Mike McCarthy",
        )
        session.add(s)
        session.commit()
        assert session.get(CoachingStaff, "DAL_2024").head_coach == "Mike McCarthy"

    def test_unique_team_season(self, session):
        s1 = CoachingStaff(staff_id="SF_2024", team="SF", season=2024, head_coach="Shanahan")
        s2 = CoachingStaff(staff_id="SF_2024_dup", team="SF", season=2024, head_coach="Other")
        session.add(s1)
        session.commit()
        session.add(s2)
        with pytest.raises(IntegrityError):
            session.commit()


class TestPlayerSeasonBaseline:
    def test_create_baseline(self, session, seed_players):
        b = PlayerSeasonBaseline(
            baseline_id="PFF001_2025", player_id="PFF001",
            season=2025, team="KC",
        )
        session.add(b)
        session.commit()
        assert session.get(PlayerSeasonBaseline, "PFF001_2025").season == 2025

    def test_fk_constraint(self, session):
        b = PlayerSeasonBaseline(
            baseline_id="FAKE_2025", player_id="NONEXISTENT",
            season=2025,
        )
        session.add(b)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_baseline_relationship(self, session, seed_players):
        b = PlayerSeasonBaseline(
            baseline_id="PFF001_2025", player_id="PFF001",
            season=2025, team="KC",
        )
        session.add(b)
        session.commit()
        player = session.get(Player, "PFF001")
        assert len(player.baselines) == 1


class TestPipelineIdMap:
    def test_create_mapping(self, session, seed_players):
        m = PipelineIdMap(
            pipeline_player_id="MahomPa01", player_id="PFF001",
            match_method="exact", match_confidence=1.0,
        )
        session.add(m)
        session.commit()
        assert session.get(PipelineIdMap, "MahomPa01").player_id == "PFF001"


class TestAllTablesCreated:
    def test_table_count(self, engine):
        from fantasy_data.models import Base
        assert len(Base.metadata.tables) == 8
