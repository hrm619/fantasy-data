# fantasy-data

Fantasy football data model, ETL, and edge identification for the [quant-edge](https://github.com/hrm619) platform.

## What This Does

Builds a structured database of fantasy football player valuations across 12 NFL seasons (2014-2025) by combining 8 data sources: expert rankings, PFF grades, nflverse play-by-play, NGS tracking, FTN charting, Reception Perception film study, historical ADP, and coaching continuity data. Trust-weighted baselines account for HC, OC, and QB changes.

The primary output is an **ADP divergence report** — players where sharp expert consensus disagrees with public market ADP, enriched with PFF grades, scheme context, and tracking data to explain *why* the divergence exists.

## Data Model

**2,248 players · 8,536 player-season baselines · 90+ fields per baseline · 12 seasons**

```
                    ┌──────────────────────┐
                    │     8 Data Sources    │
                    └──────────┬───────────┘
                               │
   ┌───────────────┬───────────┼───────────┬──────────────┐
   ▼               ▼           ▼           ▼              ▼
Rankings       nflverse      PFF API    Reception      Coaching
Pipeline      (seasonal,    (grades,   Perception     Staff
(6 experts)    PBP, NGS,    stats,     (film-graded   (HC, OC, QB
               FTN, PFR,    bulk)      WR metrics)    continuity)
               snap counts)
   │               │           │           │              │
   └───────────────┴─────┬─────┴───────────┘              │
                         ▼                                │
              ┌─────────────────────┐                     │
              │   SQLite Database   │◄────────────────────┘
              │                     │
              │  players (2,248)    │
              │  baselines (8,536)  │
              │  coaching (384)     │
              │  reception_perc     │
              │    (117 WR records) │
              └─────────┬──────────┘
                        │
               ┌────────┼────────┐
               ▼        ▼        ▼
           trust     baselines   reports
           weights   (40+ field  + viz
           (HC/OC/   weighted    (7 charts)
            QB decay) averages)
```

## Quick Start

```bash
# Install
cd fantasy-data
uv sync

# Full historical build (automated)
fantasy-data init-db
fantasy-data seed-coaching --file data/coaching_staff_historical.json
fantasy-data seed-coaching --file data/coaching_staff_2024.json
fantasy-data seed-coaching --file data/coaching_staff_2025.json
fantasy-data build-history --start-season 2014 --end-season 2024 --target-season 2025

# Or step by step
fantasy-data ingest historical                                        # box scores 2014-2024
fantasy-data ingest nflverse --start-season 2014 --end-season 2024    # advanced metrics
fantasy-data ingest pff-bulk --dir data-dev/pff-grades                # PFF grades
fantasy-data ingest historical-adp                                    # ADP 2017-2024
fantasy-data ingest rp --dir "data-dev/Reception Perception WR Deep Dive"
fantasy-data ingest rankings --season 2025                            # current season
fantasy-data compute trust-weights --season 2025
fantasy-data compute baselines --season 2025

# Reports
fantasy-data report adp-divergence --season 2025 --plot
fantasy-data report rankings --player-id ChasJa00 --season 2025 --plot
fantasy-data report rankings-variance --season 2025 --plot
fantasy-data report trust-flags --season 2025 --plot
fantasy-data report player --player-id ChasJa00 --season 2025
```

## Trust Weight System

Historical baselines are discounted when a player's production context changes:

| Factor | Multiplier | Rationale |
|--------|-----------|-----------|
| New OC | ×0.40 | Scheme change affects usage, route trees, play design |
| New HC | ×0.65 | Culture/philosophy shift |
| New QB (WR/TE) | ×0.50 | Target distribution, timing, volume all change |
| New QB (RB) | ×0.75 | Less affected than pass catchers |
| Team change | ×0.20 | Entirely new context |
| Injury concern | ×0.55 | Missed time uncertainty |
| Rookie | cap 0.50 | No NFL history |
| Floor | 0.05 | Always some signal |

Multipliers stack multiplicatively. QB changes are auto-detected from baseline data.

## Key Concepts

- **Sharp consensus**: Format-neutral ranking from 4 sharp sources (FantasyPoints, LateRound, Underdog, PFF) using position-first ranking with ADP scarcity curve conversion
- **ADP divergence**: Where sharp consensus disagrees with market ADP by 12+ positions
- **Canonical player ID**: Pipeline's `player_key_dict.json` format (e.g., `McCaCh01`). PFF IDs stored as secondary field. nflverse IDs resolved via pfr_id.
- **No-overwrite ingest**: All modules only set NULL fields, so multiple sources layer safely

## Dependencies

- **[fantasy-pipeline](https://github.com/hrm619/fantasy_data_pipeline)** — multi-source rankings processor
- **nfl_data_py** — nflverse data access (seasonal, PBP, NGS, FTN, PFR, snap counts)
- **SQLAlchemy** — ORM and database management
- **Click** — CLI framework
- **pandas** — data manipulation

## Tests

```bash
uv run pytest tests/ -v --ignore=tests/test_viz.py    # 118 tests
```

## Phase Roadmap

- **Phase 1 (complete)**: Multi-source ingest (8 sources), trust weights with QB continuity, PFF grades, NGS tracking, FTN charting, historical ADP, Reception Perception, baseline computation, ADP divergence reports
- **Phase 2 (next)**: Weekly in-season layer (`player_week` table), target competition analysis
- **Viz rewrite (complete)**: NYT-inspired theme (Inter font, editorial color system), all 7 charts converted to Plotly, Seaborn/Matplotlib removed
- **Phase 3**: Qualitative signal automation from podcast ingestion via research-assistant
- **Calibration**: Year-over-year correlation study to empirically validate trust weight multipliers
