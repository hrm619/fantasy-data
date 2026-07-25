---
name: reference-nfl-play-caller-verification
description: How to verify who ACTUALLY called NFL offensive plays per team+season — the best canonical sources, plus verified AFC South/West + NFC South/West play-callers for 2025 and 2026
metadata:
  type: reference
---

Verifying the **play caller** (not the OC) per team+season. The OC title is not evidence — see
[[reference-nfl-coaching-staff-sources]] for the OC≠play-caller gotcha.

## Highest-yield sources (fetched, no auth)
- **ESPN MIDSEASON playcaller update is better than the preseason one** — the Nov 17 2025 edition prints an
  explicit `Offensive coordinator: X | Playcaller: Y` pair per team, which is exactly the OC-vs-caller
  distinction we need, AND it catches in-season changes the preseason article cannot:
  `https://www.espn.com/nfl/story/_/id/46970963/nfl-offensive-coordinators-playcallers-josh-mcdaniels-dan-campbell`
  It also states which teams changed callers in-season (2025: **Detroit only**), which lets you rule out
  mid-season changes league-wide in one fetch. Fetch this one FIRST; the preseason edition is prose and
  often only names the OC without saying he calls plays.
- **ESPN annual "all 32 playcallers" preview** — 2025 edition:
  `https://www.espn.com/nfl/story/_/id/46137832/nfl-playcallers-32-teams-mike-mcdaniel-sean-mcvay-brian-schottenheimer`
  Published ~Sept 9. **The next season's edition does not exist until ~Sept of that year** — as of July 2026
  there is no 2026 all-32 roundup, which is why 2026 cells are inherently weaker than 2025 cells. Re-run any
  2026 sweep after early Sept 2026.
- **CBS "new play-caller" fantasy series** is a useful *negative* signal: teams absent from its list are
  teams with no play-caller change. `https://www.cbssports.com/fantasy/football/news/new-play-caller-nfl-fantasy-football-rankings/`
- **Official team sites state play-calling changes explicitly** when they happen (tennesseetitans.com,
  raiders.com, denverbroncos.com all published dedicated "X hands off play-calling to Y" articles).
  Search `{team}.com "play-calling duties"`.
- **profootballrumors.com** is fetchable (unlike PFR/SB Nation) and is unusually good on *interim* /
  mid-season play-caller detail that team sites and Wikipedia both omit.
- **Wikipedia season pages are useless for play-calling** — the 2025 Titans season page lists the staff
  but never says who called plays, despite two mid-season changes. Don't bother fetching for this field.

- **CBS "new play-caller" list names 2026 callers outright** ("2. Lions play-caller Drew Petzing"), but that
  is an *editorial* designation and it over-claims: it asserted Petzing while Campbell was publicly
  uncommitted. Corroborate against a team site or ESPN before trusting a name from it.
- **Blocked/paywalled for this field**: fantasypoints.com (HTTP 402), acmepackingcompany + all SB Nation
  (403), athlonsports.com (403). The Yahoo "NFL's play-callers are set for 2026" roundup 404s at
  `sports.yahoo.com/articles/nfl-play-callers-set-2026-230450873.html` — its content survives only on the
  blocked SB Nation mirror, so that widely-cited piece is effectively unfetchable.

## ESPN "all 32 playcallers" annual franchise — coverage map (probed 2026-07-19)
The ESPN NFL Nation preseason roundup prints the actual playcaller per team WITH title, correctly
flagging HC-callers (Shanahan/McVay/Reid/Payton) vs OC-callers (verified in 2023, 2024). Confirmed IDs:
- **2017**: `espn.com/espn/print?id=21415806` (pub Nov 15 2017; earliest found)
- **2023**: `espn.com/nfl/story/_/id/38108724` (pub Aug 23 2023) — preseason
- **2024**: `espn.com/nfl/story/_/id/41018846` — preseason (verified reliable)
- **2025**: `espn.com/nfl/story/_/id/46137832` — preseason
Midseason "what's gone right/wrong for every OC/playcaller" franchise (catches in-season caller changes):
- **2024 midseason**: `espn.com/nfl/story/_/id/42466407`
- **2025 midseason**: `espn.com/nfl/story/_/id/46970963`
**GAP — 2019/2020/2021/2022 dedicated roundups did NOT surface** in ~6 targeted searches. Story-ID jump
21M(2017)→38M(2023) suggests franchise was paused ~2018-2022 and revived 2023. Absence of evidence, not
proof: an ESPN site-search or ID-range scan (2022≈33M, 2021≈29M, 2020≈27M, 2019≈24M) could still find them.
**Backfill verdict**: 2023+2024 cheap (2 fetches, reliable). ESPN itself has NO 2019-2022 roundup.

