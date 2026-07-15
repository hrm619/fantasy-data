"""Derive coaching continuity flags by comparing consecutive seasons.

The 2014-2023 records get their flags from `scripts/build_coaching_history.py`;
later seasons were hand-authored in JSON, which is how Las Vegas came to carry
its 2024 staff into 2025 with `hc_continuity_flag = 1` through Pete Carroll's
first year. Deriving the flags from the stored names removes that class of error.

`oc_continuity_flag` tracks the **play caller**, not the OC title, because the
trust weight is a proxy for scheme disruption and the two diverge often: a new
OC under a play-calling head coach is not a scheme change, while an unchanged OC
who takes over play-calling is. Where `play_caller` is unknown for either season,
this falls back to comparing the OC title.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fantasy_data.models import CoachingStaff


def _same(current: str | None, previous: str | None) -> bool | None:
    """Compare two names, returning None when either is unknown."""
    if current is None or previous is None:
        return None
    return current == previous


def _next_tenure(continuous: int, previous_tenure: int | None) -> int:
    """Year with the team: prior count + 1 when continuous, else year one."""
    if not continuous:
        return 1
    return (previous_tenure or 1) + 1


def continuity_flags(current: CoachingStaff, previous: CoachingStaff | None) -> dict[str, int | str]:
    """Derive continuity flags and the basis used for the OC flag.

    With no prior season there is nothing to compare, so both flags are 1 —
    matching `build_coaching_history.py`, which treats a team's first observed
    season as continuous rather than as a change.
    """
    if previous is None:
        return {"hc_continuity_flag": 1, "oc_continuity_flag": 1, "oc_basis": "no_prior_season"}

    hc_same = _same(current.head_coach, previous.head_coach)

    play_caller_same = _same(current.play_caller, previous.play_caller)
    if play_caller_same is None:
        oc_same = _same(current.offensive_coordinator, previous.offensive_coordinator)
        basis = "oc_title_fallback"
    else:
        oc_same = play_caller_same
        basis = "play_caller"

    return {
        "hc_continuity_flag": int(bool(hc_same)) if hc_same is not None else 1,
        "oc_continuity_flag": int(bool(oc_same)) if oc_same is not None else 1,
        "oc_basis": basis,
    }


def compute_coaching_continuity(session: Session, season: int, verbose: bool = True) -> dict[str, int]:
    """Recompute continuity flags for every team in `season` against `season - 1`."""
    stats = {"updated": 0, "hc_changes": 0, "oc_changes": 0, "play_caller_basis": 0, "oc_title_fallback": 0}

    current_rows = session.scalars(select(CoachingStaff).where(CoachingStaff.season == season)).all()
    previous_rows = {
        r.team: r for r in session.scalars(select(CoachingStaff).where(CoachingStaff.season == season - 1))
    }

    for current in current_rows:
        previous = previous_rows.get(current.team)
        flags = continuity_flags(current, previous)
        hc_continuous = int(flags["hc_continuity_flag"])
        oc_continuous = int(flags["oc_continuity_flag"])

        current.hc_continuity_flag = hc_continuous
        current.oc_continuity_flag = oc_continuous

        # Tenure rides on the flags: carry the prior count forward on
        # continuity, otherwise this is year one. Hand-authored tenure is what
        # let Las Vegas claim a third Antonio Pierce year he never coached.
        current.hc_year_with_team = _next_tenure(hc_continuous, previous.hc_year_with_team if previous else None)
        current.oc_year_with_team = _next_tenure(oc_continuous, previous.oc_year_with_team if previous else None)

        stats["updated"] += 1
        stats["hc_changes"] += int(not hc_continuous)
        stats["oc_changes"] += int(not oc_continuous)
        if flags["oc_basis"] == "play_caller":
            stats["play_caller_basis"] += 1
        elif flags["oc_basis"] == "oc_title_fallback":
            stats["oc_title_fallback"] += 1

    session.commit()

    if verbose:
        print(
            f"Coaching continuity {season}: {stats['updated']} teams — "
            f"{stats['hc_changes']} HC changes, {stats['oc_changes']} OC/play-caller changes "
            f"({stats['play_caller_basis']} by play caller, {stats['oc_title_fallback']} by OC title fallback)"
        )

    return stats
