# Data Gathering To-Do List

Prioritized list of external data to acquire, organized by source. Each item notes what fields it fills, how to get it, and what it costs.

---

## Tier 1: High Priority (Fills Critical Baseline Gaps)

### PFF Grades & Metrics
**What it fills**: `pff_receiving_grade`, `pff_rush_grade`, `pff_run_blocking_grade`, `route_grade_pff`, `target_quality_rating`, `contested_target_rate`, `drop_rate`, `broken_tackle_rate`
**Why it matters**: Only source for play-grading data. Grades capture efficiency that box scores miss — a WR can have identical targets but vastly different route grades. Broken tackle rate and contested catch rate are unique to PFF.
**How to get**:
- PFF Ultimate subscription ($39.99/mo or $249.99/yr)
- Export CSV from PFF player pages → filter by season → download
- Manual process: navigate to position group page, export "Grades" and "Receiving" or "Rushing" tabs
- Columns needed: `player_id`, `player`, `position`, `team_abbr`, `receiving_grade`, `route_grade`, `rushing_grade`, `run_block_grade`, `target_quality_rating`, `drop_rate`, `contested_catch_rate`, `games`, `games_started`, `jersey_number`, `age`, `years_exp`, `draft_year`, `draft_round`, `draft_pick`, `college`, `height`, `weight`
**Seasons needed**: 2022, 2023, 2024 (lookback window). Ideally 2014-2024 for full history.
**Ingest**: Already built — `fantasy-data ingest pff --file <csv> --season <year>`
**Status**: Not acquired

### PFF Projections
**What it fills**: Could populate `fp_projected_pts_ppr`, `fp_projected_pts_std` as a secondary projection source alongside FantasyPros
**Why it matters**: PFF projections are considered among the most accurate. Cross-referencing with FPTS projections gives a "projection consensus" for the model.
**How to get**: Same PFF Ultimate sub. Export from projections page.
**Status**: Not acquired

---

### Reception Perception (Matt Harmon)
**What it fills**: WR-specific route-level performance metrics that no other source provides. Film-graded separation, route win rates, coverage-type splits, contested catch, and YAC profile.
**Why it matters**: RP is the only source that evaluates WR performance independent of QB/scheme by charting every route in an 8-game sample. Success Rate vs. Man coverage is the single highest-correlation metric to WR breakouts (82% hit rate above 80th percentile → 1,000-yard season). This is the film-graded equivalent of NGS separation data, but more granular and available for 270+ WRs since 2014.

**Data available** (7 structured CSVs per season, all keyed by Player + Year):

| Dataset | Fields | Fantasy-Data Value |
|---------|--------|-------------------|
| **Success Rate vs. Coverage** | man atts, Success Rate vs. Man, zone atts, Success Rate vs. Zone, dbl atts, Success Rate vs. Double, press atts, Success Rate vs. Press, Routes, % Press, % Man, % Zone, % Doubled | **Crown jewel** — QB-independent separation grades by coverage type. Replaces need for NGS avg_separation. |
| **Route Percentage** | % by route: Screen, Slant, Curl, Dig, Post, Nine, Corner, Out, Comeback, Flat, Other | **Route tree profile** — classifies WR archetype (deep threat vs. possession vs. complete). Directly informs `route_tree_type` for target competition. |
| **Success Rate by Route** | Win rate on each individual route type (same route categories) | **Route-level skill** — identifies specific strengths/weaknesses (e.g., elite on Slants but poor on Nines). Enables scheme-fit scoring. |
| **Alignment Data** | Outside %, LWR %, RWR %, Slot %, Backfield %, Behind LOS %, On LOS % | **Deployment profile** — maps to OUTSIDE/SLOT/FLEX classification. Reveals if a WR plays a true X role or moves around. |
| **Target Data** | Total Routes, Route Target Rate, Route Catch Rate, Targets, Catch Rate, Drop Rate | **QB-independent demand** — Route Target Rate (targets per route) is purer than target share. Film-graded Drop Rate is more accurate than PBP-derived. |
| **Contested Catch** | Contested Targets, Contested Target Rate, Contested Catch Rate | **Catch radius** — strongest predictor of WR ceiling. Complements PFF contested_target_rate. |
| **Tackle Breaking** | Opportunities, % of Routes, 1st Contact Drop %, 1 Broken Tackle %, 2+ Broken Tackle % | **YAC profile** — physicality-based YAC (broken tackles) vs. speed-based YAC. |

Plus **Dynasty Rankings** with Buy/Sell/Hold signals and qualitative scouting notes.

**Coverage**: 43 WRs in 2023 season, sample of 9 in 2024-25. Full sub covers 50+ per season. 270+ since 2014.

**How to get**:
- Reception Perception subscription (receptionperception.com, est. $30-50/yr)
- Data arrives as structured CSVs (already have samples in `data-dev/Reception Perception WR Deep Dive/`)
- Pre-draft rookie profiles also available as RTF/PDF (6 in `qualitative-dev/2025 Pre-Draft/RP/`)

