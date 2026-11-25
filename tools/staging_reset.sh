#!/bin/bash
# STAGING bazasini noldan tiklash (sinov kirishlari, inventar, holatlar o'chadi; xodimlar saqlanadi).
# PRODUCTION'da ISHLAMAYDI: baza 'environment' sozlamasi STAGING bo'lishi va CONFIRM=STAGING_RESET bo'lishi shart.
#   DB_URL='postgresql://postgres:...@db.<staging-ref>.supabase.co:5432/postgres' CONFIRM=STAGING_RESET ./tools/staging_reset.sh
set -euo pipefail
: "${DB_URL:?DB_URL kerak}"
[ "${CONFIRM:-}" = "STAGING_RESET" ] || { echo "CONFIRM=STAGING_RESET qo'ying"; exit 2; }
DIR="$(cd "$(dirname "$0")/.." && pwd)"; P() { psql -d "$DB_URL" -v ON_ERROR_STOP=1 -q "$@"; }
ENV=$(P -Atc "select value #>> '{}' from checkin.settings where key='environment'")
[ "$ENV" = "STAGING" ] || { echo "TO'XTATILDI: bu baza muhiti '$ENV' (faqat STAGING tozalanadi)"; exit 3; }
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
P -c "\copy (select user_id, username, display_name, role, active from checkin.staff) to '$TMP/staff.csv' csv"
P -c "drop schema checkin cascade" 2>&1 | grep -v NOTICE || true
for f in 001_checkin_schema 002_checkin_functions 003_seed_tickets 004_settings_seed 005_print_sheets; do P -f "$DIR/sql/$f.sql" 2>&1 | grep -v NOTICE || true; done
P -c "\copy checkin.staff (user_id, username, display_name, role, active) from '$TMP/staff.csv' csv"
P -Atc "select 'tiklandi: biletlar=' || count(*) || ', kiritilgan=' || count(*) filter (where status='ADMITTED') from checkin.tickets"
P -Atc "select 'muhit=' || (select value #>> '{}' from checkin.settings where key='environment') || ', kirish_ochiq=' || (select value::text from checkin.settings where key='admission_open') || ', xodimlar=' || (select count(*) from checkin.staff)"
