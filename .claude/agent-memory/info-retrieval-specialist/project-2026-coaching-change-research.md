---
name: project-2026-coaching-change-research
description: The 2026 offseason was an unusually heavy coaching-turnover cycle — continuity assumptions carried over from 2025 will be wrong for most teams
metadata:
  type: project
---

The 2026 NFL offseason had exceptionally high coaching turnover. In the AFC North + AFC East alone (8 teams), 5 changed HC and 6 changed OC. Several long-tenured coaches assumed to be permanent fixtures left: Sean McDermott (fired), John Harbaugh (fired, → Giants), Mike Tomlin (stepped down after 19 years), Kevin Stefanski (fired), Mike McDaniel (fired).

**NFC South + NFC West verified 2026-07-15** (8 teams: 2 HC changes, 5 OC changes):
- ATL — HC Raheem Morris (fired, 8-9) → Kevin Stefanski; OC Zac Robinson → Tommy Rees (Rees calls plays; he was Stefanski's *Cleveland* OC in 2025, followed him to ATL).
- TB — HC Todd Bowles unchanged; OC Josh Grizzard (fired after 1 yr) → Zac Robinson (ATL's 2025 OC).
- CAR — HC Dave Canales + OC Brad Idzik both unchanged (Idzik OC since 2024), **but play-caller changed Canales → Idzik for 2026**. Inverse of the usual case: nominal OC continuity masks a real play-calling change.
- NO — HC Kellen Moore + OC Doug Nussmeier both unchanged (Nussmeier's 2nd yr).
- ARI — HC Jonathan Gannon (fired) → Mike LaFleur (Rams' 2025 OC); OC Drew Petzing (→ DET) → Nathaniel Hackett, who does **not** call plays (LaFleur does).
- LAR — HC Sean McVay unchanged; OC Mike LaFleur (→ ARI HC) → Nate Scheelhaase promoted from pass game coordinator. McVay has always been the play caller, so OC change is likely nominal.
- SF — HC Kyle Shanahan + OC Klay Kubiak both unchanged (Kubiak OC since 2025; Shanahan calls plays). Raheem Morris joined SF as DC.
- SEA — HC Mike Macdonald unchanged; OC Klint Kubiak (→ LV HC after SB LX win) → Brian Fleury (ex-SF run game coordinator/TE coach).

The Klint Kubiak (SEA→LV HC) / Klay Kubiak (SF OC) name collision is a real trap — they are different people on different teams.

**Why:** This matters for the `trust_weight` formula in `compute_trust_weights.py` — OC change ×0.40, HC change ×0.65 are the heaviest multiplicative decays in the model. A wrong continuity flag silently inflates trust on a player whose scheme actually turned over, which propagates into every baseline that season.

**How to apply:** Do NOT carry 2025 continuity assumptions into 2026 for any team, and do not infer a coach is still in place because they were long-tenured — verify every team from a fetched source. Prior-year staff data is not a safe default this cycle. See [[reference-nfl-coaching-staff-sources]] for verification sources and the OC-vs-play-caller distinction (a nominal OC change with an unchanged play caller may not warrant full OC decay — Buffalo 2026 is exactly this case).
