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

# Install with dev tools (pytest, ruff, ty, pre-commit)
uv sync --extra dev

# Run tests (exclude viz unless plotly/scipy installed)
uv run pytest tests/ -v --ignore=tests/test_viz.py

# Contract tests against the real RP captures (skipped automatically without data-dev/)
uv run pytest -m integration

# Run viz tests (requires viz extra)
uv sync --extra viz && uv run pytest tests/test_viz.py -v

# Run single test
uv run pytest tests/test_compute.py::TestComputeTrustWeight -v

# Lint, format, type-check (Astral tooling — gated in CI, see .github/workflows/ci.yml)
uv run ruff check src/ scripts/ tests/         # lint
uv run ruff format src/ scripts/ tests/        # format (black-compatible drop-in)
uv run ty check src/ scripts/ tests/            # type check (gated in CI)

# Install pre-commit hooks (ruff lint+format + ty run on commit)
uv run pre-commit install

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
│   ├── ingest_reception_perception.py # RP film-graded WR metrics (7 CSV types, 2 naming schemes)
│   ├── rp_parse.py                    # RP filename -> data type/position (pure, no I/O)
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
| `players` | Master identity — pipeline PLAYER ID is canonical PK | 2,344 players |
| `coaching_staff` | HC/OC/play-caller/QB continuity by team+season | 416 records (32 × 13) |
| `player_season_baseline` | Core table — 90+ fields: role signals, PFF grades, NGS tracking, FTN charting, rankings, ADP, fantasy output | 8,334 records (2014-2026) |
| `wr_reception_perception` | Film-graded WR metrics from Reception Perception | 183 records (2023-2025) |
| `target_competition` | Intra-team route tree competition (Phase 2) | Empty |
| `player_week` | Weekly observation layer (Phase 2) | Empty |
| `qualitative_signals` | Expert qualitative signals (Phase 3) | Empty |

### Data Sources (8 active)

| Source | Seasons | Key Fields |
|--------|---------|-----------|
| Rankings pipeline (experts) | 2025-2026 | Sharp consensus, ADP, per-source positional ranks |
| Pipeline combined_data.csv | 2014-2025 | Box scores, fantasy points (STD/PPR/half) |
| nflverse seasonal + weekly | 2014-2025 | Target share, air yards share, racr, dominator, boom/bust, consistency |
| nflverse snap counts | 2014-2025 | Snap share |
| nflverse PBP | 2014-2025 | RZ/EZ target shares, down splits, goal-line carries |
| nflverse PFR advanced | 2018-2025 | Drop rate, broken tackle rate |
| nflverse NGS tracking | 2016-2025 | avg_cushion, avg_separation, expected YPC, RYOE |
| nflverse FTN charting | 2022-2025 | Play-action %, screen %, true drop rate, contested/catchable ball % |
| PFF grades (API capture) | 2014-2025 | Route grade, rush grade, offense grade, pass block, receiving grade, YPRR |
| PFF stats (API capture) | 2014-2025 | Contested catch rate, drop rate, route participation |
| Reception Perception | 2023-2025 | Coverage success rates + attempt counts, route tree, alignment, contested catch, in-space tackle breaking |
| Historical ADP (FFC API) | 2017-2024 | Pre-season ADP consensus |
| Coaching staff (manual + script) | 2014-2025 | HC, OC, starting QB, continuity flags, system tags |

### Key Design Decisions

