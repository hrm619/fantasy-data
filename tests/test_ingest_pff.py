"""Tests for PFF data ingest — enrichment of existing players."""

import pytest

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.ingest.ingest_pff import ingest_pff
from fantasy_data.ingest.ingest_pff_bulk import _normalize


class TestIngestPff:
    def test_enriches_existing_players(self, session, seed_players, sample_pff_df):
        stats = ingest_pff(session, sample_pff_df, 2024, verbose=False)
        assert stats["enriched"] == 2  # Mahomes and Hill exist in seed

        mahomes = session.get(Player, "MahomPa01")
        assert mahomes.pff_id == "PFF_EXT_001"
        assert mahomes.jersey_number == 15

    def test_sets_grade_fields(self, session, seed_players, sample_pff_df):
        ingest_pff(session, sample_pff_df, 2024, verbose=False)

        baseline = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        assert baseline is not None
        assert baseline.pff_receiving_grade == 85.5
        assert baseline.route_grade_pff == 82.0

    def test_drop_rate_is_rescaled_from_percent_to_proportion(self, session, seed_players):
        # PFF reports drop_rate 0-100; nflverse's PFR feeds the same column a
        # 0-1 proportion. Without rescaling the field means two different
        # things depending on which ingest reached the row first.
        import pandas as pd

        df = pd.DataFrame(
            {
                "player_id": ["PFF_EXT_002"],
                "player": ["Tyreek Hill"],
                "position": ["WR"],
                "team_abbr": ["MIA"],
                "drop_rate": [8.5],
            }
        )
        ingest_pff(session, df, 2024, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        assert baseline.drop_rate == pytest.approx(0.085)

    def test_does_not_write_games_played(self, session, seed_players, sample_pff_df):
        # PFF counts the postseason; games_played means regular-season games and
        # is owned by ingest_historical. Two writers made the column mean
        # whatever ran first.
        ingest_pff(session, sample_pff_df, 2024, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        assert baseline.games_played is None

    def test_unmatched_pff_players(self, session, seed_players):
        """PFF players not in the DB get logged as unmatched."""
        import pandas as pd

        df = pd.DataFrame(
            {
                "player_id": ["PFF_UNKNOWN"],
                "player": ["Unknown PFF Player"],
                "position": ["TE"],
                "team_abbr": ["NE"],
                "games": [10],
            }
        )
        stats = ingest_pff(session, df, 2024, verbose=False)
        assert stats["unmatched"] == 1
        assert stats["enriched"] == 0

    def test_creates_baseline_if_missing(self, session, seed_players, sample_pff_df):
        """PFF ingest creates baseline records if they don't exist yet."""
        # seed_players exists but seed_baselines was not called
        ingest_pff(session, sample_pff_df, 2024, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "MahomPa01_2024")
        assert baseline is not None
        assert baseline.games_started == 17


class TestNormalize:
    def test_rescales_percent_fields(self):
        assert _normalize("drop_rate", 8.5) == pytest.approx(0.085)
        assert _normalize("drop_rate", 100.0) == pytest.approx(1.0)
        assert _normalize("drop_rate", 0.0) == 0.0

    def test_leaves_other_fields_untouched(self):
        # Grades are 0-100 by definition and must not be rescaled.
        assert _normalize("pff_offense_grade", 86.6) == 86.6
        assert _normalize("yards_per_route_run", 1.88) == 1.88
