"""CLI entry point for fantasy-data platform."""

import click

from fantasy_data.db import get_session, init_db


@click.group()
def cli():
    """Fantasy football data platform — quant-edge."""
    pass


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


@cli.command("init-db")
def cmd_init_db():
    """Initialize the database (create all tables)."""
    init_db()
    click.echo("Database initialized.")


@cli.command("seed-coaching")
@click.option("--file", "file_path", required=True, help="Path to coaching staff JSON.")
def cmd_seed_coaching(file_path):
    """Seed coaching_staff table from JSON file."""
    import json
    from fantasy_data.models import CoachingStaff

    with open(file_path) as f:
        data = json.load(f)

    session = get_session()
    try:
        for entry in data:
            staff_id = f"{entry['team']}_{entry['season']}"
            staff = session.get(CoachingStaff, staff_id)
            if not staff:
                staff = CoachingStaff(staff_id=staff_id)
                session.add(staff)
            for key, val in entry.items():
                setattr(staff, key, val)
        session.commit()
        click.echo(f"Seeded {len(data)} coaching staff records.")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


@cli.group("ingest")
def ingest_group():
    """Ingest data from external sources."""
    pass


@ingest_group.command("rankings")
@click.option("--league-type", default="redraft",
              type=click.Choice(["redraft", "bestball"]),
              help="Rankings league type.")
@click.option("--season", required=True, type=int, help="NFL season year.")
@click.option("--data-path", default=None, help="Path to rankings data directory.")
def cmd_ingest_rankings(league_type, season, data_path):
    """Run rankings pipeline and ingest into player_season_baseline."""
    from fantasy_data.ingest.ingest_rankings import run_rankings_pipeline

    session = get_session()
    try:
        stats = run_rankings_pipeline(session, season, league_type, data_path)
        click.echo(f"Done: {stats}")
    finally:
        session.close()


@ingest_group.command("pff")
@click.option("--file", "file_path", required=True, help="Path to PFF CSV export.")
@click.option("--season", required=True, type=int, help="NFL season year.")
def cmd_ingest_pff(file_path, season):
    """Ingest PFF data into players + player_season_baseline."""
    import pandas as pd
    from fantasy_data.ingest.ingest_pff import ingest_pff_players, ingest_pff_grades

    df = pd.read_csv(file_path)
    session = get_session()
    try:
        ingest_pff_players(session, df, season)
        ingest_pff_grades(session, df, season)
    finally:
        session.close()


@ingest_group.command("ngs")
@click.option("--file", "file_path", required=True, help="Path to NGS CSV export.")
@click.option("--season", required=True, type=int, help="NFL season year.")
def cmd_ingest_ngs(file_path, season):
    """Ingest Next Gen Stats into player_season_baseline."""
    import pandas as pd
    from fantasy_data.ingest.ingest_ngs import ingest_ngs

    df = pd.read_csv(file_path)
    session = get_session()
    try:
        ingest_ngs(session, df, season)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------


@cli.group("compute")
def compute_group():
    """Run compute pipelines."""
    pass


@compute_group.command("trust-weights")
@click.option("--season", required=True, type=int)
def cmd_compute_trust(season):
    """Compute data_trust_weight for all player-season baselines."""
    from fantasy_data.compute.compute_trust_weights import compute_all_trust_weights

    session = get_session()
    try:
        compute_all_trust_weights(session, season)
    finally:
        session.close()


@compute_group.command("baselines")
@click.option("--season", required=True, type=int)
@click.option("--lookback", default=3, type=int, help="Number of prior seasons to consider.")
def cmd_compute_baselines(season, lookback):
    """Compute trust-weighted multi-season baselines."""
    from fantasy_data.compute.compute_baselines import compute_all_baselines

    session = get_session()
    try:
        compute_all_baselines(session, season, lookback)
    finally:
        session.close()


