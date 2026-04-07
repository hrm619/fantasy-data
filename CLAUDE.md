# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **fantasy-data** — the fantasy football data model, ETL, and edge identification system for the quant-edge platform. It builds structured player valuations from 8 data sources across 12 NFL seasons (2014-2025), producing trust-weighted baselines and ADP divergence analysis. The primary analytical output is where sharp expert consensus disagrees with public market ADP.

**Package Name**: `fantasy-data` — installed as `fantasy_data` Python package
**Dependency**: `fantasy-pipeline` (hrm619/fantasy_data_pipeline) — multi-source rankings processor, installed as editable local dependency

## Requirements

- **Python**: 3.13+
- **Package Manager**: `uv`
- **Database**: SQLite (via SQLAlchemy ORM)
- **Key Dependencies**: sqlalchemy, click, pandas, nfl_data_py, tabulate, fantasy-pipeline

## Commands

```bash
# Install
uv sync

# Install with dev tools (pytest, ruff, mypy)
uv sync --extra dev

# Run tests (exclude viz unless plotly/scipy installed)
uv run pytest tests/ -v --ignore=tests/test_viz.py

# Run viz tests (requires viz extra)
uv sync --extra viz && uv run pytest tests/test_viz.py -v

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
├── db.py                              # Engine, session factory, init_db()
├── models.py                          # 8 SQLAlchemy ORM models
├── standardize.py                     # Team, player name, coach name normalization
├── cli.py                             # Click CLI entry point
├── ingest/
│   ├── ingest_rankings.py             # RankingsProcessor wrapper + sharp consensus
│   ├── ingest_historical.py           # Pipeline combined_data.csv → box scores (2014-2024)
│   ├── ingest_nflverse.py             # nflverse: seasonal, weekly, snap, PBP, PFR, NGS, FTN
│   ├── ingest_pff.py                  # PFF CSV → grades enrichment (single file)
│   ├── ingest_pff_bulk.py             # PFF per-season CSVs → bulk grade ingest (2014-2025)
│   ├── ingest_reception_perception.py # RP film-graded WR metrics (7 CSV types)
│   ├── ingest_historical_adp.py       # Fantasy Football Calculator API → historical ADP
│   ├── ingest_ngs.py                  # NGS CSV → baseline (legacy stub)
│   └── id_resolver.py                 # nflverse gsis_id → pipeline PLAYER ID bridge
├── compute/
│   ├── compute_trust_weights.py       # Trust decay + QB continuity detection
│   ├── compute_baselines.py           # Multi-season trust-weighted averaging (40+ fields)
│   └── compute_competition.py         # Route overlap scoring (Phase 2)
├── reports/
│   ├── adp_divergence.py              # Players where sharp ≠ ADP
│   ├── rankings.py                    # Per-source breakdown for one player
│   ├── rankings_variance.py           # Cross-source disagreement (high std dev)
│   ├── player_profile.py              # Full player profile
│   └── trust_flags.py                 # Projection-uncertain players
└── viz/
    ├── theme.py                       # NYT-inspired theme: COLORS, FONTS, LAYOUT, apply_theme(), color_for_mode()
    ├── fonts/Inter/                   # Bundled Inter variable font + OFL license
    ├── adp_divergence.py              # ADP divergence bar chart (Plotly, diverging colors)
    ├── correlation_heatmap.py         # Role signal correlation matrix (Plotly heatmap)
    ├── opportunity_dist.py            # Opportunity KDE distributions + sharp vs ADP scatter (Plotly)
    ├── player_profile.py              # Per-player source breakdown (Plotly, spotlight mode)
    ├── rankings_variance.py           # Cross-source variance scatter (Plotly, categorical colors)
    └── trust_overview.py              # Trust weight distribution (Plotly horizontal bar)

scripts/
├── build_coaching_history.py          # Generate coaching_staff_historical.json with QBs
└── convert_pff_json.py                # Convert PFF API JSON → CSV for ingest
```

