-- Fantasy Data Platform — Views
-- Depends on tables from create_tables.sql

-- Player season summary: joins players + baseline + competition count
CREATE VIEW IF NOT EXISTS player_season_summary AS
SELECT
    p.player_id,
    p.full_name,
    p.position,
    p.position_group,
    p.team AS current_team,
    b.season,
    b.team AS season_team,
    b.games_played,
    b.data_trust_weight,
    b.snap_share,
    b.target_share,
    b.air_yards_share,
    b.wopr,
    b.yards_per_route_run,
    b.catch_rate_over_expected,
    b.adp_consensus,
    b.adp_positional_rank,
    b.sharp_consensus_rank,
    b.adp_divergence_rank,
    b.adp_divergence_flag,
    b.rankings_avg_positional,
    b.rankings_source_count,
    b.fantasy_pts_ppr,
    b.fpts_per_game_ppr,
    b.projection_uncertain_flag,
    (SELECT COUNT(*) FROM target_competition tc
     WHERE tc.player_id = p.player_id AND tc.season = b.season
       AND tc.competition_type = 'DIRECT') AS direct_competitors
FROM players p
JOIN player_season_baseline b ON p.player_id = b.player_id;


-- ADP divergence report: players where sharp consensus disagrees with ADP
CREATE VIEW IF NOT EXISTS adp_divergence AS
SELECT
    p.player_id,
    p.full_name,
    p.position,
    p.team,
    b.season,
    b.adp_consensus,
    b.adp_positional_rank,
    b.sharp_consensus_rank,
    b.adp_divergence_rank,
    b.rankings_avg_positional,
    b.rankings_source_count,
    b.rankings_fpts_positional,
    b.rankings_hw_positional,
    b.rankings_pff_positional,
    b.rankings_jj_positional,
    b.rankings_ds_positional,
    CASE
        WHEN b.adp_divergence_rank > 0 THEN 'UNDERVALUED'
        WHEN b.adp_divergence_rank < 0 THEN 'OVERVALUED'
        ELSE 'FAIR'
    END AS divergence_direction
FROM players p
JOIN player_season_baseline b ON p.player_id = b.player_id
WHERE b.adp_divergence_flag = 1
ORDER BY ABS(b.adp_divergence_rank) DESC;
