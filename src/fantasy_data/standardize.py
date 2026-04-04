"""Standardization for team abbreviations, player names, and coach names.

Every value written to the database should pass through this module first.
Import and use these functions in all ingest scripts.
"""

import re

# -- Canonical 32 NFL team abbreviations --------------------------------------

CANONICAL_TEAMS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
}

# Maps variant abbreviations to canonical form
TEAM_VARIANTS: dict[str, str] = {
    # Current canonical (identity mappings)
    "ARI": "ARI", "ATL": "ATL", "BAL": "BAL", "BUF": "BUF",
    "CAR": "CAR", "CHI": "CHI", "CIN": "CIN", "CLE": "CLE",
    "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GB": "GB",
    "HOU": "HOU", "IND": "IND", "JAX": "JAX", "KC": "KC",
    "LAC": "LAC", "LAR": "LAR", "LV": "LV", "MIA": "MIA",
    "MIN": "MIN", "NE": "NE", "NO": "NO", "NYG": "NYG",
    "NYJ": "NYJ", "PHI": "PHI", "PIT": "PIT", "SEA": "SEA",
    "SF": "SF", "TB": "TB", "TEN": "TEN", "WAS": "WAS",
    # Common variants
    "JAC": "JAX",
    "LA": "LAR",
    "OAK": "LV",
    "LVR": "LV",
    "SD": "LAC",
    "STL": "LAR",
    "WSH": "WAS",
    "GBP": "GB",
    "GNB": "GB",
    "KCC": "KC",
    "NOR": "NO",
    "SFO": "SF",
    "TAM": "TB",
    "TBB": "TB",
    "NWE": "NE",
    "CLT": "IND",
    "RAI": "LV",
    "RAM": "LAR",
    "HTX": "HOU",
    "PHO": "ARI",
    "CRD": "ARI",
}

TEAM_FULL_NAMES: dict[str, str] = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys", "DEN": "Denver Broncos",
    "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs",
    "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
    "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings", "NE": "New England Patriots",
    "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers", "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}

TEAM_CITIES: dict[str, str] = {
    "ARI": "Arizona", "ATL": "Atlanta", "BAL": "Baltimore", "BUF": "Buffalo",
    "CAR": "Carolina", "CHI": "Chicago", "CIN": "Cincinnati", "CLE": "Cleveland",
    "DAL": "Dallas", "DEN": "Denver", "DET": "Detroit", "GB": "Green Bay",
    "HOU": "Houston", "IND": "Indianapolis", "JAX": "Jacksonville",
    "KC": "Kansas City", "LAC": "Los Angeles", "LAR": "Los Angeles",
    "LV": "Las Vegas", "MIA": "Miami", "MIN": "Minnesota",
    "NE": "New England", "NO": "New Orleans", "NYG": "New York",
    "NYJ": "New York", "PHI": "Philadelphia", "PIT": "Pittsburgh",
    "SEA": "Seattle", "SF": "San Francisco", "TB": "Tampa Bay",
    "TEN": "Tennessee", "WAS": "Washington",
}


def standardize_team(team: str | None) -> str | None:
    """Normalize any team abbreviation variant to canonical form.

    Returns None for None/empty input. Returns the input unchanged
    if it's not a recognized variant (logs nothing — caller decides).
    """
    if not team:
        return None
    cleaned = team.strip().upper()
    return TEAM_VARIANTS.get(cleaned, cleaned)


# -- Player name standardization ----------------------------------------------

def standardize_player_name(name: str) -> str:
    """Normalize a player name for matching.

    Strips suffixes (Jr, Sr, II–V), removes apostrophes/periods,
    collapses whitespace, lowercases. Used for cross-source matching.
    """
    name = name.strip()
    name = re.sub(r"[.''\u2019]", "", name)
    name = re.sub(r"\s+(Jr|Sr|II|III|IV|V)$", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.lower()


# -- Coach name standardization -----------------------------------------------

def standardize_coach_name(name: str | None) -> str | None:
    """Normalize a coach name for consistency.

    Title-cases, strips whitespace, collapses spaces.
    """
    if not name:
        return None
    name = name.strip()
    name = re.sub(r"\s+", " ", name)
    return name.title()