### Database Tables (models.py)

| Table | Purpose | Scale |
|-------|---------|-------|
| `players` | Master identity — pipeline PLAYER ID is canonical PK | 2,248 players |
| `coaching_staff` | HC/OC/QB continuity by team+season | 384 records (32 × 12) |
| `player_season_baseline` | Core table — 90+ fields: role signals, PFF grades, NGS tracking, FTN charting, rankings, ADP, fantasy output | 8,536 records |
| `wr_reception_perception` | Film-graded WR metrics from Reception Perception | 117 records |
| `target_competition` | Intra-team route tree competition (Phase 2) | Empty |
| `player_week` | Weekly observation layer (Phase 2) | Empty |
| `qualitative_signals` | Expert qualitative signals (Phase 3) | Empty |

### Data Sources (8 active)

| Source | Seasons | Key Fields |
|--------|---------|-----------|
| Rankings pipeline (6 experts) | 2025 | Sharp consensus, ADP, per-source positional ranks |
| Pipeline combined_data.csv | 2014-2024 | Box scores, fantasy points (STD/PPR/half) |
| nflverse seasonal + weekly | 2014-2024 | Target share, air yards share, boom/bust, consistency |
| nflverse snap counts | 2014-2024 | Snap share |
| nflverse PBP | 2014-2024 | RZ/EZ target shares, down splits, goal-line carries |
| nflverse PFR advanced | 2018-2024 | Drop rate, broken tackle rate |
| nflverse NGS tracking | 2016-2024 | avg_cushion, avg_separation, expected YPC, RYOE |
| nflverse FTN charting | 2022-2024 | Play-action %, screen %, true drop rate, contested/catchable ball % |
| PFF grades (API capture) | 2014-2025 | Route grade, rush grade, offense grade, pass block, receiving grade, YPRR |
| PFF stats (API capture) | 2014-2025 | Contested catch rate, drop rate, route participation |
| Reception Perception | 2023-2025 | Coverage success rates, route tree, alignment, contested catch |
| Historical ADP (FFC API) | 2017-2024 | Pre-season ADP consensus |
| Coaching staff (manual + script) | 2014-2025 | HC, OC, starting QB, continuity flags, system tags |

### Key Design Decisions

- **Pipeline PLAYER ID is canonical**: All tables FK to `players.player_id` using `player_key_dict.json` format (e.g., `McCaCh01`). PFF IDs stored as secondary field. nflverse gsis_id resolved via pfr_id from IDs table (7,500+ direct mappings).
- **Sharp consensus ≠ average rank**: `sharp_consensus_rank` uses format-neutral position-first ranking with ADP scarcity curve conversion. `rankings_avg_positional` = mean of ALL sources.
- **Trust weight formula**: Multiplicative decay — OC change ×0.40, HC change ×0.65, **QB change ×0.50 (WR/TE) or ×0.75 (RB)**, team change ×0.20, injury ×0.55, rookie cap 0.50, floor 0.05. QB changes auto-detected from baseline data.
- **No-overwrite rule**: All ingest modules only set fields that are currently NULL. Running multiple ingests in sequence safely layers data without destroying prior values.
- **Baselines are trust-weighted averages**: `compute baselines` pulls 3 prior seasons and weights each by its `data_trust_weight`. 40+ fields are aggregated.

### Data Ingest Order (Full Build)

