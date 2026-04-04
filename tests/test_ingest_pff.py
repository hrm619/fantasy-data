"""Tests for PFF data ingest — enrichment of existing players."""

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.ingest.ingest_pff import ingest_pff


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
        assert baseline.games_played == 16

    def test_unmatched_pff_players(self, session, seed_players):
        """PFF players not in the DB get logged as unmatched."""
        import pandas as pd
        df = pd.DataFrame({
            "player_id": ["PFF_UNKNOWN"],
            "player": ["Unknown PFF Player"],
            "position": ["TE"],
            "team_abbr": ["NE"],
            "games": [10],
        })
        stats = ingest_pff(session, df, 2024, verbose=False)
        assert stats["unmatched"] == 1
        assert stats["enriched"] == 0

    def test_creates_baseline_if_missing(self, session, seed_players, sample_pff_df):
        """PFF ingest creates baseline records if they don't exist yet."""
        # seed_players exists but seed_baselines was not called
        ingest_pff(session, sample_pff_df, 2024, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "MahomPa01_2024")
        assert baseline is not None
        assert baseline.games_played == 17
