"""Convert PFF API JSON exports to CSV for ingest_pff.py.

Reads JSON files captured from PFF's internal API (via browser network tab)
and produces a single CSV. Merges grades files (*-grades.json) with stats
files (*-grades-stats.json) on player_id for comprehensive output.

Usage:
    uv run python scripts/convert_pff_json.py --input-dir data-dev/pff-grades --output data/pff_grades_2025.csv
"""

import json
import argparse
from pathlib import Path

import pandas as pd


def _decode_height(h) -> int | None:
    """PFF encodes height as int: 602 = 6'02" = 74 inches."""
    if h is None or pd.isna(h):
        return None
    h = int(h)
    feet = h // 100
    inches = h % 100
    return feet * 12 + inches


def _load_grades(input_path: Path) -> tuple[pd.DataFrame, int | None]:
    """Load and merge all *-grades.json files (position-level grade data)."""
    all_players = []
    detected_season = None

    for json_file in sorted(input_path.glob("*-grades.json")):
        if "stats" in json_file.name:
            continue  # Skip stats files, handled separately

        with open(json_file) as f:
            data = json.load(f)

        file_season = data.get("season")
        if detected_season is None:
            detected_season = file_season

        for p in data.get("players", []):
            draft = p.get("draft") or {}
            all_players.append({
                "player_id": str(p.get("id", "")),
                "player": p.get("name", ""),
                "position": p.get("position") or p.get("grade_position", ""),
                "team_abbr": p.get("team_name", ""),
                "offense_grade": p.get("offense"),
                "receiving_grade": p.get("receiving"),
                "run_block_grade": p.get("run_block"),
                "pass_block_grade": p.get("pass_block"),
                "rushing_grade": p.get("run"),
                "passing_grade": p.get("pass"),
                "offense_rank": p.get("offense_rank"),
                "offense_snaps": p.get("offense_snaps"),
                "jersey_number": p.get("jersey_number"),
                "age": p.get("age"),
                "height": _decode_height(p.get("height")),
                "weight": p.get("weight"),
                "college": p.get("college"),
                "draft_year": draft.get("season"),
                "draft_round": draft.get("round"),
                "draft_pick": draft.get("selection"),
            })

    return pd.DataFrame(all_players), detected_season


def _extract_stats(data: list[dict], field_map: dict[str, str]) -> pd.DataFrame:
    """Extract specific fields from a PFF stats list, renaming to our schema."""
    rows = []
    for p in data:
        row = {"player_id": str(p.get("player_id", ""))}
        for src_key, dst_key in field_map.items():
            row[dst_key] = p.get(src_key)
        rows.append(row)
    return pd.DataFrame(rows)


def _load_stats(input_path: Path) -> pd.DataFrame:
    """Load and merge all *-grades-stats.json files (detailed per-player stats)."""
    frames = []

    # Receiving stats
    rec_path = input_path / "receiving-grades-stats.json"
    if rec_path.exists():
        with open(rec_path) as f:
            data = json.load(f)
        df = _extract_stats(data.get("receiving_summary", []), {
            "player_game_count": "games",
            "grades_pass_route": "route_grade",
            "drop_rate": "drop_rate",
            "contested_catch_rate": "contested_catch_rate",
            "avg_depth_of_target": "avg_depth_of_target",
            "yprr": "yards_per_route_run",
            "route_rate": "route_participation_rate",
            "caught_percent": "catch_rate_pff",
            "yards_after_catch_per_reception": "yac_per_rec",
            "targeted_qb_rating": "targeted_qb_rating",
            "slot_rate": "slot_rate",
            "wide_rate": "wide_rate",
            "inline_rate": "inline_rate",
            "avoided_tackles": "avoided_tackles_rec",
            "routes": "routes_run",
        })
        frames.append(df)

    # Rushing stats
    rush_path = input_path / "rushing-grades-stats.json"
    if rush_path.exists():
        with open(rush_path) as f:
            data = json.load(f)
        df = _extract_stats(data.get("rushing_summary", []), {
            "player_game_count": "games_rush",
            "elusive_rating": "elusive_rating",
            "yco_attempt": "yards_after_contact_per_att",
            "breakaway_percent": "breakaway_pct",
            "avoided_tackles": "avoided_tackles_rush",
        })
        frames.append(df)

    # Passing stats
    pass_path = input_path / "passing-grades-stats.json"
    if pass_path.exists():
        with open(pass_path) as f:
            data = json.load(f)
        df = _extract_stats(data.get("passing_summary", []), {
            "player_game_count": "games_pass",
            "accuracy_percent": "accuracy_pct",
            "btt_rate": "big_time_throw_rate",
            "twp_rate": "turnover_worthy_play_rate",
            "avg_time_to_throw": "avg_time_to_throw",
            "avg_depth_of_target": "adot_pass",
            "completion_percent": "completion_pct",
        })
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    # Merge all on player_id
    merged = frames[0]
    for df in frames[1:]:
        new_cols = [c for c in df.columns if c not in merged.columns]
        if new_cols:
            merged = merged.merge(df[["player_id"] + new_cols], on="player_id", how="outer")

    return merged


def convert_pff_json(input_dir: str, output: str, season: int | None = None):
    """Convert PFF JSON files to a single CSV for ingest."""
    input_path = Path(input_dir)

    # Load grades (player-level with bio data)
    grades_df, detected_season = _load_grades(input_path)
    print(f"Grades: {len(grades_df)} players from season {detected_season}")

    # Load stats (detailed metrics)
    stats_df = _load_stats(input_path)
    if not stats_df.empty:
        print(f"Stats: {len(stats_df)} player records across receiving/rushing/passing")

    # Merge grades + stats on player_id
    if not stats_df.empty and not grades_df.empty:
        merged = grades_df.merge(stats_df, on="player_id", how="left")
    elif not grades_df.empty:
        merged = grades_df
    else:
        merged = stats_df

    output_season = season or detected_season or "unknown"
    print(f"\nFinal: {len(merged)} players for season {output_season}")
    print(f"  Positions: {merged['position'].value_counts().to_dict()}")

    # Key field coverage
    for field in ["route_grade", "drop_rate", "contested_catch_rate",
                   "yards_per_route_run", "games", "avg_depth_of_target"]:
        if field in merged.columns:
            count = merged[field].notna().sum()
            print(f"  {field}: {count} players")

    merged.to_csv(output, index=False)
    print(f"\n  Output: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert PFF JSON to CSV")
    parser.add_argument("--input-dir", required=True, help="Directory with PFF JSON files")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument("--season", type=int, default=None, help="Override season")
    args = parser.parse_args()
    convert_pff_json(args.input_dir, args.output, args.season)
