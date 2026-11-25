#!/usr/bin/env python3
"""Master CSV (11 222) -> 003_seed_tickets.sql (seats + tickets). Haqiqiy master o'zgartirilmaydi."""
import csv, sys, hashlib
src, out = sys.argv[1], sys.argv[2]
ZONE = {'2-этаж': '2-qavat', '4-этаж': '4-qavat', 'Блитчеры': 'Blitcher (1-qavat)'}
rows = list(csv.DictReader(open(src, encoding='utf-8-sig')))
assert len(rows) == 11222 and [r['TICKET_NUMBER'] for r in rows] == [f'{i:05d}' for i in range(1, 11223)]
sha = hashlib.sha256(open(src, 'rb').read()).hexdigest()
L = [f"-- 11 222 bilet: {src.split('/')[-1]} sha256 {sha}", "begin;"]
def q(s): return "'" + s.replace("'", "''") + "'"
for i in range(0, len(rows), 1000):
    chunk = rows[i:i + 1000]
    L.append("insert into checkin.seats (seat_key, kind, zone, sector, row_no, seat_no) values")
    L.append(",\n".join(f"({q(r['FIELD1_LABEL']+':'+r['SECTOR']+':'+r['ROW']+':'+r['SEAT'])},{q(r['FIELD1_LABEL'])},{q(ZONE[r['ZONE']])},{q(r['SECTOR'])},{int(r['ROW'])},{int(r['SEAT'])})" for r in chunk) + "\non conflict do nothing;")
    L.append("insert into checkin.tickets (ticket_no, seat_key, zone, kind, sector, row_no, seat_no) values")
    L.append(",\n".join(f"({q(r['TICKET_NUMBER'])},{q(r['FIELD1_LABEL']+':'+r['SECTOR']+':'+r['ROW']+':'+r['SEAT'])},{q(ZONE[r['ZONE']])},{q(r['FIELD1_LABEL'])},{q(r['SECTOR'])},{int(r['ROW'])},{int(r['SEAT'])})" for r in chunk) + "\non conflict do nothing;")
L.append(f"insert into checkin.settings (key, value) values ('master_sha256', {q('\"'+sha+'\"')}::jsonb) on conflict (key) do update set value = excluded.value;")
L.append("commit;")
open(out, 'w').write("\n".join(L) + "\n")
print("OK", out, sha)