- **Pipeline PLAYER ID is canonical**: All tables FK to `players.player_id` using `player_key_dict.json` format (e.g., `McCaCh01`). PFF IDs stored as secondary field. nflverse gsis_id resolved via pfr_id from IDs table (7,500+ direct mappings).
- **Sharp consensus ≠ average rank**: `sharp_consensus_rank` uses format-neutral position-first ranking with ADP scarcity curve conversion. `rankings_avg_positional` = mean of ALL sources.
- **Divergence filters thin consensus by default (`--min-sources 3`)**: sharp consensus is a mean of per-source positional ranks, so a player covered by few sources has a noisier mean and lands further from ADP for reasons that are variance, not disagreement. On the 2026 board, 2-source players averaged 30.5 absolute divergence against 5.0 for 4-source players — 6x — which made 5% of the board 45% of the top 20. Sorting by divergence alone surfaces the *least*-supported players as the strongest edges. The report states how many it excluded; `--min-sources 0` (or `min_sources=0` on the MCP tool) opts out.
- **`sharp_consensus_rank` is degenerate at the tail**: the scarcity curve maps positional rank → ADP overall via `np.interp`, which **clamps** rather than extrapolating. 32 of 216 players on the 2026 board have a sharp positional rank beyond the last ADP-ranked player at their position (WR sharp ranks reach 140; the curve ends at WR86), so they collapse onto the boundary — 216 players yield only 155 distinct values, 13 tied at 179.0. This is arguably correct (outside the ADP universe there is no ADP to map to) but it is lossy. The divergence report is unaffected: it ranks on `adp_divergence_pos` and displays `sharp_pos_rank`, both positional.
- **Trust weight formula**: Multiplicative decay — OC change ×0.40, HC change ×0.65, **QB change ×0.50 (WR/TE) or ×0.75 (RB)**, team change ×0.20, injury ×0.55, rookie cap 0.50, floor 0.05. QB changes auto-detected from baseline data.
- **No-overwrite rule**: All ingest modules only set fields that are currently NULL. Running multiple ingests in sequence safely layers data without destroying prior values. **This only yields order-independent results when each field has exactly one writer.** Where two ingests map different source columns to the same field, "don't destroy prior values" quietly becomes "whichever ran first wins" — and the winner is decided by run history, not by which source is authoritative. That produced two real bugs (`games_played`, `drop_rate`), and in both cases the result was not corrupt data but *correct data answering a different question*, which is why it survived review. Before trusting a field's semantics, grep for who writes it; if it's more than one module and they aren't the same source, the meaning is a function of history.
- **Baselines are trust-weighted averages**: `compute baselines` pulls 3 prior seasons and weights each by its `data_trust_weight`. 40+ fields are aggregated.

### Data Ingest Order (Full Build)

```
Phase 1: Schema & Seeds
  fantasy-data init-db
  fantasy-data seed-coaching --file data/coaching_staff_historical.json
  fantasy-data seed-coaching --file data/coaching_staff_2024.json
  fantasy-data seed-coaching --file data/coaching_staff_2025.json
  fantasy-data seed-coaching --file data/coaching_staff_2025_playcallers.json  # play-callers + LV correction
  fantasy-data seed-coaching --file data/coaching_staff_2026.json
  fantasy-data compute coaching-continuity --season 2025   # derive flags; don't trust authored ones
  fantasy-data compute coaching-continuity --season 2026

Phase 2: Historical Data (2014-2025)
  fantasy-data ingest historical                                      # box scores
  fantasy-data ingest nflverse --start-season 2014 --end-season 2025  # advanced metrics + PBP + NGS + FTN
  fantasy-data ingest pff-bulk --dir data-dev/pff-grades              # PFF grades 2014-2025
  fantasy-data ingest historical-adp                                  # ADP 2017-2024 (FFC has no 2025)
  fantasy-data ingest rp --dir "data-dev/Reception Perception WR Deep Dive"   # hand-downloaded CSVs
  fantasy-data ingest rp --dir data-dev/rp-site/csv --position WR            # site exports (fetch_rp.py)

  Capturing from receptionperception.com (needs `ff-rankings login rp` once, from the
  pipeline repo — Playwright lives in ITS 'headless' extra):
    uv run python scripts/fetch_rp.py --all                  # data tables -> csv/ (browser)
    uv run python scripts/fetch_rp.py --profiles             # profile prose -> html/ (no browser)
  Profiles are corpus material, not DB rows: the run also writes `sources_rp.yaml`, which
  knowledge-base's config splices in via `files_from:`.

Phase 3: Draft Season (2026)
  fantasy-data ingest rankings --season 2026            # consolidate files already in update/
  fantasy-data ingest rankings --season 2026 --refresh  # fetch automated sources first, then consolidate
  fantasy-data ingest rankings --season 2026 --skip-source fpts   # a source that hasn't published yet

  Runs from any directory — the pipeline anchors its data dir and player_key_dict.json to
  its own repo root (config.project_root()); set FANTASY_PIPELINE_HOME to point elsewhere.

  Every source is REQUIRED — one missing file aborts the whole ingest. Through much of the
  preseason that is the normal state: the FantasyPoints fetcher refuses to download while
  the site still serves last season's board under this season's title, and Barrett publishes
  late. Use --skip-source; note it changes what the consensus columns MEAN (they average
  only the sources that remain).

Phase 4: Compute — ingest a season's actuals BEFORE computing its baselines
  for year in $(seq 2014 2025); do fantasy-data compute trust-weights --season $year; done
  fantasy-data compute baselines --season 2026 --lookback 3

Phase 5: Reports
  fantasy-data report adp-divergence --season 2026 --plot
  fantasy-data report trust-flags --season 2026 --plot
```

