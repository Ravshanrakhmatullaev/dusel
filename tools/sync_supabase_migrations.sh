#!/bin/bash
# sql/00N_*.sql (asosiy manba) → supabase/migrations/<vaqt>_*.sql (Supabase branching / CLI uchun).
# Faqat haqiqiy migratsiyalar: sql/local/* (sinov auth taqlidi) va e2e/seed_* (sinov xodimlari) HECH QACHON ko'chirilmaydi.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p supabase/migrations; rm -f supabase/migrations/*.sql
i=0
for f in sql/001_checkin_schema.sql sql/002_checkin_functions.sql sql/003_seed_tickets.sql sql/004_settings_seed.sql sql/005_print_sheets.sql; do
  i=$((i+1)); n=$(basename "$f" .sql | sed 's/^[0-9]*_//')
  cp "$f" "supabase/migrations/2026120100000${i}_${n}.sql"
done
ls supabase/migrations
