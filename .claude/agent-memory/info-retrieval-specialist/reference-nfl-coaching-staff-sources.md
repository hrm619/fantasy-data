---
name: reference-nfl-coaching-staff-sources
description: Where to verify NFL head coach / OC by team+season — official team site URL patterns, which sources lie or go stale, and the play-caller gotcha
metadata:
  type: reference
---

Verifying NFL HC/OC per team+season (feeds `coaching_staff` table / `data/coaching_staff_*.json`).

## URL patterns that work (fetched directly, no auth)
- Roster page (most reliable for current season): `https://www.{team}.com/team/coaches-roster/`
  - Confirmed working: steelers.com, bengals.com, newyorkjets.com, patriots.com, miamidolphins.com,
    clevelandbrowns.com, philadelphiaeagles.com, giants.com, dallascowboys.com, commanders.com,
    detroitlions.com, packers.com, vikings.com, atlantafalcons.com, panthers.com, buccaneers.com,
    neworleanssaints.com, azcardinals.com, therams.com, 49ers.com, seahawks.com
  - **chicagobears.com is the exception**: use `/team/coaches/` (no `-roster`), and individual pages
    are `/team/coaches/{first-last}` (not `/team/coaches-roster/{first-last}`).
  - Bonus: these pages state tenure ("his third as offensive coordinator"), which back-dates prior seasons.
- **NFL.com annual hiring-cycle tracker** — the single highest-yield page for a whole-cycle sweep; one
  fetch gave HC+OC+DC hires with dates for all 32 teams:
  `https://www.nfl.com/news/nfl-coaching-gm-tracker-latest-news-interviews-developments-{YEAR}-hiring-cycle`
- Wikipedia `{YEAR}_{Team}_season` infobox — best source for **prior**-season OC and for mid-season
  firings/interims, which team sites erase.

## Known blockers / unreliable sources
- SB Nation sites (baltimorebeatdown.com, cincyjungle.com, etc.) return **HTTP 403 to WebFetch**.
- **Pro-Football-Reference returns HTTP 403 to WebFetch** (`/teams/{abbr}/coaches.htm` confirmed 403 on
  2026-07-15). It is often requested as a preferred source but is not fetchable — substitute the
  Wikipedia season infobox + official team site.
- Individual coach bios (`/team/coaches-roster/{name}`) go stale too: 49ers' Klay Kubiak page still read
  "first year in this role" in July 2026 when Wikipedia + reporting confirmed 2026 was his **second**
  year as OC (promoted Jan 2025). Wikipedia coach pages (`/wiki/{First_Last}`) list role by season and
  often name the play caller — good tiebreaker when a team bio's tenure phrasing looks off.
- **Search-engine AI summaries are actively wrong on this topic — never cite them without fetching.**
  Observed in the 2026 sweep: a summary claimed the Eagles hired Todd Monken as HC (false — Sirianni
  was retained) and that Mike LaFleur was hired as HC by *both* Arizona and Tampa Bay (mutually
  exclusive). Treat search snippets as leads to fetch, never as evidence.
- **Team-site bios go stale mid-offseason.** commanders.com said Dan Quinn "enters his second season"
  in 2026 despite a Feb 2024 hire date on the same page (would be his third). The name was right, the
  tenure phrasing was stale. Cross-check tenure claims against the hire date rather than trusting prose.
- Don't construct news-article URLs by guessing slugs — `/news/eagles-hire-sean-mannion-offensive-coordinator`
  404s. Search for the slug instead.

## Play-caller sources (best-in-class, verified 2026-07-15)
- **ESPN publishes TWO playcaller roundups per season — always fetch BOTH.** The named coach per team
  *is* the play caller by construction (no OC-title inference needed).
  - Preseason: `Who calls plays for every NFL team in {YEAR}?` — 2025 ed. id/46137832 (pub Sept 9, 2025).
  - **Midseason: `Midseason reports on NFL offensive coordinators, playcallers` — 2025 ed. id/46970963
    (pub Nov 17, 2025).** The preseason edition ALONE IS NOT SAFE: it missed Cleveland's Week 10
    Stefanski→Rees handoff and Detroit's Week 9 Morton→Campbell handoff. Mid-season play-caller changes
    are common; a single preseason snapshot silently encodes a wrong full-season value.
- **CBS `Dave Richard's {YEAR} new offensive play-caller rankings`** — enumerates every team with a NEW
  play caller. Useful two ways: a team's presence confirms a change; its *absence* is evidence of
  continuity (CIN's absence in 2026 correctly implied Taylor stayed).
- **Fantasy Index `Ranking the offensive play callers` table — DO NOT TRUST.** It defaults the play
  caller to the OC name: listed Dan Pitcher as CIN's 2026 caller when Taylor explicitly kept it. Its
  HC column was also garbled (showed "head coach Pete Carmichael" for BUF, "head coach Travis Switzer"
  for CLE). It is exactly the OC≠play-caller error this research exists to avoid.
- Official team sites announce play-caller changes as news posts (clevelandbrowns.com carried both the
  "Stefanski to assume play-calling duties again in 2025" and the "Rees to call plays" reversal) but the
  coaches-roster pages never state the play caller. Hire articles (newyorkjets.com Reich, miamidolphins.com
  2026 staff) frequently omit play-calling entirely — absence there is not evidence.

## Gotchas
- **A play caller can change MID-SEASON — a season is not always one name.** CLE 2025 = Stefanski
  (Wks 1–9) then Rees (Wks 10–18). If the schema stores one play caller per team-season, this team is
  unrepresentable; consider a split/`changed_midseason` flag rather than forcing a single value.
- **Recurring false lead: "Zac Taylor handed play-calling to Dan Pitcher."** It has NEVER happened.
  Taylor has called plays since 2019 through 2026. He considered it for 2024 (Callahan) and declined,
  and said in Feb 2026 that giving Pitcher the duties "wasn't on the table." Taylor's own quote —
  "To say he doesn't call plays isn't true… He calls a lot of the plays we run. They are just coming out
  of my mouth" — is what fuels the myth; the collaboration is real but Taylor is the caller.
- **OC ≠ play caller.** Verify separately — a nominal OC change may be no real scheme change, and vice
  versa. Team sites omit the play caller; the nfl.com hire article usually states it. Sometimes no source
  states it (Eagles 2026) — record it as unknown rather than inferring from the OC title.
- **The play-caller can change while the OC does not.** Carolina 2026: Canales and Idzik both stayed, but
  Canales handed play-calling to Idzik. A pure OC-name diff would flag this team as continuous when the
  offense's actual caller turned over. Check the play caller even when both names match year-over-year.
- **Watch near-identical coach names.** Klint Kubiak (SEA 2025 OC → LV HC 2026) vs Klay Kubiak (SF OC
  2025–26) are different people; a fuzzy name match would merge them.
- **Don't infer an OC from who held the job previously.** Giants 2025 OC was Tim Kelly, not Mike Kafka
  (Kafka was the *interim HC* after Daboll's Nov 10 firing). Inference would have produced a wrong flag.
- Coaching changes **cascade**: an OC hired away becomes another team's HC/OC, vacating a seat. When one
  division peer changes, re-verify the rest rather than assuming continuity.
- Team-site roster pages only show the **current** season. For a prior season use tenure phrasing,
  Pro-Football-Reference `/teams/{abbr}/coaches.htm` (HC only), or the Wikipedia season infobox (has OC).

See [[project-2026-coaching-change-research]].
