#!/usr/bin/env python3
"""Master CSV (11 222) -> 003_seed_tickets.sql (seats + tickets), ixcham (< 1 MB: Supabase migratsiya chegarasi).
Har bilet bir marta yoziladi; seats va tickets shu ro'yxatdan olinadi. Natija avvalgi to'liq seed bilan bir xil (CI tekshiradi).
Haqiqiy master o'zgartirilmaydi.  python3 tools/gen_seed.py master_v7.csv sql/003_seed_tickets.sql"""
import csv, sys, hashlib
src, out = sys.argv[1], sys.argv[2]
ZONE = {'2-этаж': 2, '4-этаж': 4, 'Блитчеры': 1}
KIND = {'SEKTOR': 'S', 'BLITCHER': 'B'}
rows = list(csv.DictReader(open(src, encoding='utf-8-sig')))
assert len(rows) == 11222 and [r['TICKET_NUMBER'] for r in rows] == [f'{i:05d}' for i in range(1, 11223)]
assert all(r['FIELD1_LABEL'] in KIND and r['ZONE'] in ZONE for r in rows)
sha = hashlib.sha256(open(src, 'rb').read()).hexdigest()
vals = ",\n".join(f"({int(r['TICKET_NUMBER'])},'{KIND[r['FIELD1_LABEL']]}',{ZONE[r['ZONE']]},'{r['SECTOR']}',{int(r['ROW'])},{int(r['SEAT'])})" for r in rows)
sql = f"""-- 11 222 bilet: {src.split('/')[-1]} sha256 {sha}
-- Ixcham shakl: (raqam, tur S/B, zona 1/2/4, sektor, qator, joy). Qayta qo'llash xavfsiz (on conflict do nothing).
-- Tranzaksiyaga bog'liq emas: migratsiya vositasi (Supabase CLI/MCP) o'zi tranzaksiyaga o'raydi; psql bilan ham xavfsiz.
drop table if exists pg_temp._master;
create temp table _master (n int primary key, k char(1), z int, s text, r int, c int);
insert into _master values
{vals};
do $$ begin
  if (select count(*) from _master) <> 11222 or (select count(distinct (k, s, r, c)) from _master) <> 11222 then
    raise exception 'MASTER_INVALID';
  end if;
end $$;
insert into checkin.seats (seat_key, kind, zone, sector, row_no, seat_no)
select kd || ':' || s || ':' || r || ':' || c, kd, zn, s, r, c
from (select *, case k when 'S' then 'SEKTOR' else 'BLITCHER' end kd,
             case z when 2 then '2-qavat' when 4 then '4-qavat' else 'Blitcher (1-qavat)' end zn from _master) m
order by n
on conflict do nothing;
insert into checkin.tickets (ticket_no, seat_key, zone, kind, sector, row_no, seat_no)
select lpad(n::text, 5, '0'), kd || ':' || s || ':' || r || ':' || c, zn, kd, s, r, c
from (select *, case k when 'S' then 'SEKTOR' else 'BLITCHER' end kd,
             case z when 2 then '2-qavat' when 4 then '4-qavat' else 'Blitcher (1-qavat)' end zn from _master) m
order by n
on conflict do nothing;
insert into checkin.settings (key, value) values ('master_sha256', '"{sha}"'::jsonb) on conflict (key) do update set value = excluded.value;
drop table if exists pg_temp._master;
"""
open(out, 'w').write(sql)
print("OK", out, sha, len(sql.encode()), "bayt")