**Rolling to a new season.** The order below is load-bearing, not stylistic — every step depends on the
one before it, and getting it wrong fails silently rather than erroring. The 2026 refresh got it wrong
twice (see "Ordering traps" below).

1. Ingest **every** source of season N's actuals before computing anything from them —
   `ingest historical`, `ingest nflverse`, **and `ingest pff-bulk`** (PFF alone feeds
   `route_participation_rate` and `yards_per_route_run`).
   If `compute baselines --season N` already ran, clear its projections first (see gotchas).
2. Seed `coaching_staff` for season N+1 (names only), then `compute coaching-continuity`
   for **N first, then N+1** — N+1's tenure counts up from N's.
3. Ingest the new board as season N+1.
4. `compute baselines --season N+1 --lookback 3` — this CREATES most of season N+1's rows.
5. `compute trust-weights` for N and N+1 — **after** step 4, because it only updates rows that
   already exist.
6. Bump `DEFAULT_SEASON` in `quant-edge-mcp`'s `server.py` and the CLI's stale season defaults.

**Ordering traps** (both hit during the 2026 refresh, both silent, both found only by auditing the
blend against a hand-recomputed one):
- **Compute before every source has landed** → the blend quietly drops that season, and a plain
  re-run will **not** fix it: the no-overwrite rule skips the now-populated field, so the stale
  blend survives. Use **`compute baselines --season N --recompute`**, which clears the aggregable
  fields (and the `wopr`/`market_share_score` composites derived from them) before rebuilding.
  This bit twice in the 2026 refresh — `route_participation_rate`/`yards_per_route_run` were
  averaged from 2023-2024 only because `pff-bulk` had not been re-run yet, and five nflverse-fed
  fields (`snap_share`, `carries_per_game`, `total_touches_per_game`, `avg_depth_of_target`,
  `yards_after_catch_per_rec`) had the same defect across 29 rows. Both were invisible in aggregate
  and found only by re-deriving the blend and diffing.
- **`compute trust-weights` before `compute baselines`** → weights land on only the rows that existed
  at the time (2026: 216 of 1012), because trust-weights only updates rows that already exist while
  baselines is what creates most of them. `compute baselines` now WARNS when lookback rows have no
  weight (it blends them at `MISSING_TRUST_WEIGHT = 0.5`), but the warning is a smell, not a fix —
  run trust-weights for the lookback seasons and then again for the target.