**Integration design**:

*Option A (recommended): New `wr_reception_perception` table*
- Dedicated table since RP data is WR-only, multi-dimensional, and updated on its own cadence
- Schema: `player_id FK, season, routes_charted, success_rate_man, success_rate_zone, success_rate_press, success_rate_double, route_target_rate, route_catch_rate, contested_catch_rate, drop_rate_rp, pct_outside, pct_slot, pct_nine, pct_slant, pct_curl, pct_dig, pct_post, pct_screen, tackle_break_rate`
- Composite score: `rp_score = weighted_mean(success_rate_man * 0.4, success_rate_zone * 0.25, success_rate_press * 0.2, contested_catch_rate * 0.15)`
- Joins to baseline via `player_id + season`

*Option B: Flatten into PlayerSeasonBaseline*
- Add ~10 fields directly to baseline (simpler queries, but WR-only fields on a position-agnostic table)

*Qualitative notes*: Dynasty Buy/Sell/Hold signals and scouting text → `qualitative_signals` table with `signal_type='RP_SCOUTING'`

*Auto-classification*: Route Percentage + Alignment data can auto-populate `Player.route_tree_type`:
- Outside > 70% → OUTSIDE
- Slot > 50% → SLOT
- Mixed → FLEX
- This enables the target competition analysis (Phase 2)

**New module**: `src/fantasy_data/ingest/ingest_reception_perception.py`
- Reads all 7 CSVs for a given season
- Joins on player name (via `standardize_player_name()`)
- Creates/updates `wr_reception_perception` records
- Auto-sets `Player.route_tree_type` from alignment data
- CLI: `fantasy-data ingest rp --dir <path> --season <year>`

**Seasons to acquire**: 2022, 2023, 2024 (lookback window). 2025 pre-draft for rookies.
**Status**: Sample data in hand (2023 full, 2024-25 partial). Sub needed for complete coverage.

---

## Tier 2: Valuable Supplements (Enhance Existing Fields)

### Expected Fantasy Points (xFPTS) — Hayden Winks + Scott Barrett
**What it fills**: Expected fantasy points based on opportunity quality, stripping TD variance. xFP vs actual FP identifies over/under-performers and regression candidates.
**Why it matters**: xFPTS is the single best predictor of future fantasy output. Two sharp sources provide this independently:
- **Hayden Winks (HW)**: `HPPR` (half-PPR projection) and `EXP` (expected points) via Underdog. Already configured in pipeline as `hw-data` merge source.
- **Scott Barrett (FPTS)**: `XFP`, `XTD`, plus target detail (`EZTGT`, `DEEPTGT`, `AIRYDS`). Already configured in pipeline as `fpts-data` merge source.
**Current gap**: Both data sources are configured in `fantasy_data_pipeline/config.py` and merge during processing, but **the xFPTS columns are dropped before the final consolidated output CSV**. The data is in the pipeline — it just doesn't flow through to `fantasy-data`.
**How to fix**:
1. Update `fantasy_data_pipeline` processor to include `HPPR`, `EXP`, `XFP`, `FPTS_DIFF`, `XTD`, `EZTGT`, `DEEPTGT`, `AIRYDS` in the final output
2. Add column mappings in `fantasy-data/ingest_rankings.py` COLUMN_MAP
3. Add new baseline fields: `xfp_hw`, `xfp_fpts`, `xfp_diff`, `xtd`, `deep_target_pct`, `ez_target_pct`
**Cost**: HW data is scraped (free via Underdog Network). FPTS requires FantasyPoints.com ($24.99/yr).
**Status**: Data is in the pipeline config but not flowing through. Pipeline output change + new COLUMN_MAP entries needed. No new subscription required for HW; FPTS sub may already be active.

### DraftSharks Detailed Data
**What it fills**: Strength of schedule data, bye weeks, injury risk scores. `ds_POS RANK` already ingested.
**Why it matters**: DraftSharks is the only source with explicit SOS (strength of schedule) rankings and injury risk modeling. SOS context helps explain why a player at the same ADP might have very different floors.
**How to get**:
- DraftSharks subscription ($29.99/yr)
- The pipeline already ingests DS rankings (`ds` source key)
- Additional data: SOS rankings by position, injury risk scores, bye week projections
- CSV export from site
**What's new vs. what we have**: We have DS positional rankings. The incremental value is SOS and injury risk.
**Status**: Rankings already ingested. SOS/injury risk not captured.

---

## Tier 3: Nice to Have (Advanced Metrics)

