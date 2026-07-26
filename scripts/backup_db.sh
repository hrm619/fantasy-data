#!/usr/bin/env bash
# WAL-safe snapshot of the fantasy-data DB via SQLite's own VACUUM INTO.
#
# The engine runs in WAL mode (db.py), so a plain `cp` of fantasy_data.db can miss commits
# still sitting in the -wal file, or land mid-write. VACUUM INTO goes through SQLite's own
# API and always produces a complete, consistent, compacted snapshot regardless of WAL state.
#
# Usage: scripts/backup_db.sh [dest_dir]   (default: ~/.fantasy-data/backups)
# No retention policy here — prune old snapshots by hand.
set -euo pipefail

DB_PATH="${FANTASY_DATA_DB:-$HOME/.fantasy-data/fantasy_data.db}"
DEST_DIR="${1:-$HOME/.fantasy-data/backups}"

if [ ! -f "$DB_PATH" ]; then
  echo "No DB at $DB_PATH — nothing to back up." >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DEST="$DEST_DIR/fantasy_data-$TIMESTAMP.db"

sqlite3 "$DB_PATH" "VACUUM INTO '$DEST'"
echo "Backed up $DB_PATH -> $DEST"
