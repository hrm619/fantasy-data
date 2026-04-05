# Data Enhancement Plan

Three free data sources that fill critical baseline gaps using data already available through nflverse.

---

## Phase 1: NGS Tracking Data

**Source**: `nfl_data_py.import_ngs_data('receiving' | 'rushing', seasons)`
**Fields filled**: `avg_cushion`, `avg_separation`, `avg_expected_yac`, `catch_rate_over_expected`
**Availability**: 2016-2024, weekly granularity (aggregate to season)

### What it gives us
- `avg_cushion` — yards of space at snap between WR and nearest defender. Higher = more schemed separation.
- `avg_separation` — yards of space at time of throw/arrival. The best proxy for route-running + athleticism.
- `avg_expected_yac` / `avg_yac_above_expectation` — YAC over expected from tracking. Distinguishes scheme YAC (screens, RAC plays) from skill YAC (broken tackles, speed).
- `avg_intended_air_yards` — tracking-derived aDOT (more precise than PBP-derived).
- `catch_percentage` — tracking-derived catch rate.
- Also available for rushing: `expected_rush_yards`, `rush_yards_over_expected`, `avg_time_to_los`.

### Implementation
- Add `_fetch_ngs_receiving()` and `_fetch_ngs_rushing()` to `ingest_nflverse.py`
- Aggregate weekly NGS to season-level (mean per player-season)
- Merge by gsis_id → player_id via existing id_map
- Only set fields where baseline is currently NULL (don't overwrite PFF/PBP-derived values)
- Available 2016-2024 (~7 seasons in lookback, ~1,400 WR/TE/RB per season)

### Baseline fields populated
| NGS Column | Baseline Field | Currently |
|-----------|---------------|-----------|
| `avg_cushion` | `avg_cushion` | Empty |
| `avg_separation` | `avg_separation` | Empty |
| `catch_percentage` | (validate vs existing `catch_rate`) | Partial |
| `avg_yac_above_expectation` | `catch_rate_over_expected` (repurpose or new field) | Empty |
| `avg_intended_air_yards` | `avg_depth_of_target` (validate vs PFF) | Partial |
| NGS rushing `efficiency` | `expected_yards_per_carry` | Empty |
| NGS rushing `rush_yards_over_expected_per_att` | `rush_yards_over_expected` | Empty |

---

## Phase 2: FTN Charting Data

**Source**: `nfl_data_py.import_ftn_data(seasons)`
**Fields filled**: Play-action target %, screen target %, true drop rate, contested ball rate, catchable ball rate
**Availability**: 2022-2024, play-level (aggregate to player-season)

### What it gives us
Play-level flags that aggregate to scheme-context metrics:
- `is_play_action` — % of a player's targets on play-action. High PA rate = scheme-dependent production.
- `is_screen_pass` — % of targets on screens. High screen rate = short/manufactured touches.
- `is_drop` — film-charted drops (independent of PFF and PFR). Third source for drop rate validation.
- `is_contested_ball` — charted contested targets. Compare to PFF/RP contested data.
- `is_catchable_ball` — what % of targets were catchable. Measures QB quality on targets to this WR.
- `is_created_reception` — receptions where WR created the play (not schemed open).

### Implementation
- New aggregation function: `aggregate_ftn(pbp_df, ftn_df)` that joins on game_id + play_id
- Group by receiver/rusher player_id + season
- Compute: `play_action_target_pct`, `screen_target_pct`, `true_drop_rate`, `catchable_ball_pct`, `created_reception_pct`
- New baseline fields or store in a supplemental table

### Value
- **Scheme independence scoring**: A WR with 40% play-action targets is more scheme-dependent than one with 10%. This directly informs the trust weight — if the OC changes, the PA-dependent WR's baseline is less reliable.
- **Drop rate triangulation**: Three independent drop rate sources (PFF, PFR, FTN) gives high-confidence drop assessment.
- **Created reception rate**: Measures WR agency — comparable to RP's success rate but from charting data instead of film study.

---

## Phase 3: Historical ADP

**Source**: FantasyPros historical ADP archives (free, downloadable CSVs)
**Fields filled**: `adp_consensus` for 2017-2024 baselines (currently all NULL)
**Availability**: 2017-2024

### What it gives us
- Pre-season ADP for every ranked player, every year
- Enables: "where was this player drafted vs. where did they finish?"
- ADP finish delta = how the market mispriced this player historically
- Combined with our existing actuals data, enables the historical ADP divergence backtest from the calibration brainstorm

### Implementation
- Download FantasyPros historical ADP CSVs (one per year)
- New ingest script or extend `ingest_historical.py` to populate `adp_consensus` and `adp_positional_rank` on existing baselines
- Match by player name (FantasyPros names → standardized)

### Analytical value
- **Calibration**: Backtest whether sharp consensus historically outperformed ADP — validates the entire divergence model
- **Player-level ADP trajectory**: A player who was ADP 50 → ADP 20 → ADP 10 over 3 years has a different signal than one who was always ADP 10
- **Market efficiency**: Which positions does the ADP market misprice most consistently?

---

## Execution Order

| Phase | Data | Effort | Timeline |
|-------|------|--------|----------|
| **Phase 1** | NGS tracking | Low — extend existing nflverse ingest | Now |
| **Phase 2** | FTN charting | Medium — new aggregation logic | After Phase 1 |
| **Phase 3** | Historical ADP | Medium — new data source + ingest | After Phase 2 |

After all three phases, the baseline model will have near-complete field coverage for 2018-2024 with multiple independent sources for key metrics (drop rate from PFF + PFR + FTN, separation from NGS + RP, aDOT from PBP + PFF + NGS).