@compute_group.command("competition")
@click.option("--season", required=True, type=int)
@click.option("--team", default=None, help="Team abbreviation (all teams if omitted).")
def cmd_compute_competition(season, team):
    """Compute target competition analysis."""
    from fantasy_data.compute.compute_competition import compute_team_competition
    from fantasy_data.models import CoachingStaff

    session = get_session()
    try:
        if team:
            compute_team_competition(session, team.upper(), season)
        else:
            teams = [r.team for r in
                     session.query(CoachingStaff.team)
                     .filter(CoachingStaff.season == season)
                     .distinct().all()]
            for t in teams:
                compute_team_competition(session, t, season)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@cli.group("report")
def report_group():
    """Generate reports."""
    pass


@report_group.command("adp-divergence")
@click.option("--season", required=True, type=int)
@click.option("--position", default=None, help="Filter by position (QB, RB, WR, TE, all).")
@click.option("--threshold", default=12, type=int, help="Minimum divergence to display.")
def cmd_report_divergence(season, position, threshold):
    """Show players where sharp consensus disagrees with ADP."""
    from fantasy_data.reports.adp_divergence import print_adp_divergence

    session = get_session()
    try:
        print_adp_divergence(session, season, position, threshold)
    finally:
        session.close()


@report_group.command("rankings")
@click.option("--player-id", required=True, help="PFF player ID.")
@click.option("--season", required=True, type=int)
def cmd_report_rankings(player_id, season):
    """Show per-source positional rank breakdown for a player."""
    from fantasy_data.reports.rankings import print_player_rankings

    session = get_session()
    try:
        print_player_rankings(session, player_id, season)
    finally:
        session.close()


@report_group.command("rankings-variance")
@click.option("--season", required=True, type=int)
@click.option("--position", default=None, help="Filter by position.")
@click.option("--min-sources", default=3, type=int, help="Minimum sources required.")
def cmd_report_variance(season, position, min_sources):
    """Show players with highest cross-source ranking disagreement."""
    from fantasy_data.reports.rankings_variance import print_rankings_variance

    session = get_session()
    try:
        print_rankings_variance(session, season, position, min_sources)
    finally:
        session.close()


@report_group.command("player")
@click.option("--player-id", required=True, help="PFF player ID.")
@click.option("--season", required=True, type=int)
def cmd_report_player(player_id, season):
    """Show full player profile: role signals, rankings, signals."""
    from fantasy_data.reports.player_profile import print_player_profile

    session = get_session()
    try:
        print_player_profile(session, player_id, season)
    finally:
        session.close()


@report_group.command("trust-flags")
@click.option("--season", required=True, type=int)
@click.option("--position", default=None, help="Filter by position.")
def cmd_report_trust(season, position):
    """Show players with uncertain projections."""
    from fantasy_data.reports.trust_flags import print_trust_flags

    session = get_session()
    try:
        print_trust_flags(session, season, position)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Rankings Status
# ---------------------------------------------------------------------------


@cli.command("rankings-status")
@click.option("--season", required=True, type=int)
def cmd_rankings_status(season):
    """Check staleness of ranking source data."""
    from fantasy_data.models import PlayerSeasonBaseline

    session = get_session()
    try:
        baseline = (
            session.query(PlayerSeasonBaseline)
            .filter(PlayerSeasonBaseline.season == season)
            .first()
        )
        if not baseline or not baseline.rankings_last_updated:
            click.echo(f"No rankings data found for {season} season.")
            return

        click.echo(f"Rankings last updated: {baseline.rankings_last_updated}")

        count = (
            session.query(PlayerSeasonBaseline)
            .filter(
                PlayerSeasonBaseline.season == season,
                PlayerSeasonBaseline.rankings_source_count.isnot(None),
            )
            .count()
        )
        click.echo(f"Players with rankings data: {count}")

        low_source = (
            session.query(PlayerSeasonBaseline)
            .filter(
                PlayerSeasonBaseline.season == season,
                PlayerSeasonBaseline.rankings_source_count < 3,
                PlayerSeasonBaseline.rankings_source_count.isnot(None),
            )
            .count()
        )
        if low_source:
            click.echo(f"Players with < 3 sources: {low_source} (low confidence)")

    finally:
        session.close()
