# Trust Weight Calibration Brainstorm

## Current State

The trust weight system uses manually chosen multipliers to discount historical baselines when a player's production context changes. All values were set by domain intuition, not empirically validated.

**Current multipliers:**
| Factor | Multiplier | Source |
|--------|-----------|--------|
| New OC | ×0.40 | PRD Section 6.3 (intuition) |
| New HC | ×0.65 | PRD Section 6.3 (intuition) |
| New QB (WR/TE) | ×0.50 | Domain reasoning |
| New QB (RB) | ×0.75 | Domain reasoning |
| Team change | ×0.20 | PRD Section 6.3 (intuition) |
| Injury | ×0.55 | PRD Section 6.3 (intuition) |
| Rookie cap | 0.50 | PRD Section 6.3 (intuition) |
| Floor | 0.05 | PRD Section 6.3 (intuition) |

---

## Empirical Calibration Ideas

### 1. Year-over-Year Correlation Study

**Concept**: Measure how well Season N stats predict Season N+1 stats under different change conditions. The multiplier should reflect the actual predictive decay.

**Method**:
- For each player-season pair (N, N+1) in our 2014-2024 data, compute the correlation between Season N and Season N+1 for key metrics (fpts_per_game_ppr, target_share, snap_share)
- Segment by change type: no change, OC only, HC only, QB only, team change, combinations
- The correlation coefficient for each segment IS the empirical multiplier

**Example**: If target_share correlation is 0.85 with no changes but 0.35 with a new OC, then the OC multiplier should be ~0.41 (0.35/0.85) — close to our 0.40 but now evidence-based.

**Data needed**: Already have it — player_season_baseline × coaching_staff for 2014-2024.

**Implementation**: New script in `scripts/calibrate_trust_weights.py` that runs the correlation analysis and outputs recommended multipliers.

### 2. Prediction Error Backtest

**Concept**: Use the trust-weighted baseline as a "prediction" for Season N+1 and measure RMSE against actuals. Sweep multiplier values to find the set that minimizes error.

**Method**:
- For each player entering Season N+1, compute the trust-weighted baseline using Seasons N-2, N-1, N
- Compare to actual Season N+1 stats
- Grid search or gradient descent over multiplier space to minimize RMSE
- Cross-validate: train on 2014-2020, test on 2021-2024

**Advantage**: Directly optimizes the thing we care about — prediction accuracy.

**Risk**: Overfitting to small sample sizes, especially for compound flags (e.g., HC + OC + QB change might only have 15 player-seasons).

### 3. Bayesian Hierarchical Model

**Concept**: Model the "true" year-over-year stability as a latent variable that depends on change factors. Let the data determine both the magnitude and uncertainty of each factor.

**Method**:
- Likelihood: `stats_{n+1} ~ Normal(multiplier * stats_n, sigma)`
- Multiplier: `log(multiplier) = beta_0 + beta_oc * oc_change + beta_hc * hc_change + ...`
- Priors: weakly informative centered on current values
- Fit with PyMC or Stan

**Advantage**: Gives uncertainty intervals on each multiplier, not just point estimates. We'd know that OC change is ×0.40 ± 0.08, not just ×0.40.

**Disadvantage**: More complex, requires additional dependencies.

---

## Additional Trust Factors to Consider

### 4. Scheme Similarity on Coaching Changes

**Current gap**: All OC changes are treated equally, but replacing a Shanahan-zone OC with another Shanahan-zone OC is very different from replacing one with an Air Raid OC.

**Concept**: When `oc_continuity_flag=0`, check if the new OC's `system_tag` matches the old OC's. If same scheme family, reduce the penalty.

**Implementation**:
- Add `prev_system_tag` or compute at trust-weight time
- If `system_tag` matches prior season: `oc_change_multiplier = 0.60` instead of 0.40
- If different scheme: keep 0.40

### 5. Coaching Tree Proximity

**Concept**: A new OC who worked under the same HC or came from the same coaching tree (e.g., McVay assistants going to other McVay-tree teams) preserves more scheme continuity than a completely unrelated hire.

**Data needed**: Coaching tree relationships (who worked for whom). Partially captured by `system_tag` but could be more granular.

### 6. QB Quality / Archetype Change

**Current gap**: QB change is binary. But replacing Kirk Cousins (pocket passer) with JJ McCarthy (mobile) is more disruptive than replacing one pocket passer with another.

**Concept**: Weight the QB change multiplier by how different the QBs are:
- Same archetype (pocket→pocket): ×0.65
- Different archetype (pocket→mobile): ×0.40
- Upgrade (bad→good): ×0.60 (less trust in historical but upside)
- Downgrade (good→bad): ×0.45