### Next Gen Stats (NFL NGS)
**What it fills**: `avg_cushion`, `avg_separation`, `expected_catch_rate`, `catch_rate_over_expected`, `expected_yards_per_carry`, `rush_yards_over_expected`, `avg_box_count`
**Why it matters**: Tracking data captures what the eye test sees — how much separation a WR gets, how tight the coverage window is. These are the highest-signal efficiency metrics available.
**How to get**:
- nfl_data_py has `import_ngs_data()` — partially available for recent seasons
- NFL.com Next Gen Stats page has some data publicly
- Full dataset requires NFL data access agreement (rare for individuals)
- Alternative: nflverse may have partial NGS data bundled
**Status**: Stub ingest exists (`ingest_ngs.py`). Need to check `nfl_data_py.import_ngs_data()` coverage.
**Action item**: Test `import_ngs_data()` to see what's available before pursuing paid access.

### ESPN/FantasyPros Projections
**What it fills**: `fp_projected_pts_ppr`, `fp_projected_pts_std`
**Why it matters**: Consensus projection baseline. Useful for computing projection-vs-baseline variance.
**How to get**:
- FantasyPros free tier has ECR and consensus projections
- Already in pipeline as `fp` source — may need to extend column mapping for projections
**Status**: ECR rankings ingested. Projections not captured.

### Underdog ADP Data
**What it fills**: `adp_underdog` field (best ball ADP)
**Why it matters**: Underdog best ball ADP is the sharpest ADP market. Comparing Underdog vs. redraft ADP reveals format-specific edges.
**How to get**:
- Underdog Fantasy publishes ADP data (free)
- Available via Hayden Winks data exports
- Would need new column mapping in pipeline
**Status**: Not captured. `adp_underdog` column exists in model but is empty.

---

## Tier 4: Future / Research Phase

### Coaching Analytics (Sharp Football)
**What it fills**: `pass_rate_tendency`, `te_usage_tendency`, `rb_pass_usage_tendency`, `tempo`
**Why it matters**: Team-level tendencies directly predict positional opportunity. A team running 65% pass rate creates more WR value than one running 45%.
**How to get**:
- Sharp Football Stats subscription
- Or compute from nflverse PBP data (team-level aggregation — we could build this)
- Pass rate = pass plays / total plays per team-season
- Already partially derivable from our PBP ingest
**Action item**: Add team-level tendency computation to `ingest_nflverse.py` as a bonus aggregation step.

### Snap Count Breakdown by Formation
**What it fills**: `route_participation_rate` (more precise than snap_share)
**Why it matters**: A WR can have high snap share but run fewer routes if they're blocking in heavy sets. Route participation is a better measure of pass-game involvement.
**How to get**: nflverse PBP data can approximate this (count plays where player ran a route vs. was on field)
**Status**: Would require PBP enhancement to track individual route running.

---

## Data Acquisition Summary

| Source | Cost | Fields | Priority | Status |
|--------|------|--------|----------|--------|
| **PFF Grades** | $250/yr | 8 grade fields, all positions | Tier 1 | Not acquired |
| **PFF Projections** | (same sub) | 2 projection fields | Tier 1 | Not acquired |
| **Reception Perception** | ~$30-50/yr | 20+ WR-specific metrics (7 CSVs) | Tier 1 | 2023 full (43 WRs) + 2024 partial (9) in hand |
| **xFPTS (HW + FPTS)** | $25/yr (FPTS only) | XFP, XTD, target detail | Tier 2 | In pipeline, not flowing through |
| **DraftSharks SOS** | $30/yr | SOS, injury risk | Tier 2 | Rankings ingested, detail not |
| **NGS Tracking** | Free (partial) | 7 tracking fields | Tier 3 | Test nfl_data_py first |
| **FantasyPros Projections** | Free | 2 projection fields | Tier 3 | ECR ingested, projections not |
| **Underdog ADP** | Free | 1 ADP field | Tier 3 | Column exists, not populated |
| **Sharp Football Tendencies** | Derivable | 4 tendency fields | Tier 4 | Build from PBP |

## Next Actions

### Data Acquisition
1. **Subscribe to PFF Ultimate** — largest single data unlock, fills 8+ fields across all positions
2. **Acquire RP subscription** — get 2022 + 2024 full season data to match 2023 already in hand
3. **Test `nfl_data_py.import_ngs_data()`** — check what's free before pursuing paid NGS access
4. **Check Underdog ADP availability** — may be bundled with HW data exports

### Pipeline / Code Changes
5. **Build RP ingest module** — new table `wr_reception_perception`, new `ingest_reception_perception.py`, CLI command. Can prototype now with 2023 data already in hand.
6. **Flow xFPTS through pipeline** — update `fantasy_data_pipeline` to carry HW `HPPR`/`EXP` and FPTS `XFP`/`XTD` to final output. Add COLUMN_MAP entries + baseline fields in fantasy-data.
7. **Build team tendency aggregation** — compute pass_rate, TE usage, RB pass usage from existing PBP data
8. **Auto-populate `route_tree_type`** — use RP Alignment Data to classify WRs, enabling target competition (Phase 2)
