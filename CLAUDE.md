# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **fantasy-data** — the fantasy football data model, ETL, and edge identification system for the quant-edge platform. It builds structured player valuations from multiple expert ranking sources, PFF grades, and coaching continuity data. The primary analytical output is ADP divergence — where a sharp consensus disagrees with public market ADP.

**Package Name**: `fantasy-data` — installed as `fantasy_data` Python package
**Dependency**: `fantasy-pipeline` (hrm619/fantasy_data_pipeline) — multi-source rankings processor, installed as editable local dependency

## Requirements

- **Python**: 3.13+
- **Package Manager**: `uv`
- **Database**: SQLite (via SQLAlchemy ORM)
- **Key Dependencies**: sqlalchemy, click, pandas, tabulate, fantasy-pipeline

## Commands

```bash
# Install
uv sync

# Install with dev tools (pytest, ruff, mypy)
uv sync --extra dev

# Run tests
uv run pytest tests/ -v

# Run single test
uv run pytest tests/test_compute.py::TestComputeTrustWeight -v

# CLI help
fantasy-data --help
fantasy-data ingest --help
fantasy-data compute --help
fantasy-data report --help
```

## Architecture

### Package Structure

```
src/fantasy_data/
├── __init__.py
├── db.py                          # Engine, session factory, init_db()
├── models.py                      # 6 SQLAlchemy ORM models (all tables)
├── standardize.py                 # Team, player name, coach name normalization
├── cli.py                         # Click CLI entry point
├── ingest/
│   ├── ingest_rankings.py         # RankingsProcessor wrapper + sharp consensus + player creation
│   ├── ingest_pff.py              # PFF CSV → enriches existing players with grades
│   └── ingest_ngs.py              # NGS CSV → baseline opportunity quality (stub)
├── compute/
│   ├── compute_trust_weights.py   # data_trust_weight from coaching continuity
│   ├── compute_baselines.py       # Multi-season trust-weighted averaging
│   └── compute_competition.py     # Route overlap scoring (Phase 2)
├── reports/
│   ├── adp_divergence.py          # Players where sharp ≠ ADP
│   ├── rankings.py                # Per-source breakdown for one player
│   ├── rankings_variance.py       # Cross-source disagreement (high std dev)
│   ├── player_profile.py          # Full player profile
│   └── trust_flags.py             # Projection-uncertain players
└── viz/
    ├── theme.py                   # Shared color palette and Plotly/Seaborn theming
    ├── adp_divergence.py          # ADP divergence bar chart
    ├── correlation_heatmap.py     # Role signal correlation matrix
    ├── opportunity_dist.py        # Opportunity distributions + sharp vs ADP scatter
    ├── player_profile.py          # Per-player source breakdown radar
    ├── rankings_variance.py       # Cross-source variance plots
    └── trust_overview.py          # Trust weight distribution
```

### Database Tables (models.py)

| Table | Purpose |
|-------|---------|
| `players` | Master identity — pipeline PLAYER ID is canonical PK (e.g., McCaCh01) |
| `coaching_staff` | HC/OC continuity by team+season — drives trust decay |
| `player_season_baseline` | Core table — 60+ fields: role signals, PFF grades, rankings, ADP, fantasy output |
| `target_competition` | Intra-team route tree competition (Phase 2) |
| `player_week` | Weekly observation layer (Phase 2) |
| `qualitative_signals` | Expert qualitative signals (Phase 3) |

### Key Design Decisions

- **Pipeline PLAYER ID is canonical**: All tables FK to `players.player_id` which uses the pipeline's `player_key_dict.json` format (e.g., `McCaCh01`). PFF IDs are stored as a secondary field (`Player.pff_id`) for grade joins.
- **Sharp consensus ≠ average rank**: `sharp_consensus_rank` = mean of 4 sharp sources (fpts, jj, hw, pff). `rankings_avg_positional` = mean of ALL sources including non-sharp (ds). These are distinct fields.
- **Trust weight formula** (Section 6.3 of PRD): Multiplicative decay — OC change ×0.40, HC change ×0.65, team change ×0.20, injury ×0.55, rookie cap 0.50, floor 0.05.
- **Rankings ingest seeds the players table**: Rankings ingest creates Player records directly using the pipeline's PLAYER ID. PFF ingest is supplemental — it enriches existing players with grades by name matching.
- **`return_dataframe=True`**: Rankings ingest calls `RankingsProcessor.process_rankings(return_dataframe=True)` to get a DataFrame directly, avoiding CSV round-trip.

