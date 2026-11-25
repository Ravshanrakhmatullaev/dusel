#!/bin/bash
# Sinov bazasini noldan yaratish (faqat lokal/CI). Ulanish: PGHOST/PGPORT/PGUSER/PGPASSWORD muhit o'zgaruvchilari.
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
export PGHOST=${PGHOST:-/tmp} PGPORT=${PGPORT:-5433} PGUSER=${PGUSER:-postgres}
P="psql -v ON_ERROR_STOP=1 -q"
DB=${1:-ci_e2e}
$P -d postgres -c "drop database if exists $DB" -c "create database $DB"
for f in sql/local/000_local_supabase_stub.sql sql/001_checkin_schema.sql sql/002_checkin_functions.sql sql/003_seed_tickets.sql sql/004_settings_seed.sql sql/005_print_sheets.sql ${2:+e2e/seed_e2e.sql}; do
  $P -d $DB -f "$DIR/$f" 2>&1 | grep -v NOTICE || true
done
echo "reset $DB ok"