**Data needed**: QB archetype classification (could derive from rushing stats, aDOT, time-to-throw).

### 7. Draft Capital / Age-Adjusted Rookie Factor

**Current gap**: All rookies capped at 0.50. But a 1st-round pick and a 7th-round pick have very different baseline expectations.

**Concept**: Scale rookie cap by draft capital:
- Round 1: cap at 0.60 (high investment = high opportunity floor)
- Round 2-3: cap at 0.50 (current)
- Round 4+: cap at 0.40 (lower guaranteed role)
- UDFA: cap at 0.30

**Data needed**: Already have `draft_round` on Player model.

### 8. Injury Severity Gradient

**Current gap**: Binary injury flag (×0.55 or nothing). A player who missed 4 games with a hamstring is very different from one who missed 12 with an ACL.

**Concept**: Scale multiplier by games missed:
- 4-6 games: ×0.70
- 7-10 games: ×0.55 (current)
- 11-14 games: ×0.40
- 15+: ×0.25
- Also weight by injury type: soft tissue recurrence risk vs. structural recovery

**Data needed**: `games_played` is already in baseline. Could derive from 17 - games_played. Injury type would need external source.

### 9. Age Curve Decay

**Current gap**: No age factor. A 32-year-old WR's baseline should be discounted more than a 26-year-old's even with full continuity.

**Concept**: Apply age-curve multiplier based on position-specific aging curves from the literature:
- RB: peak 23-25, sharp decline after 27
- WR: peak 25-29, gradual decline after 30
- TE: peak 26-30, slow decline
- QB: peak 27-34, varies

**Implementation**: `age_multiplier = age_curve[position](player.age)` applied after all other factors.

**Data needed**: Age already on Player model. Age curves from academic research (Berry & Reade, Over the Hill at 24, etc.).

### 10. Snap Share Trajectory

**Concept**: A player whose snap share was trending up vs. down in the lookback window should have different trust. Increasing snap share = role solidifying. Decreasing = role eroding.

**Implementation**: Compute slope of snap_share across lookback seasons. Positive slope → bonus (×1.1), negative slope → penalty (×0.85).

### 11. Contract Year Effect

**Current gap**: `contract_year_flag` exists on Player but isn't used in trust weights.

**Concept**: Players in contract years may over-perform (motivation) or be traded/leave. After a contract year, their production is less stable.

**Implementation**: If prior season was contract year AND player re-signed with same team → ×0.80 (post-contract-year regression). If player changed teams after contract year → already captured by team_change.

---

## Tuning Methodology

### Recommended Approach: Phased

**Phase 1 (now)**: Run the Year-over-Year Correlation Study (#1) as a validation exercise. This requires no new dependencies and uses existing data. It will tell us if our current multipliers are in the right ballpark.

**Phase 2**: Implement the Prediction Error Backtest (#2) to optimize multiplier values. This is the "proper" calibration — minimize prediction error on held-out data.

**Phase 3**: Add the highest-value new factors:
- Scheme similarity (#4) — low effort, data exists
- Draft capital rookie scaling (#7) — low effort, data exists
- Injury severity gradient (#8) — low effort, data exists
- Age curve (#9) — medium effort, requires defining curves

**Phase 4**: Bayesian model (#3) if we want uncertainty quantification for the research-assistant integration (e.g., "this edge has a trust weight of 0.40 ± 0.08").

### Key Principle

The trust weight should equal the **empirical year-over-year correlation under that change condition**. If our data shows that WR target_share correlates at r=0.82 with no changes and r=0.33 with a new QB, then the QB multiplier for WR should be 0.33/0.82 ≈ 0.40, not our intuited 0.50. The calibration study will reveal these ratios.

### Sample Size Concerns

Some compound conditions (new HC + new OC + new QB + team change) may have too few observations for reliable correlation estimates. For these:
- Use the multiplicative assumption (compound = product of individual factors)
- Validate with the backtest that the compound product doesn't over-discount
- Consider Bayesian shrinkage toward the multiplicative prior

---

## Quick Wins for Next Session

1. **Calibration script**: `scripts/calibrate_trust_weights.py` — correlate season-over-season stats segmented by change type
2. **Draft capital scaling**: Modify `compute_trust_weight()` to use `draft_round` for rookies
3. **Injury severity**: Replace binary flag with games-missed gradient
4. **Scheme similarity**: When OC changes, check if `system_tag` matches prior season