### Data Ingest Order

```
1. fantasy-data init-db
2. fantasy-data seed-coaching --file data/coaching_staff_2024.json
3. fantasy-data ingest rankings --season <year>               # seeds players table
4. fantasy-data ingest pff --file <csv> --season <year>       # enriches existing players (optional)
5. fantasy-data compute trust-weights --season <year>
6. fantasy-data compute baselines --season <year>
7. fantasy-data report adp-divergence --season <year>
```

### Rankings Column Mapping

Pipeline output → baseline field (see `ingest_rankings.py:COLUMN_MAP`):

| Pipeline Column | Baseline Field |
|----------------|----------------|
| `avg_RK` | `rankings_avg_overall` |
| `avg_POS RANK` | `rankings_avg_positional` |
| `fpts_POS RANK` | `rankings_fpts_positional` |
| `hw_POS RANK` | `rankings_hw_positional` |
| `pff_POS RANK` | `rankings_pff_positional` |
| `jj_POS RANK` | `rankings_jj_positional` |
| `ds_POS RANK` | `rankings_ds_positional` |
| `fp_POS RANK` | `fp_positional_rank` |
| `ADP` | `adp_consensus` |
| `POS ADP` | `adp_positional_rank` |
| `ECR ADP Delta` | `ecr_adp_delta` |
| `ECR Delta` | `ecr_avg_rank_delta` |

### Computed Fields

- `sharp_consensus_rank` = mean(fpts, jj, hw, pff positional ranks) — 4 sharp sources only
- `adp_divergence_rank` = `adp_positional_rank` - `sharp_consensus_rank`
- `adp_divergence_flag` = 1 when |divergence| >= 12
- `wopr` = (1.5 × target_share) + (0.7 × air_yards_share)
- `projection_uncertain_flag` = 1 when `data_trust_weight` < 0.7

## Testing

86 tests across 7 files, all using in-memory SQLite:

- `test_models.py` — ORM models, FK constraints, unique constraints, pff_id field
- `test_ingest_rankings.py` — Direct player creation, sharp consensus, divergence flags, team standardization
- `test_ingest_pff.py` — Name-match enrichment of existing players, grade population
- `test_compute.py` — Trust weight formula (8 cases), weighted baselines, route overlap
- `test_reports.py` — ADP divergence filtering, rankings breakdown, variance sorting, trust flags
- `test_standardize.py` — Team abbreviation variants (32 canonical + variants), player name normalization, coach names
- `test_viz.py` — Theme application, chart return types for all 7 plot functions

## Integration with quant-edge

This repo is part of the quant-edge platform. See `/Users/henrymarsh/Documents/quant-edge/CLAUDE.md` for system-wide context.

- **PRD**: `Fantasy_Football_Domain_PRD.md` in quant-edge root
- **Dependency**: `fantasy-pipeline` at `../fantasy_data_pipeline` (editable local install)
- **Future**: Phase 3 wires research-assistant podcast signals into `qualitative_signals` table

## Common Gotchas

- **Package name mismatch**: The dependency is `fantasy-pipeline` (PyPI name) but imports as `fantasy_pipeline` (Python). The `uv.lock` resolves it from the local path `../fantasy_data_pipeline`.
- **Rankings ingest is step 1**: Rankings ingest creates Player records directly. PFF ingest is optional supplemental enrichment — it matches by name against existing players.
- **Team standardization**: All team abbreviations are normalized via `standardize.py`. Common variants like `JAC→JAX`, `LA→LAR`, `OAK→LV` are handled automatically.
- **Coaching staff seed data**: `data/coaching_staff_2024.json` contains all 32 teams. System tags (SHANAHAN_ZONE, REID_WEST_COAST, etc.) are manually assigned.
- **DB location**: Defaults to `fantasy_data.db` in the repo root. Override with `FANTASY_DATA_DB` env var.
