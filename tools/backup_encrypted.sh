#!/bin/bash
# Shifrlangan zaxira nusxa (AES-256, gpg simmetrik) + butunlik tekshiruvi (shifrni ochib, pg_restore --list).
#   DB_URL='postgresql://...' PASSFILE=~/dusel_backup.pass ./tools/backup_encrypted.sh [chiqish_papkasi]
# Parol fayli faqat ofline saqlanadi (2 nusxa: tashkilotchi + texnik rahbar). Zaxira fayllar alohida diskda/bulutda.
set -euo pipefail
: "${DB_URL:?DB_URL kerak}"; : "${PASSFILE:?PASSFILE kerak (parol fayli, kamida 20 belgi)}"
[ "$(wc -c < "$PASSFILE")" -ge 20 ] || { echo "Parol juda qisqa"; exit 2; }
OUT=${1:-backups}; mkdir -p "$OUT"; TS=$(date +%Y%m%d_%H%M%S); F="$OUT/dusel_checkin_$TS.dump.gpg"
pg_dump "$DB_URL" -n checkin -Fc | gpg --batch --yes --pinentry-mode loopback --passphrase-file "$PASSFILE" --symmetric --cipher-algo AES256 -o "$F"
sha256sum "$F" > "$F.sha256"
N=$(gpg --batch -q --pinentry-mode loopback --passphrase-file "$PASSFILE" -d "$F" 2>/dev/null | pg_restore --list 2>/dev/null | grep -c "TABLE DATA checkin" || true)
[ "$N" -ge 10 ] || { echo "XATO: zaxira tekshiruvi o'tmadi ($N jadval)"; exit 3; }
echo "OK $F ($(du -h "$F" | cut -f1), $N jadval ma'lumoti, sha256 $(cut -c1-16 "$F.sha256")…)"
# Tiklash (alohida bazaga!): gpg -d F | pg_restore -d "$RESTORE_DB_URL" --no-owner