## Yardbarker "Ranking the offensive play-caller for each NFL team" — the 2019-2022 backfill source (probed 2026-07-19)
This overturns the earlier "2019-2022 need per-team reconstruction" conclusion. Yardbarker runs an
**annual all-32 play-caller ranking** (prose slideshow, 1-32) that DOES flag HC-callers vs OC-callers —
it lists each caller's title ("49ers head coach", "Chiefs head coach") and even handles OC-caller edge
cases (2020 edition explicitly notes Kubiak calls plays for MIN despite being OC). Verified caller-vs-OC
capture via spot-checks (Shanahan/McVay/Reid/Payton/LaFleur/Reich all labeled HC-callers). Confirmed IDs
(URL stem `yardbarker.com/nfl/articles/ranking_the_offensive_play_caller[s]_for[from]_each[every]_nfl_team/`):
- **2020**: `s1__32555903` (updated Oct 22 2020) — all 32, best caller-vs-OC labeling of the set
- **2021**: `s1__35857394` (updated Oct 18 2021) — all 32, clear HC titles
- **2022**: `s1__37978942` (updated Dec 5 2022) — all 32, HC-callers flagged but labeling less consistent
- **2024**: `s1_17304_40001199` ("Ranking Every NFL Offensive Play-Caller Entering 2024 Offseason")
- Fetchable via WebFetch in ONE call each (WebFetch pulled all 32 per page; slideshow didn't require paging).
- Series appears to START in 2020 — **NO dedicated 2019 edition surfaced** (~2 targeted searches). The 2020
  edition discusses 2019 performance in prose but ranks who calls plays *entering 2020*, so it is a proxy,
  not a 2019 in-season snapshot.
- PFF "best offensive play callers 2022" (`pff.com/news/nfl-ranking-best-offensive-play-callers-2022`) is
  only a ~6-team top listicle, NOT an all-32 roundup — don't use it for backfill.
**Cheapness**: 2020/2021/2022 = CHEAP (1 Yardbarker fetch/year, caller distinction present). 2022
specifically IS cheaply recoverable (s1__37978942). 2019 = the one gap; needs the 2020 proxy or per-team
work. Caveat: prose slideshows, so extraction = read each entry (no clean table), and these are Yardbarker
editorial rankings, not an authority — spot-check a couple HC-caller teams per year before trusting.

## Verified 2023 + 2024 Week-1 play-callers (fetched 2026-07-19, ESPN preseason+midseason roundups)
Base = ESPN preseason all-32 (2023: id 38108724, 2024: id 41018846). Mid-season catches from ESPN
2024-midseason (id 42466407) + targeted searches (no ESPN 2023-midseason roundup exists — reconstructed
2023 in-season changes via team-site/NFL.com searches).
- **2023 mid-season play-caller changes (5)**: BUF Dorsey→Joe Brady (~Wk11, Dorsey fired Nov 14);
  CAR Reich(Wk1)→Thomas Brown(Wk8-9 bye handoff)→Reich took back→Reich fired Nov 27, Brown resumed — messy;
  LV McDaniels→Bo Hardegree (QB coach, Wk9, McDaniels fired Oct 31); PIT Canada→Mike Sullivan (QB coach,
  Wk12, Canada fired Nov 21); NYG Kafka→Daboll partial/late (murky, revoked "at times", no clean week).
- **2024 mid-season play-caller changes (4)**: NYJ Hackett→Todd Downing (Wk6); CLE Stefanski→Ken Dorsey
  (Wk8); CHI Waldron→Thomas Brown (after Wk9, Waldron fired); LV Getsy→Scott Turner interim (after Wk10).
- **HC-caller counts ran HIGH both years** (2023 ≈15, 2024 ≈14 per ESPN's explicit labels) — the "8-10"
  rule of thumb undercounts these two seasons. High count = safe direction (default-to-OC error gives ~0).
- 2023 OC-callers under defensive HCs (caller=OC, ESPN-confirmed not inferred): BUF Dorsey, NE O'Brien,
  NYJ Hackett, BAL Monken, PIT Canada, HOU Slowik, TEN Tim Kelly, LAC Kellen Moore, NO Carmichael,
  TB Canales, ARI Petzing, SEA Waldron, WAS Bieniemy, PHI Brian Johnson, CHI Getsy, DET Ben Johnson, NYG Kafka.
- 2024 JAX flipped to OC-caller: Pederson handed play-calling to Press Taylor (was HC-caller in 2023).

## Verified Week-1 play-callers 2020/2021/2022 (compiled 2026-07-19, Yardbarker roundups + targeted confirms)
Base = Yardbarker s1__32555903 (2020), s1__35857394 (2021), s1__37978942 (2022). HC-caller counts:
2020=13, 2021=13, 2022=14 (all healthy — no OC-default failure).
**Yardbarker labeling errors caught & fixed:** HOU 2021 listed Tim Kelly as "Head Coach" — he was OC
(Culley was HC); caller name right, title wrong. PHI 2021/2022 listed Sirianni as HC-caller — only true
for 2021 Wk1; Steichen took over ~Wk8 2021 and was full-time caller in 2022 (CBS/NBC confirmed).
**Mid-season play-caller changes (store Wk1 caller):**
- 2020: NONE that changed the caller — ATL/HOU/DET fired their HC (Quinn Wk5, O'Brien Wk4, Patricia Wk12)
  but the OC play-caller (Koetter/Kelly/Bevell) was unchanged. Good example that HC firing ≠ caller change.
- 2021: LV Gruden(Wk1-5)→Greg Olson Wk6 (Gruden resigned); NYG Garrett(Wk1-11)→Freddie Kitchens Wk12
  (Garrett fired Nov 23); CHI Nagy(Wk1-3)→Bill Lazor Wk4 (messy, Nagy took back at times); PHI
  Sirianni(Wk1-7)→Steichen ~Wk8 (after 2-5 LV loss); CAR Brady(Wk1-13)→Jeff Nixon final 5 (Brady fired
  Dec 5). JAX Meyer fired Dec but Bevell called plays all year (no change).
- 2022: IND Reich(Wk1)→Parks Frazier (Reich fired ~Wk9, interim HC Saturday); DEN Hackett(Wk1)→Klint
  Kubiak Wk11 (Nov 20, QB coach). CAR Rhule fired Wk5 but McAdoo called plays all year (no change).
**Soft/edge cases (kept with note, not null):** MIN 2020 Gary Kubiak = OC who calls plays (Yardbarker's
own flagged edge case). MIA 2021 co-OCs Godsey+Studesville, Godsey primary caller. NE 2022 Matt Patricia
de facto caller, no OC title (Belichick delegated; Judge was QB coach). NYG 2022 Kafka designated caller
but Daboll (HC) took over at times. CIN 2020-2022 Zac Taylor calls plays (Callahan OC, does not).
Full 32×3 table delivered to parent; no nulls needed — all three seasons well-documented.

## Verified play-callers (fetched 2026-07-15)
| Team | 2025 | 2026 |
|------|------|------|
| DAL | Brian Schottenheimer (HC) | Brian Schottenheimer |
| NYG | Mike Kafka all season (OC→interim HC wk11) | Matt Nagy (OC) |
| PHI | Kevin Patullo (OC) | Sean Mannion (OC) — Sirianni has never called plays |
| WAS | Kliff Kingsbury (OC) | David Blough (OC) |
| CHI | Ben Johnson (HC) — Doyle OC, did NOT call | Ben Johnson — Press Taylor OC, does NOT call |
| DET | **John Morton wks1-9 → Dan Campbell wks10-18** | **DISPUTED** — Petzing expected, Campbell uncommitted |
| GB | Matt LaFleur (HC) | Matt LaFleur |
| MIN | Kevin O'Connell (HC) | Kevin O'Connell |
| HOU | Nick Caley (OC, 1st time calling plays) | Nick Caley |
| IND | Shane Steichen (HC) — Cooter OC, does NOT call | Shane Steichen |
| JAX | Liam Coen (HC) — Udinski OC, does NOT call | Liam Coen |
| TEN | **Callahan wks1-3 → Bo Hardegree (QB coach) wks4-18** | Brian Daboll (medium conf.) |
| DEN | Sean Payton (HC) | **Davis Webb** (Payton still calls some) |
| KC | Andy Reid (HC) — Nagy OC, never sole caller | Andy Reid |
| LAC | Greg Roman (OC, fired Jan 2026) | Mike McDaniel (OC) |
| LV | **Chip Kelly wks1-11 → Greg Olson wks12-18** | Klint Kubiak (HC) |
| ATL | Zac Robinson (OC) | Tommy Rees (OC) — HC Stefanski confirmed |
| CAR | Dave Canales (HC) | Brad Idzik (OC) — Canales handed it off |
| NO | Kellen Moore (HC) — Nussmeier OC, does NOT call | Kellen Moore (continuity only, medium) |
| TB | Josh Grizzard (OC) | Zac Robinson (OC) |
| ARI | Drew Petzing (OC) | Mike LaFleur (HC) — Hackett OC, does NOT call |
| LAR | Sean McVay (HC) | Sean McVay (continuity only, medium) |
| SF | Kyle Shanahan (HC) | Kyle Shanahan |
| SEA | Klint Kubiak (OC) | Brian Fleury (OC, 1st time calling at any level) |

## Traps found in this sweep
- **TEN 2025 is the worst case in the league**: OC Nick Holz never called plays *at any point*. HC Callahan
  called them wks 1-3, then handed the sheet to the **QB coach** Bo Hardegree from wk 4; when Callahan was
  fired (Oct 13) and Mike McCoy took over as interim HC, McCoy **kept Hardegree** as caller despite his own
  play-calling history. Both an OC-inference and an HC-inference produce a wrong answer here.
- **LV 2025 changed mid-season**: Chip Kelly (OC) called plays for 11 games; after the Wk12 Browns loss
  (Nov 23-24) Greg Olson took over. Any single-name 2025 LV value is wrong.
- **DEN 2026 is a partial delegation**, not a clean handoff: Webb is "primary play-caller" but Payton said
  he "would still call some plays on game days." A binary play_caller field loses this.
- **LAC 2026: Mike McDaniel is the OC, NOT the head coach** — Jim Harbaugh was retained. Easy to get wrong
  since McDaniel was a fired HC (MIA). Chargers.com never states plainly that McDaniel calls plays; the
  only explicit line is "The opportunity to be the offensive playcaller was one McDaniel couldn't turn down."
- KC/IND/JAX are all HC-called offenses where a well-regarded OC exists — exactly the shape that fools an
  OC-based inference (Nagy, Cooter, Udinski all do not call plays).
- **NYG 2025 is the inverse trap of TEN**: the HC was fired (Daboll, Nov 10) and the OC *title* moved
  (Kafka → interim HC, TE coach Tim Kelly → interim OC), yet the **play-caller never changed** — Kafka
  called plays wks 1-18. giants.com: "Kafka... will continue to call plays." A staff-churn heuristic
  flags this as a change; the play-calling field must show continuity. Note Daboll *did* call plays in
  2024, so the 2024→2025 transition is the real change year.
- **DET 2026 is the one cell that must stay `unknown`**: Campbell took play-calling from Morton in wk10
  2025 and, as of July 2026, "told reporters he hadn't made up his mind" about 2026. ESPN's new-coordinator
  piece pointedly says Campbell "retains his overarching influence" without assigning calling duties, while
  CBS labels Petzing the play-caller. Sources conflict → do not encode a name until Sept 2026.
- **PHI: Sirianni has never called plays in any season since 2021** — Mannion is his *sixth* play-caller in
  six years. So a PHI OC change is always a real play-caller change, never nominal. This is the opposite of
  LAR/CAR, where OC churn happens under a play-calling HC.
- **A "first time calling plays" phrase is the strongest available evidence** when no source says "X calls
  plays" outright — it establishes the caller by implication (used for PHI 2026 Mannion, HOU 2025 Caley,
  SEA 2026 Fleury). Team sites often never state the obvious incumbent case plainly.
- **Zac Robinson moves ATL→TB for 2026 while Tommy Rees moves into ATL** — a caller swap between two teams
  in the same division. Joining on coach name alone across seasons will scramble these two teams.
- **"New OC" ≠ "new play-caller", in BOTH directions.** CAR 2026 keeps the same HC but changes caller
  (Canales→Idzik). TB 2026 changes OC *and* caller. LAR/SF change OC but the caller (McVay/Shanahan) is
  unchanged. The OC field carries no information about the caller field in either direction.
- **Beware SI/team-site articles that discuss a coach's "play-calling philosophy" without ever stating he
  calls plays** — the SI Bucs piece on "Zac Robinson's playcalling" never actually says he is TB's 2026
  caller. Headline verbs are not evidence; require a declarative sentence.
- **LAR and NO 2026 could not be explicitly sourced** (July 2026). therams.com's 2026 staff page, ESPN's
  Scheelhaase promotion piece, and Nussmeier's official bio all describe roles without ever naming the
  caller. Turf Show Times / Canal Street Chronicles (both SB Nation) 403. Recheck in Sept 2026.
