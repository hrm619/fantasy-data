"""Tests for PFF data ingest."""

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.ingest.ingest_pff import ingest_pff_players, ingest_pff_grades


class TestIngestPffPlayers:
    def test_creates_players(self, session, sample_pff_df):
        stats = ingest_pff_players(session, sample_pff_df, 2024, verbose=False)
        assert stats["created"] == 2
        player = session.get(Player, "PFF010")
        assert player.full_name == "Test Player One"
        assert player.position == "WR"
        assert player.team == "DAL"

    def test_updates_existing(self, session, sample_pff_df):
        # Create first
        ingest_pff_players(session, sample_pff_df, 2024, verbose=False)
        # Update with same data
        stats = ingest_pff_players(session, sample_pff_df, 2024, verbose=False)
        assert stats["updated"] == 2

    def test_sets_position_group(self, session, sample_pff_df):
        ingest_pff_players(session, sample_pff_df, 2024, verbose=False)
        wr = session.get(Player, "PFF010")
        rb = session.get(Player, "PFF011")
        assert wr.position_group == "PASS_CATCHER"
        assert rb.position_group == "BACKFIELD"


class TestIngestPffGrades:
    def test_creates_baselines(self, session, sample_pff_df):
        ingest_pff_players(session, sample_pff_df, 2024, verbose=False)
        stats = ingest_pff_grades(session, sample_pff_df, 2024, verbose=False)
        assert stats["created"] == 2

        baseline = session.get(PlayerSeasonBaseline, "PFF010_2024")
        assert baseline.pff_receiving_grade == 85.5
        assert baseline.route_grade_pff == 82.0
        assert baseline.games_played == 17

    def test_rb_gets_rush_grade(self, session, sample_pff_df):
        ingest_pff_players(session, sample_pff_df, 2024, verbose=False)
        ingest_pff_grades(session, sample_pff_df, 2024, verbose=False)

        baseline = session.get(PlayerSeasonBaseline, "PFF011_2024")
        assert baseline.pff_rush_grade == 78.3
        assert baseline.pff_receiving_grade is None
