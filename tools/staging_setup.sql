-- DUSEL — STAGING branch'ni sinovga tayyorlash (faqat STAGING; production'da xato bilan to'xtaydi).
-- Supabase SQL editor (branch) yoki MCP execute_sql. Sinov xodimlari alohida: tools/create_staff.mjs (staging_staff.csv).
do $$ begin
  if (select value #>> '{}' from checkin.settings where key = 'environment') is distinct from 'STAGING' then
    raise exception 'TO''XTATILDI: bu baza STAGING emas';
  end if;
end $$;
-- yuklama darvozalari L1..L32 va 4 ta haqiqiy darvoza nomi (G1–G4, VIP 004 da bor)
insert into checkin.gates (gate_id, name) select 'L' || i, 'Yuklama ' || i from generate_series(1, 32) i on conflict do nothing;
-- yuklama testida xodim boshiga 10 soniyada 200 so'rov (production standarti 40)
update checkin.settings set value = '200' where key = 'rate_limit_per_10s';
select 'staging tayyor: darvozalar=' || (select count(*) from checkin.gates) || ', rate_limit=' || (select value::text from checkin.settings where key = 'rate_limit_per_10s')
       || ', biletlar=' || (select count(*) from checkin.tickets) || ', kirish_ochiq=' || (select value::text from checkin.settings where key = 'admission_open') as natija;
