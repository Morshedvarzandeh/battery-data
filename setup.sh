#!/usr/bin/env bash
# =====================================================================
# battery-data : one-command setup
#
#   ./setup.sh              create the database, load everything, test it
#   ./setup.sh --api        ... and then start the read API
#   ./setup.sh --reset      drop and rebuild from scratch
#
# Safe to run twice. Touches nothing outside the database it creates.
# =====================================================================
set -uo pipefail

DB="${BATTERY_DB:-batterydb}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
START_API=0
RESET=0
FAILED=0

for arg in "$@"; do
  case "$arg" in
    --api)   START_API=1 ;;
    --reset) RESET=1 ;;
    -h|--help)
      sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "unknown option: $arg"; exit 2 ;;
  esac
done

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mok\033[0m    %s\n' "$*"; }
warn() { printf '  \033[33mskip\033[0m  %s\n' "$*"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; FAILED=1; }

echo
bold "battery-data setup"
echo  "  repo     : $ROOT"
echo  "  database : $DB"
echo

# ---------------------------------------------------------------------
bold "1. Checking what you have"
# ---------------------------------------------------------------------
if command -v psql >/dev/null 2>&1; then
  ok "psql $(psql --version | awk '{print $3}')"
else
  bad "psql not found."
  cat <<'EOS'

        Postgres is the only hard requirement.

          macOS          brew install postgresql@16 && brew services start postgresql@16
          Ubuntu/Debian  sudo apt install postgresql
          Windows        https://www.postgresql.org/download/windows/

        Or skip installing anything and run:  docker compose up

EOS
  exit 1
fi

if ! psql -l >/dev/null 2>&1; then
  bad "psql is installed but cannot connect to a server."
  cat <<'EOS'

        Start Postgres, or point at one with the standard variables:
          export PGHOST=localhost PGPORT=5432 PGUSER=postgres

EOS
  exit 1
fi
ok "connected to a Postgres server"

PY=""
for c in python3 python; do command -v $c >/dev/null 2>&1 && { PY=$c; break; }; done
if [ -n "$PY" ]; then
  ok "$($PY --version 2>&1)"
else
  warn "python not found - SQL will still work, tooling will not"
fi

have_py_mod() { [ -n "$PY" ] && $PY -c "import $1" >/dev/null 2>&1; }

# ---------------------------------------------------------------------
bold ""
bold "2. Building the database"
# ---------------------------------------------------------------------
if [ "$RESET" = "1" ]; then
  dropdb --if-exists "$DB" 2>/dev/null && ok "dropped existing $DB"
fi

if psql -lqt | cut -d'|' -f1 | grep -qw "$DB"; then
  warn "$DB already exists - rebuilding it (use --reset to be explicit)"
fi

if "$ROOT/tools/build_db.sh" "$DB" >/tmp/bd_build.log 2>&1; then
  ok "schema loaded: $(psql -tAq -d "$DB" -c "
        SELECT count(*)||' tables' FROM information_schema.tables
         WHERE table_schema IN ('bd','bd_stage','bd_graph')
           AND table_type='BASE TABLE';")"
  ok "quantity registry: $(psql -tAq -d "$DB" -c 'SELECT count(*) FROM bd.quantity;') quantities"
else
  bad "schema failed to load - see /tmp/bd_build.log"
  tail -20 /tmp/bd_build.log
  exit 1
fi

if psql -q -v ON_ERROR_STOP=1 -d "$DB" -f "$ROOT/seed/001_reference_cells.sql" \
     >/tmp/bd_seed.log 2>&1; then
  ok "example cells loaded: $(psql -tAq -d "$DB" -c 'SELECT count(*) FROM bd.observation;') observations"
else
  bad "seed failed - see /tmp/bd_seed.log"
fi

psql -q -d "$DB" -c "SELECT bd_graph.refresh();" >/dev/null 2>&1 \
  && ok "graph projection built: $(psql -tAq -d "$DB" -c 'SELECT count(*) FROM bd_graph.node;') nodes, $(psql -tAq -d "$DB" -c 'SELECT count(*) FROM bd_graph.edge;') edges"

# ---------------------------------------------------------------------
bold ""
bold "3. Testing it"
# ---------------------------------------------------------------------
if psql -q -v ON_ERROR_STOP=1 -d "$DB" -f "$ROOT/tests/010_killer_queries.sql" \
     >/tmp/bd_tests.log 2>&1; then
  ok "all 11 demonstration queries ran (output: /tmp/bd_tests.log)"
else
  bad "demonstration queries failed - see /tmp/bd_tests.log"
fi

# The single most important behaviour: does it REFUSE bad data?
if psql -q -d "$DB" -c "
      INSERT INTO bd.observation
        (product_revision_id, quantity_id, value_native, unit_native, provenance_id)
      SELECT pr.id, q.id, 15, 'mohm', pv.id
        FROM bd.product_revision pr, bd.quantity q, bd.provenance pv
       WHERE q.code='internal_resistance_ac' LIMIT 1;" >/dev/null 2>&1; then
  bad "the schema ACCEPTED a resistance with no method or conditions - this is a regression"
else
  ok "refuses uninterpretable data (a resistance with no frequency, SOC or temperature)"
fi

if [ -n "$PY" ]; then
  if have_py_mod pandas && have_py_mod numpy; then
    if $PY "$ROOT/tools/cyclers.py" selftest >/tmp/bd_cyclers.log 2>&1; then
      ok "cycler adapters: Arbin, Maccor, Neware and BDF all round-trip"
    else
      bad "cycler self-test failed - see /tmp/bd_cyclers.log"
    fi
  else
    warn "cycler adapters need: pip install pandas numpy"
  fi

  if $PY "$ROOT/api/filter_grammar.py" >/tmp/bd_filter.log 2>&1; then
    ok "API filter grammar: parsing, type checking and injection safety"
  else
    bad "filter grammar failed - see /tmp/bd_filter.log"
  fi

  if have_py_mod yaml && have_py_mod jsonschema; then
    $PY "$ROOT/tools/dump_quantities.py" "$DB" >/dev/null 2>&1
    if $PY "$ROOT/tools/validate_contrib.py" "$ROOT/contrib" >/tmp/bd_contrib.log 2>&1; then
      ok "contribution validator"
    else
      bad "contribution validation failed - see /tmp/bd_contrib.log"
    fi
  else
    warn "contribution validator needs: pip install pyyaml jsonschema"
  fi

  $PY "$ROOT/tools/export_crosswalk.py" "$DB" >/dev/null 2>&1 \
    && ok "crosswalk exported to crosswalk/ ($(psql -tAq -d "$DB" -c 'SELECT count(*) FROM bd.v_crosswalk;') mappings)"
fi

# ---------------------------------------------------------------------
bold ""
if [ "$FAILED" = "0" ]; then
  bold "Everything works."
else
  bold "Finished with failures - see the FAIL lines above."
fi
cat <<EOS

  Try it:

    psql -d $DB -f tests/010_killer_queries.sql   # the eleven queries, with output
    psql -d $DB -c "SELECT * FROM bd.v_cell_selection;"

  Read next:

    START-HERE.md              what to do with all of this
    docs/02-conventions.md     the actual thinking
    crosswalk/CROSSWALK.md     publishable on its own

EOS

if [ "$START_API" = "1" ]; then
  bold "Starting the API on http://127.0.0.1:8080/v1"
  echo  "  try: curl -G localhost:8080/v1/cells --data-urlencode 'filter=capacity_ah >= 4.5'"
  echo
  exec $PY "$ROOT/api/server.py" --port 8080 --dsn "dbname=$DB"
else
  echo "  Start the API with:  ./setup.sh --api"
  echo
fi

exit $FAILED