To verify a blend actually used the seasons you think it did, recompute one player by hand and compare
against the stored value — a wrong blend is arithmetically plausible and invisible in aggregate.
`player_season_baseline.created_at`/`updated_at` (added 2026-07-15, NULL on older rows) exist to make
"which ingest wrote this, and had the sources landed yet?" answerable from the data rather than
inferred from the values.

Or use `fantasy-data build-history` for an automated Phase 2-4 sequence.

## Testing

144 tests across 11 files, all using in-memory SQLite:

- `test_models.py` — ORM models, FK constraints, unique constraints
- `test_ingest_rankings.py` — Sharp consensus, scarcity curves, divergence flags
- `test_ingest_pff.py` — Name-match enrichment, grade population
- `test_ingest_historical.py` — Box score mapping, derived fields, no-overwrite
- `test_ingest_nflverse.py` — Aggregation functions (seasonal, weekly, snaps, PBP), the `stats_player` share/racr derivations, the offensive-player filter, and no-overwrite vs backfill semantics
- `test_id_resolver.py` — gsis_id resolution, fallback ID generation
- `test_compute.py` — Trust weight formula (14 cases incl. QB continuity), baselines, route overlap
- `test_compute_coaching_continuity.py` — Flag/tenure derivation, play-caller vs OC-title basis, the LV regression
- `test_reports.py` — ADP divergence filtering, rankings breakdown, variance, trust flags
- `test_standardize.py` — Team abbreviations, player names, coach names
- `test_ingest_rp.py` — RP filename classification (both schemes), position isolation, source precedence, falsy-zero preservation, cross-season column renames, name-collapse matching
- `test_rp_contract.py` — pins each RP data type's exact header, proves both naming schemes parse to identical rows, and (marked `integration`, auto-skipped without `data-dev/`) compares the real site exports against the hand-downloaded CSVs cell by cell
- `test_viz.py` — NYT theme API (apply_theme, color_for_mode, annotate_point), all 7 chart modules return `go.Figure` (requires `--extra viz`)

## Integration with quant-edge

This repo is part of the quant-edge platform. See `/Users/henrymarsh/Documents/quant-edge/CLAUDE.md` for system-wide context.

- **PRD**: `Fantasy_Football_Domain_PRD.md` in quant-edge root
- **Dependency**: `fantasy-pipeline` at `../fantasy_data_pipeline` (editable local install)
- **Future**: Phase 3 wires research-assistant podcast signals into `qualitative_signals` table

## Common Gotchas

