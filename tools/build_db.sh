#!/usr/bin/env bash
# Rebuild the battery-data database from scratch.
#   tools/build_db.sh [dbname]
# Honours standard PG* environment variables.
set -euo pipefail

DB="${1:-batterydb}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> dropping and recreating ${DB}"
dropdb --if-exists "$DB"
createdb "$DB"

for f in $(ls "$ROOT"/schema/*.sql | sort); do
  printf '    %-34s' "$(basename "$f")"
  if out=$(psql -q -v ON_ERROR_STOP=1 -d "$DB" -f "$f" 2>&1); then
    echo "ok"
  else
    echo "FAILED"
    echo "$out" | head -30
    exit 1
  fi
done

echo "==> schema loaded"
psql -t -d "$DB" -c "
SELECT '    tables: ' || count(*) FROM information_schema.tables
 WHERE table_schema IN ('bd','bd_stage','bd_graph') AND table_type='BASE TABLE';
SELECT '    views:  ' || count(*) FROM information_schema.views
 WHERE table_schema IN ('bd','bd_stage','bd_graph');
SELECT '    quantities: ' || count(*) FROM bd.quantity;"
