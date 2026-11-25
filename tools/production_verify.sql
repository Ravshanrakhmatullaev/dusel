-- DUSEL — production bazasini tekshirish (Supabase SQL editor, faqat o'qish). Har qator 'OK' bo'lishi shart.
-- Admin hali yaratilmagan bo'lsa ham ishlaydi (ci_readiness ADMIN talab qiladi).
with k(tekshiruv, ok, qiymat) as (values
  ('muhit = PRODUCTION', (select value #>> '{}' from checkin.settings where key='environment') = 'PRODUCTION', (select value #>> '{}' from checkin.settings where key='environment')),
  ('biletlar = 11222', (select count(*) from checkin.tickets) = 11222, (select count(*)::text from checkin.tickets)),
  ('master sha256', (select value #>> '{}' from checkin.settings where key='master_sha256') = 'e50b9a597d5e7f5f74a3270ad6689968c8f1572c3a2fbdeac71eadc417b831bb', (select value #>> '{}' from checkin.settings where key='master_sha256')),
  ('bosma varaq sha256', (select value #>> '{}' from checkin.settings where key='print_layout_sha256') = '3e35be16c86f445b1c551b46f5a11add694a9c0d6f42790c405a1dce472e13d4', (select value #>> '{}' from checkin.settings where key='print_layout_sha256')),
  ('hamma bilet NOT_ADMITTED', not exists (select 1 from checkin.tickets where status <> 'NOT_ADMITTED'), (select count(*)::text from checkin.tickets where status <> 'NOT_ADMITTED')),
  ('kirish hodisalari = 0', not exists (select 1 from checkin.admission_events), (select count(*)::text from checkin.admission_events)),
  ('almashtirishlar = 0', not exists (select 1 from checkin.replacements), (select count(*)::text from checkin.replacements)),
  ('holatlar = 0', not exists (select 1 from checkin.review_cases), (select count(*)::text from checkin.review_cases)),
  ('zaxira joylar = 0', not exists (select 1 from checkin.seats where spare_status <> 'NONE'), (select count(*)::text from checkin.seats where spare_status <> 'NONE')),
  ('EXTRA joylar = 0', not exists (select 1 from checkin.seats where origin = 'EXTRA'), (select count(*)::text from checkin.seats where origin = 'EXTRA')),
  ('sig''im = 11222', (select value #>> '{}' from checkin.settings where key='capacity') = '11222', (select value #>> '{}' from checkin.settings where key='capacity')),
  ('kirish YOPIQ', (select value #>> '{}' from checkin.settings where key='admission_open') = 'false', (select value #>> '{}' from checkin.settings where key='admission_open')),
  ('sinov xodimlari yo''q', not exists (select 1 from checkin.staff where username ~* '(@dusel\.test|@test\.local|^load-|^load[0-9])'), (select count(*)::text from checkin.staff where username ~* '(@dusel\.test|@test\.local|^load-|^load[0-9])')),
  ('sinov auth foydalanuvchilari yo''q', not exists (select 1 from auth.users where email ~* '(@dusel\.test|@test\.local|^load-)'), (select count(*)::text from auth.users where email ~* '(@dusel\.test|@test\.local|^load-)')),
  ('RLS hamma checkin jadvalida', not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'checkin' and c.relkind = 'r' and not c.relrowsecurity),
     (select string_agg(c.relname, ',') from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'checkin' and c.relkind = 'r' and not c.relrowsecurity)),
  ('anon ci_* funksiyalarini chaqira olmaydi', not exists (select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' and p.proname like 'ci\_%' and has_function_privilege('anon', p.oid, 'execute')), ''),
  ('bootstrap faqat service_role', not has_function_privilege('authenticated', 'public.ci_staff_bootstrap(jsonb)', 'execute'), '')
)
select case when ok then 'OK' else 'XATO' end as natija, tekshiruv, qiymat from k;
