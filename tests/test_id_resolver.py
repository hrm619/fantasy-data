"""Tests for ID resolver — gsis_id to pipeline PLAYER ID mapping."""

import pandas as pd
import pytest

from fantasy_data.ingest.id_resolver import (
    build_id_map_from_nflverse,
    _generate_fallback_id,
    ensure_player_exists,
)
from fantasy_data.models import Player


class TestGenerateFallbackId:
    def test_basic_name(self):
        result = _generate_fallback_id("John Smith", set())
        assert result == "SmitJo00"

    def test_collision_increments(self):
        existing = {"SmitJo00"}
        result = _generate_fallback_id("John Smith", existing)
        assert result == "SmitJo01"

    def test_short_name(self):
        result = _generate_fallback_id("Al Bo", set())
        assert result == "BoxxAl00"

    def test_single_name(self):
        result = _generate_fallback_id("Madonna", set())
        assert result == "MadoXx00"


class TestBuildIdMapFromNflverse:
    def test_uses_pfr_id_as_primary(self):
        ids_df = pd.DataFrame({
            "gsis_id": ["00-001", "00-002"],
            "pfr_id": ["SmitJo00", "JoneAa00"],
            "name": ["John Smith", "Aaron Jones"],
            "merge_name": [None, None],
            "position": ["WR", "RB"],
            "team": ["KC", "GB"],
        })
        id_map = build_id_map_from_nflverse(ids_df, name_to_key={})
        assert id_map["00-001"] == "SmitJo00"
        assert id_map["00-002"] == "JoneAa00"

    def test_falls_back_to_name_matching(self):
        ids_df = pd.DataFrame({
            "gsis_id": ["00-003"],
            "pfr_id": [None],
            "name": ["Patrick Mahomes"],
            "merge_name": [None],
            "position": ["QB"],
            "team": ["KC"],
        })
        name_to_key = {"patrick mahomes": "MahomPa01"}
        id_map = build_id_map_from_nflverse(ids_df, name_to_key=name_to_key)
        assert id_map["00-003"] == "MahomPa01"

    def test_generates_fallback_for_unknown(self):
        ids_df = pd.DataFrame({
            "gsis_id": ["00-999"],
            "pfr_id": [None],
            "name": ["Unknown Player"],
            "merge_name": [None],
            "position": ["WR"],
            "team": ["NYG"],
        })
        id_map = build_id_map_from_nflverse(ids_df, name_to_key={})
        assert id_map["00-999"] == "PlayUn00"

    def test_skips_null_gsis_id(self):
        ids_df = pd.DataFrame({
            "gsis_id": [None, "00-001"],
            "pfr_id": ["Test00", "Real00"],
            "name": ["Ghost", "Real"],
            "merge_name": [None, None],
            "position": ["WR", "WR"],
            "team": ["KC", "KC"],
        })
        id_map = build_id_map_from_nflverse(ids_df, name_to_key={})
        assert len(id_map) == 1
        assert "00-001" in id_map


class TestEnsurePlayerExists:
    def test_creates_new_player(self, session):
        player = ensure_player_exists(
            session, "TestPl01", "Test Player", "WR", "KC", gsis_id="00-001"
        )
        assert player.player_id == "TestPl01"
        assert player.gsis_id == "00-001"
        assert player.is_active == 0

    def test_returns_existing_player(self, session, seed_players):
        player = ensure_player_exists(
            session, "MahomPa01", "Patrick Mahomes", "QB", "KC", gsis_id="00-999"
        )
        assert player.full_name == "Patrick Mahomes"
        assert player.gsis_id == "00-999"

    def test_does_not_overwrite_existing_gsis(self, session, seed_players):
        # Set gsis_id first
        mahomes = session.get(Player, "MahomPa01")
        mahomes.gsis_id = "00-111"
        session.commit()

        player = ensure_player_exists(
            session, "MahomPa01", "Patrick Mahomes", "QB", "KC", gsis_id="00-999"
        )
        assert player.gsis_id == "00-111"  # Not overwritten
