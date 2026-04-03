# fantasy-data

Fantasy football data model, ETL, and edge identification for the [quant-edge](https://github.com/hrm619) platform.

## What This Does

Builds a structured database of fantasy football player valuations by combining multiple expert ranking sources with PFF grades, coaching continuity data, and trust-weighted historical baselines. The primary output is an **ADP divergence report** — players where a sharp consensus (equal-weighted mean of FantasyPoints, LateRound, Underdog, PFF positional ranks) disagrees with public consensus ADP by 12+ positions.

## Architecture

```
External Sources                    fantasy_data_pipeline
(PFF CSV, FantasyPros,             (RankingsProcessor)
 FantasyPoints, LateRound,               │
 Underdog, DraftShark)                    │ return_dataframe=True
       │                                 ▼
       │ manual CSV              ┌──────────────────┐
       ▼                         │ ingest_rankings   │
┌──────────────┐                 │ • column mapping  │
│ ingest_pff   │                 │ • sharp consensus │
│ • players    │                 │ • ADP divergence  │
│ • PFF grades │                 └────────┬─────────┘
└──────┬───────┘                          │
       │        ┌─────────────────────────┘
       ▼        ▼
  ┌─────────────────────────────────┐
  │         SQLite Database         │
  │  players │ coaching_staff       │
  │  player_season_baseline         │
  │  target_competition (Phase 2)   │
  │  player_week (Phase 2)          │
  │  qualitative_signals (Phase 3)  │
  └─────────────┬───────────────────┘
                │
       ┌────────┼────────┐
       ▼        ▼        ▼
   compute   compute   compute
   trust     baselines  competition
   weights              (Phase 2)
       │        │
       ▼        ▼
    ┌─────────────────┐
    │     Reports     │
    │ adp-divergence  │
    │ rankings        │
    │ rankings-var    │
    │ player profile  │
    │ trust-flags     │
    └─────────────────┘
```

## Quick Start

```bash
# Install
cd fantasy-data
uv sync

# Initialize database
fantasy-data init-db

# Seed coaching staff (32 teams, 2024 season)
fantasy-data seed-coaching --file data/coaching_staff_2024.json

# Ingest PFF data (seeds players table — must run before rankings)
fantasy-data ingest pff --file <pff-export.csv> --season 2024

# Ingest rankings from fantasy_data_pipeline
fantasy-data ingest rankings --league-type redraft --season 2025

# Compute trust weights
fantasy-data compute trust-weights --season 2025

# Generate reports
fantasy-data report adp-divergence --season 2025 --position WR
fantasy-data report rankings --player-id <pff-id> --season 2025
fantasy-data report rankings-variance --season 2025 --min-sources 3
fantasy-data report player --player-id <pff-id> --season 2025
fantasy-data report trust-flags --season 2025

# Check data freshness
fantasy-data rankings-status --season 2025
```

## Dependencies

- **[fantasy-pipeline](https://github.com/hrm619/fantasy_data_pipeline)** — multi-source rankings processor (installed as editable local dependency)
- **SQLAlchemy** — ORM and database management
- **Click** — CLI framework
- **pandas** — data manipulation

## Data Flow

1. **PFF ingest** seeds the `players` table with canonical PFF IDs and populates grade fields in `player_season_baseline`
2. **Rankings ingest** calls `RankingsProcessor(return_dataframe=True)`, maps output columns to baseline schema, computes `sharp_consensus_rank` from 4 sharp sources, and computes `adp_divergence_rank`
3. **Trust weight computation** joins player flags with `coaching_staff` continuity data to produce `data_trust_weight` per player-season
4. **Baseline computation** produces trust-weighted multi-season averages for role signal metrics
5. **Reports** surface ADP divergences, cross-source disagreements, and projection-uncertain players

## Key Concepts

- **Sharp consensus rank**: Equal-weighted mean of 4 sharp source positional ranks (FantasyPoints, LateRound, Underdog, PFF). Distinct from `rankings_avg_positional` which includes all sources.
- **ADP divergence**: `adp_positional_rank - sharp_consensus_rank`. Positive = market undervalues. Flagged at |12|+ positions.
- **Trust weight**: Decays with OC change (×0.40), HC change (×0.65), team change (×0.20), injury (×0.55), rookie (cap 0.50). Floor at 0.05.
- **Pipeline ID bridge**: Maps `fantasy_data_pipeline` PLAYER IDs (e.g., `MahomPa01`) to PFF player IDs via name matching.

## Tests

```bash
uv run pytest tests/ -v    # 54 tests
```

## Phase Roadmap

- **Phase 1 (current)**: Schema, PFF ingest, rankings ingest, trust weights, ADP divergence reports
- **Phase 1b**: Research-assistant fantasy football domain module (non-blocking)
- **Phase 2**: Automated source fetching, target competition, weekly in-season layer
- **Phase 3**: Qualitative signal automation from podcast ingestion
