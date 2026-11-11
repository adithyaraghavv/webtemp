#!/usr/bin/env bash
# Rebuilds a throwaway local database (schema + seed), starts the local test server on SITE, runs the browser test.
# Usage: ordering/dev/run_e2e.sh SITE_DIR [PHOTO.jpg] [SHOTS_DIR]     (SITE_DIR must already have order/ from `webbuild ordering init`)
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; SITE="$(realpath "$1")"; PHOTO="${2:-}"; SHOTS="${3:-$PWD/shots}"
DB=qrtest; PSQL="runuser -u postgres -- psql -v ON_ERROR_STOP=1 -q"
pg_ctlcluster 16 main start 2>/dev/null || true
$PSQL -d postgres -c "drop database if exists $DB" -c "create database $DB" >/dev/null 2>&1
for f in "$HERE/tests/boot.sql" "$HERE"/../webbuild/ordering_kit/supabase/00*.sql "$HERE/dev/seed.sql"; do $PSQL -d $DB -f "$f" >/dev/null 2>&1; done
pkill -f dev/mock_server.py 2>/dev/null || true; sleep 0.5
STORE="$(mktemp -d)"
QR_SITE="$SITE" QR_STORAGE="$STORE" QR_PSQL="runuser -u postgres -- psql -d $DB" python3 "$HERE/dev/mock_server.py" 8780 >/dev/null 2>&1 &
SRV=$!; trap 'kill $SRV 2>/dev/null; rm -rf "$STORE"' EXIT; sleep 1.5
OUT="$SHOTS" PHOTO="$PHOTO" python3 "$HERE/tests/e2e_browser.py"
