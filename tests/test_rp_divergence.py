"""Tests for the film-vs-market divergence report.

The percentile direction gets the most attention here. A flipped percentile is silent — every
number still looks like a percentile and every row still reads plausibly — and the first
implementation did flip it, putting the best-charted receiver in the 5th percentile. Only the
real data made it obvious, so the direction is pinned explicitly.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fantasy_data.models import Base, Player, PlayerSeasonBaseline, RpQbSeason, RpRbSeason, WrReceptionPerception
from fantasy_data.reports.rp_divergence import (
    _film_score,
    _percentile_ranks,
    _weighted,
    format_rp_divergence,
    get_rp_divergence,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


class TestPercentileDirection:
    def test_higher_value_is_a_higher_percentile(self):
        out = _percentile_ranks({"best": 90.0, "mid": 70.0, "worst": 50.0}, higher_is_better=True)
        assert out["best"] > out["mid"] > out["worst"]
        assert out["best"] > 80 and out["worst"] < 20

    def test_lower_rank_is_a_higher_percentile(self):
        """Positional rank 1 is the best player, so it must map to the TOP percentile."""
        out = _percentile_ranks({"rank1": 1.0, "rank5": 5.0, "rank20": 20.0}, higher_is_better=False)
        assert out["rank1"] > out["rank5"] > out["rank20"]
        assert out["rank1"] > 80 and out["rank20"] < 20

    def test_the_regression_that_shipped_broken(self):
        """A success rate of 80 among {80, 70, 60} is the best, not the worst."""
        out = _percentile_ranks({"a": 80.0, "b": 70.0, "c": 60.0}, higher_is_better=True)
        assert out["a"] == max(out.values())

    def test_ties_share_a_percentile(self):
        out = _percentile_ranks({"a": 70.0, "b": 70.0, "c": 50.0}, higher_is_better=True)
        assert out["a"] == out["b"] > out["c"]

    def test_empty_input(self):
        assert _percentile_ranks({}) == {}


class TestFilmScore:
    def test_weighted_by_the_players_own_usage_mix(self):
        # 60% man at 80, 40% zone at 50 -> 68.0
        assert _weighted([(60.0, 80.0), (40.0, 50.0)]) == pytest.approx(68.0)

    def test_incomplete_pairs_are_skipped(self):
        assert _weighted([(60.0, None), (40.0, 50.0)]) == pytest.approx(50.0)

    def test_no_usable_pair_is_none_not_zero(self):
        assert _weighted([(None, None)]) is None
        assert _weighted([(0.0, 80.0)]) is None  # zero total weight

    def test_wr_uses_coverage_mix(self):
        wr = WrReceptionPerception(
            rp_id="x",
            player_id="p",
            season=2025,
            pct_man=60.0,
            success_rate_man=80.0,
            pct_zone=40.0,
            success_rate_zone=50.0,
        )
        assert _film_score(wr) == pytest.approx(68.0)

    def test_rb_prefers_the_sources_own_overall_rate(self):
        rb = RpRbSeason(rp_rb_id="x", player_id="p", season=2025, overall_success_pct=66.3)
        assert _film_score(rb) == 66.3

    def test_rb_falls_back_to_scheme_mix_when_no_overall(self):
        rb = RpRbSeason(
            rp_rb_id="x",
            player_id="p",
            season=2024,
            man_gap_att_pct=25.0,
            man_gap_success_pct=80.0,
            zone_att_pct=75.0,
            zone_success_pct=60.0,
        )
        assert _film_score(rb) == pytest.approx(65.0)

    def test_qb_uses_depth_mix(self):
        qb = RpQbSeason(
            rp_qb_id="x",
            player_id="p",
            season=2024,
            short_tar_pct=70.0,
            short_sr=80.0,
            intermediate_tar_pct=20.0,
            intermediate_sr=60.0,
            deep_tar_pct=10.0,
            deep_sr=50.0,
        )
        assert _film_score(qb) == pytest.approx(73.0)


def _seed_wrs(db, n=6):
    """n receivers whose film order is the exact REVERSE of their market order."""
    for i in range(n):
        pid = f"WR{i:02d}"
        db.add(Player(player_id=pid, full_name=f"Receiver {i}", position="WR", team="AAA"))
        db.add(
            WrReceptionPerception(
                rp_id=f"{pid}_2025",
                player_id=pid,
                season=2025,
                is_prospect=0,
                pct_man=50.0,
                success_rate_man=60.0 + i,
                pct_zone=50.0,
                success_rate_zone=60.0 + i,
            )
        )
        db.add(
            PlayerSeasonBaseline(
                baseline_id=f"{pid}_2026",
                player_id=pid,
                season=2026,
                sharp_pos_rank=float(i + 1),
                rankings_source_count=4,
            )
        )
    db.commit()


class TestReport:
    def test_reversed_orders_produce_large_gaps_in_both_directions(self, session):
        _seed_wrs(session)
        rows = get_rp_divergence(session, season=2026, threshold=0)
        assert len(rows) == 6
        by_name = {r["player"]: r for r in rows}
        # Receiver 5 charts best and is ranked worst -> film high.
        assert by_name["Receiver 5"]["direction"] == "FILM_HIGH"
        assert by_name["Receiver 5"]["gap"] > 0
        # Receiver 0 charts worst and is ranked best -> film low.
        assert by_name["Receiver 0"]["direction"] == "FILM_LOW"
        assert by_name["Receiver 0"]["gap"] < 0

    def test_reports_the_charted_season_not_the_board_season(self, session):
        _seed_wrs(session)
        rows = get_rp_divergence(session, season=2026, threshold=0)
        assert all(r["charted"] == 2025 for r in rows)

    def test_threshold_filters_small_gaps(self, session):
        _seed_wrs(session)
        assert len(get_rp_divergence(session, season=2026, threshold=0)) == 6
        assert len(get_rp_divergence(session, season=2026, threshold=95)) < 6

    def test_min_sources_drops_thinly_ranked_players(self, session):
        _seed_wrs(session)
        thin = session.get(PlayerSeasonBaseline, "WR00_2026")
        thin.rankings_source_count = 1
        session.commit()
        names = {r["player"] for r in get_rp_divergence(session, season=2026, threshold=0)}
        assert "Receiver 0" not in names
        assert "Receiver 0" in {
            r["player"] for r in get_rp_divergence(session, season=2026, threshold=0, min_sources=0)
        }

    def test_too_few_charted_players_yields_nothing(self, session):
        """Percentiles over 3 players are not worth reporting."""
        _seed_wrs(session, n=3)
        assert get_rp_divergence(session, season=2026, threshold=0) == []

    def test_prospects_are_excluded(self, session):
        _seed_wrs(session)
        for rp in session.query(WrReceptionPerception).all():
            rp.is_prospect = 1
        session.commit()
        assert get_rp_divergence(session, season=2026, threshold=0) == []

    def test_position_filter(self, session):
        _seed_wrs(session)
        assert get_rp_divergence(session, season=2026, threshold=0, position="RB") == []
        assert len(get_rp_divergence(session, season=2026, threshold=0, position="WR")) == 6


class TestFormatting:
    def test_states_the_charted_season_and_the_pool_caveat(self, session):
        _seed_wrs(session)
        rows = get_rp_divergence(session, season=2026, threshold=0)
        out = format_rp_divergence(rows, 2026)
        assert "WR 2025" in out
        assert "CHARTED players only" in out
        assert "never the board season" in out

    def test_empty_result_explains_itself(self):
        assert "No film-vs-market divergence" in format_rp_divergence([], 2026)