- **Package name mismatch**: The dependency is `fantasy-pipeline` (PyPI name) but imports as `fantasy_pipeline` (Python). The `uv.lock` resolves it from the local path `../fantasy_data_pipeline`.
- **PFF uses "HB" not "RB"**: The `ingest_pff.py` position group map handles this. PFF API JSON also uses different field names than CSV exports — `convert_pff_json.py` handles the translation.
- **`drop_rate` is PFF-only, stored as a proportion (0-1)**: PFF reports it as a percentage (0-100) and nflverse's PFR reports `drop_percent` as a proportion — both used to map to `drop_rate`, so the column was a percentage for 2014-2017 (PFF, no PFR before 2018) and a proportion for 2018+ (PFR, which runs first in the build order). A 100x split inside one trust-weighted field. Fixed 2026-07-15: `_normalize()` in `ingest_pff_bulk` rescales `PERCENT_FIELDS` on the way in, and PFR no longer writes the field at all — the two are *different measurements* (drops over ALL targets vs over CATCHABLE targets; 1.28x apart, only r=0.60 correlated on the same players), so alternating by season put a definitional break at 2018. PFF spans 2014-2025 with one definition; the cost is ~5% fewer players covered in 2018+ than PFR gave.
- **`games_played` means REGULAR-SEASON games, and `ingest_historical` is its only writer**: PFF's `player_game_count` counts the postseason (21 for a Super Bowl run) and used to map to the same field, so the no-overwrite rule let whichever ingest ran first decide the column's meaning per season — 2025 counted playoffs (Drake Maye 21) while 2014-2024 didn't. Fixed 2026-07-15 by dropping the mapping from `ingest_pff_bulk`/`ingest_pff`; don't re-add it. Per-game rates were never affected (`fpts_per_game_ppr` is derived inside `ingest_historical` from combined_data's own `G`, not from the stored column). This is the general hazard of two ingests mapping to one field: check for a second writer before assuming a field's semantics.
- **nflverse seasonal/weekly bypass nfl_data_py**: `nfl_data_py` (last released Sept 2024, unmaintained) reads nflverse's `player_stats` release, which was frozen in May 2025 and 404s for 2025+. `ingest_nflverse` reads the live `stats_player` release directly instead (`_fetch_weekly` → `aggregate_weekly_to_seasonal`); its other importers (snaps, PBP, NGS, FTN, PFR, IDs) still work and are still used. If a future season 404s, check whether nflverse renamed the release again.
- **The share columns are computed, not supplied**: `tgt_sh`/`ay_sh`/`dom` were never nflverse columns — nfl_data_py derived them, dividing by team pass **attempts**. nflverse's own `target_share`/`air_yards_share` divide by team **targets** and are NOT interchangeable (r≈0.89). `aggregate_weekly_to_seasonal` reproduces the nfl_data_py definitions so seasons stay comparable; it raises rather than silently NULLing if a column disappears.
- **`racr` was garbage before July 2026**: nfl_data_py builds its seasonal frame with a blanket `.sum()`, which summed weekly RACR rates into values like -80..85. It is now a true season rate (matches nflverse's own column exactly). Historical seasons were corrected via `ingest nflverse --overwrite-seasonal`; that flag replaces the share fields (and recomputes WOPR), nulling them when the new value is absent so stale numbers can't survive a backfill.
- **nflverse NGS starts at 2016, FTN at 2022, PFR at 2018**: Each nflverse sub-source has different season availability. The ingest filters automatically.
- **FTN requires PBP**: FTN charting data must be joined with PBP for player IDs. Don't use `--skip-pbp` if you want FTN data.
- **Historical ADP uses Fantasy Football Calculator API**: Free, no auth needed. Returns PPR ADP for 12-team leagues. URL: `fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year=YYYY`. Note the API returns 0 players for 2025 (an upstream gap — 2024 and 2026 are fine), so 2025 has no FFC ADP.
- **Compute baselines AFTER ingesting a season's actuals, never before**: `compute baselines --season N` writes trust-weighted projections into season N's row, and the ingest layer's no-overwrite rule then blocks the real data from ever landing. This silently stranded the whole 2025 season: the role signals were 2022-24 averages wearing a 2025 label (the tell was `dominator_rating` being NULL while `target_share` was full, since only the latter is an aggregable field). Clearing `AGGREGABLE_FIELDS` + `wopr`/`market_share_score` for that season is the fix.
- **PFF data captured via browser network tab**: No API or CSV export. Capture JSON from PFF's internal API, then run `scripts/convert_pff_json.py` to produce CSV for ingest.
- **Reception Perception has two naming schemes, and the filename is load-bearing**: hand-downloaded
  exports are `WR {Type} 2024-25.csv` / `{Type} - 2025 Draft Prospects.csv`; `scripts/fetch_rp.py`
  writes `wr-2025__{type}.csv` under `data-dev/rp-site/csv/{POSITION}/`. Both are accepted, and
  classification lives in `ingest/rp_parse.py`. **`Route Percentage` and `Success Rate by Route` have
  byte-identical headers** (`Year, Player, Total Routes, Screen, …, Other`) — one is the share of
  routes run, the other the success rate on them. The filename is the *only* discriminator, so a
  misclassification is undetectable downstream: the columns parse and the values are plausible
  percentages. `classify_type` raises rather than guessing when a name matches two types.
- **RP CSVs must be scoped by position**: the loader used to glob `*.csv` and select on data type
  alone, so an `RB Route Percentage` export sharing a directory with WR files merged into the WR
  frame, keyed only on `(Player, Year)`. `_load_csvs` now takes a `position`, skips files declaring a
  different one, and reads a `<dir>/<POSITION>/` subdirectory when present. RB charting is *run
  concepts* (gap/zone, loaded box, run stuffs), not route charting — it does not belong in this table.
- **RP renames columns between seasons**: tackle-breaking counts are `Opportunities` in the 2024
  export and `In Space Opportunities` in 2025, which is why `tackle_break_opportunities` was populated
  for 115 of 126 rows — missing exactly the 11 rows from 2025. Worse, the companion column changed
  *denominator*: 2024 gives `% of Routes`, 2025 gives `% of Catches`. They are stored as two columns
  (`in_space_pct_of_routes`, `in_space_pct_of_catches`) and must never be merged — that is the
  `drop_rate` mistake. Prospect exports can use the older name in the same season as pro exports use
  the newer one, so both readers stay live.
- **Never assign RP fields with `or`**: the ingest used `rp.field = _clean_pct(...) or rp.field`, and
  `0.0` is falsy — a charted zero was discarded and the previous value (or NULL) kept. Zero is a real,
  common reading here (no screens run, no double coverage faced, no tackles broken). Use `_set`, which
  treats only `None` as "the source said nothing".
- **`players.full_name` and RP disagree on punctuation**: the pipeline key dict stores `Jaxon
  SmithNjigba` / `AmonRa St Brown`; RP publishes `Jaxon Smith-Njigba` / `Amon-Ra St. Brown`.
  `standardize_player_name` keeps hyphens, so exact matching silently dropped two of the most-charted
  WRs. `_match_player` falls back to an alphanumeric-only key, but only where it resolves to exactly
  one player — nicknames (`Gabe` vs `Gabriel` Davis) stay unmatched by design. Every run prints the
  unmatched list; do not suppress it.
- **Site exports beat hand-downloaded CSVs where both exist**: the site table is live, a CSV on disk
  is a point-in-time copy. `_load_csvs` dedupes on (player, year, is_prospect) by `SOURCE_PRECEDENCE`
  and the row records which won in `wr_reception_perception.source`.
- **Adding a model column requires `sync_schema`, not just `init-db`**: `create_all()` never touches an
  existing table, so a new `Mapped[...]` attribute is invisible to an existing DB and every query
  against it fails with "no such column". `db.sync_schema()` (run automatically by `init-db`) issues
  additive `ALTER TABLE ... ADD COLUMN` for anything missing. It only ever adds — no drops, renames or
  retypes — so anything beyond an additive change still needs a hand-written migration.
- **`seasons_in_system` = min(system tenure, player's consecutive seasons on that team)**: it caps the system's age by how long the player has actually been in it — George Kittle reads 10 for Shanahan's system; a veteran who arrived this year reads 1 no matter how old the system is. It was previously capped by `players.years_pro`, which was wrong three ways: league experience is not time on the team, one static value cannot describe every season of a career, and the field was **never populated** (`years_exp -> years_pro` is mapped only in `ingest_pff`, whose bulk CSVs lack the column), so `min(system_years, years_pro or 1)` returned **1 for every player in every season since inception**. Team tenure comes from `player_season_baseline.team`, so no new source is needed. `players.years_pro` remains unpopulated and unused — don't reintroduce it as a cap.
- **Never hand-author continuity flags — derive them**: `compute coaching-continuity --season N` compares season N's stored names against N-1 and writes the flags plus HC/OC tenure. The 2024/2025 JSONs were hand-written, and nothing cross-checked them: Las Vegas 2025 carried the *2024* staff (Antonio Pierce / Luke Getsy) with `hc_continuity_flag = 1` straight through Pete Carroll's first year, so the ×0.65 decay never fired and Raiders trust weights ran ~4× too high (0.607 → 0.158 once corrected). Seed names only; let the command derive flags and tenure.
- **`oc_continuity_flag` tracks the play caller, not the OC title**: the two diverge on 5 of 32 teams in 2026 alone — BUF/KC/CHI/LAR changed OC while the play-calling head coach stayed (a title diff would fire ×0.40 wrongly), and CAR kept both names while play-calling moved Canales→Idzik (a title diff would miss a real scheme change). `play_caller` is NULL for 2014-2024, and the derivation falls back to the OC title whenever either season is unknown, so historical seasons keep their original semantics. The command reports how many teams used each basis — the fallback is never silent.
- **The OC column is historically a mix of both ideas**: pre-2026 `offensive_coordinator` holds the *head coach* for teams where he called plays (CHI/NO/SF 2025) but the *titled OC* elsewhere (KC/LAR/ARI 2025). That inconsistency is why `play_caller` exists. Don't assume the column means one thing.
- **Play-caller data has real limits**: four teams changed callers mid-2025 (CLE Wk10, DET Wk10, LV Wk12, TEN Wk4 — where the *QB coach*, not the OC, took over), and one row per team-season can't express that; the stored value is the Week 1 caller with the change recorded in `notes`. DET 2026 is deliberately NULL (sources conflict). LAR/NO 2026 are presumed from career-long patterns, not a fetched 2026 source. ESPN publishes an all-32 playcaller roundup each September — re-verify then.
- **Play-caller beats OC title for the decay — consistently supported at modest sample**: backtested over four transitions, 2021->2022 through 2024->2025 (play_caller now covers 2020-2026). Where the two signals disagree (14 teams, 114 player-transitions), target-share volatility follows the play-caller, not the OC title: 0.033 vs 0.028 abs Δ target share overall, and 0.047 vs 0.037 among contributors (prior target_share >= 0.10). The effect held and slightly strengthened when the sample doubled from the original 2-transition run (7 teams -> 14) — the opposite of a spurious small-sample artifact washing out. Not airtight (14 disagreeing teams), but firm enough to justify the basis. `fpts_per_game` was dropped as too noisy (TD/game-script/injury); target_share is the purer role signal and the one to trust. Only the missing 2019 year (probe: no clean source) is left; revisit after 2026 plays adds a fifth transition. Scratch analysis: `scratchpad/backtest_playcaller.py`.
- **Coach names are mangled by `.title()`**: `standardize_coach_name` renders "DeMeco Ryans" as "Demeco Ryans" and "Sean McVay" as "Sean Mcvay". Cosmetic only — it is applied consistently, so name comparisons still work — but don't be surprised by it, and don't "fix" it without re-standardizing every stored name at once.
- **Coach names are not stable join keys**: Zac Robinson (ATL→TB) and Tommy Rees (CLE→ATL) swapped teams in 2026, and Klint Kubiak (LV HC) is a different person from Klay Kubiak (SF OC) — one edit distance apart, both active. Join on team+season.
- **DB location**: Canonical location is `~/.fantasy-data/fantasy_data.db` — a stable home outside the repo so other projects can reference the same DB regardless of where they live on disk. Resolution order (`db.py`): explicit `db_path` arg → `FANTASY_DATA_DB` env var → `~/.fantasy-data/fantasy_data.db` → legacy in-repo `fantasy_data.db` (fallback for un-migrated checkouts). The parent dir is auto-created, so a fresh machine creates the DB in the canonical home on first `init-db`.
- **Sharing the DB with other projects**: `fantasy-data` is the sole writer; consumers read-only. Add it as an editable local dependency via absolute path (`[tool.uv.sources] fantasy-data = { path = "/Users/henrymarsh/Documents/quant-edge/fantasy-data", editable = true }`) and import `fantasy_data.db` / `fantasy_data.models`. No copies — one canonical DB file. SQLite handles many concurrent readers; never run two writers.
