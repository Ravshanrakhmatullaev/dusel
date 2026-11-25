#!/usr/bin/env python3
"""duseeeeeel_1.pdf tahlilidan (data/print_layout_duseeeeeel_1.csv) varaq/o'rin ma'lumotini SQL'ga aylantiradi.
Har qator master bilan (raqam, tur, sektor, qator, joy) solishtiriladi — bitta farq bo'lsa migratsiya to'xtaydi."""
import csv, hashlib, sys, collections
src = sys.argv[1] if len(sys.argv) > 1 else 'data/print_layout_duseeeeeel_1.csv'
out = sys.argv[2] if len(sys.argv) > 2 else 'sql/005_print_sheets.sql'
rows = list(csv.DictReader(open(src, encoding='utf-8')))
assert len(rows) == 11222 and len({r['TICKET'] for r in rows}) == 11222
slot = collections.Counter(); vals = []
for r in rows:
    p = int(r['PAGE']); slot[p] += 1
    vals.append("('%s',%d,%d,'%s','%s',%d,%d)" % (r['TICKET'], p, slot[p], r['KIND'], r['SECTOR'], int(r['ROW']), int(r['SEAT'])))
sha = hashlib.sha256(open(src, 'rb').read()).hexdigest()
with open(out, 'w', encoding='utf-8') as f:
    f.write("-- 006: bosma varaqlar (duseeeeeel_1.pdf, %d varaq, 6 bilet/varaq). Manba sha256 %s\n" % (len(slot), sha))
    f.write("-- O'z-o'zini tekshiradi: 11 222 qatorning har biri master bilan mos kelmasa — xato, hech narsa yozilmaydi.\n")
    f.write("do $$ declare n int; begin\n  with v(ticket_no, page, slot, kind, sector, row_no, seat_no) as (values\n")
    f.write(",\n".join(vals))
    f.write(")\n  update checkin.tickets t set print_page = v.page, print_slot = v.slot from v\n")
    f.write("   where t.ticket_no = v.ticket_no and t.kind = v.kind and t.sector = v.sector and t.row_no = v.row_no and t.seat_no = v.seat_no\n")
    f.write("     and (t.print_page is distinct from v.page or t.print_slot is distinct from v.slot);\n")
    f.write("  select count(*) into n from checkin.tickets where print_page is not null;\n")
    f.write("  if n <> 11222 then raise exception 'PRINT_LAYOUT_MISMATCH: % / 11222 bilet master bilan mos', n; end if;\n")
    f.write("end $$;\n")
    f.write("insert into checkin.settings (key, value) values ('print_layout_sha256', to_jsonb('%s'::text)) on conflict (key) do nothing;\n" % sha)
print(out, len(vals), sha)