```
Phase 1: Schema & Seeds
  fantasy-data init-db
  fantasy-data seed-coaching --file data/coaching_staff_historical.json
  fantasy-data seed-coaching --file data/coaching_staff_2024.json
  fantasy-data seed-coaching --file data/coaching_staff_2025.json

Phase 2: Historical Data (2014-2024)
  fantasy-data ingest historical                                    # box scores
  fantasy-data ingest nflverse --start-season 2014 --end-season 2024  # advanced metrics + PBP + NGS + FTN
  fantasy-data ingest pff-bulk --dir data-dev/pff-grades              # PFF grades 2014-2025
  fantasy-data ingest historical-adp                                  # ADP 2017-2024
  fantasy-data ingest rp --dir "data-dev/Reception Perception WR Deep Dive"

Phase 3: Current Season (2025)
  fantasy-data ingest rankings --season 2025
  fantasy-data ingest pff --file data/pff_grades_2025.csv --season 2025

Phase 4: Compute
  for year in $(seq 2014 2025); do fantasy-data compute trust-weights --season $year; done
  fantasy-data compute baselines --season 2025 --lookback 3

Phase 5: Reports
  fantasy-data report adp-divergence --season 2025 --plot
  fantasy-data report trust-flags --season 2025 --plot
```

Or use `fantasy-data build-history` for an automated Phase 2-4 sequence.

## Testing

118 tests across 10 files, all using in-memory SQLite:

- `test_models.py` — ORM models, FK constraints, unique constraints
- `test_ingest_rankings.py` — Sharp consensus, scarcity curves, divergence flags
- `test_ingest_pff.py` — Name-match enrichment, grade population
- `test_ingest_historical.py` — Box score mapping, derived fields, no-overwrite
- `test_ingest_nflverse.py` — Aggregation functions (seasonal, weekly, snaps, PBP)
- `test_id_resolver.py` — gsis_id resolution, fallback ID generation
- `test_compute.py` — Trust weight formula (14 cases incl. QB continuity), baselines, route overlap
- `test_reports.py` — ADP divergence filtering, rankings breakdown, variance, trust flags
- `test_standardize.py` — Team abbreviations, player names, coach names
- `test_viz.py` — NYT theme API (apply_theme, color_for_mode, annotate_point), all 7 chart modules return `go.Figure` (requires `--extra viz`)

## Integration with quant-edge

This repo is part of the quant-edge platform. See `/Users/henrymarsh/Documents/quant-edge/CLAUDE.md` for system-wide context.

- **PRD**: `Fantasy_Football_Domain_PRD.md` in quant-edge root
- **Dependency**: `fantasy-pipeline` at `../fantasy_data_pipeline` (editable local install)
- **Future**: Phase 3 wires research-assistant podcast signals into `qualitative_signals` table

## Common Gotchas

- **Package name mismatch**: The dependency is `fantasy-pipeline` (PyPI name) but imports as `fantasy_pipeline` (Python). The `uv.lock` resolves it from the local path `../fantasy_data_pipeline`.
- **PFF uses "HB" not "RB"**: The `ingest_pff.py` position group map handles this. PFF API JSON also uses different field names than CSV exports — `convert_pff_json.py` handles the translation.
- **nflverse NGS starts at 2016, FTN at 2022, PFR at 2018**: Each nflverse sub-source has different season availability. The ingest filters automatically.
- **FTN requires PBP**: FTN charting data must be joined with PBP for player IDs. Don't use `--skip-pbp` if you want FTN data.
- **Historical ADP uses Fantasy Football Calculator API**: Free, no auth needed. Returns PPR ADP for 12-team leagues. URL: `fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year=YYYY`
- **PFF data captured via browser network tab**: No API or CSV export. Capture JSON from PFF's internal API, then run `scripts/convert_pff_json.py` to produce CSV for ingest.
- **Reception Perception file naming**: Pro WRs use `WR {Type} - 2023.csv` or `WR {Type} 2024-25.csv`. Draft prospects use `{Type} - 2025 Draft Prospects.csv`. The ingest handles both patterns.
- **Coaching staff validated across all boundaries**: The 2023→2024→2025 continuity flags were cross-checked for consistency. Run `scripts/build_coaching_history.py` to regenerate historical coaching data.
- **DB location**: Defaults to `fantasy_data.db` in the repo root. Override with `FANTASY_DATA_DB` env var.
