-- DUSEL — Yulduzli Kecha 2026: bilet check-in (kirish nazorati) tizimi
-- 001: sxema, jadvallar, himoya triggerlari
-- Barcha jadvallar `checkin` sxemasida; to'g'ridan-to'g'ri kirish yo'q (RLS + REVOKE).
-- Ishlash faqat `public.ci_*` SECURITY DEFINER funksiyalari orqali (002).

create schema if not exists checkin;
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;

-- ---------------------------------------------------------------- sozlamalar
create table if not exists checkin.settings (
  key         text primary key,
  value       jsonb not null,
  updated_at  timestamptz not null default now(),
  updated_by  uuid
);

-- ---------------------------------------------------------------- xodimlar
create table if not exists checkin.staff (
  user_id               uuid primary key,              -- auth.users.id
  username              text not null unique,
  display_name          text not null,
  role                  text not null check (role in ('INVENTORY', 'GATE', 'SUPERVISOR', 'ADMIN')),   -- INVENTORY: faqat inventar; GATE: faqat kirish
  active                boolean not null default true,
  sessions_valid_after  timestamptz not null default '2000-01-01',   -- shundan oldingi tokenlar yaroqsiz
  created_at            timestamptz not null default now(),
  created_by            uuid
);

create table if not exists checkin.gates (
  gate_id  text primary key check (gate_id ~ '^[A-Z0-9_-]{1,20}$'),
  name     text not null,
  active   boolean not null default true
);

-- ---------------------------------------------------------------- o'rindiqlar
create table if not exists checkin.seats (
  seat_key           text primary key,                 -- KIND:SEKTOR:QATOR:JOY
  kind               text not null check (kind in ('SEKTOR', 'BLITCHER')),
  zone               text not null,
  sector             text not null,
  row_no             int  not null check (row_no between 1 and 99),
  seat_no            int  not null check (seat_no between 1 and 999),
  origin             text not null default 'MASTER' check (origin in ('MASTER', 'EXTRA')),
  spare_status       text not null default 'NONE' check (spare_status in ('NONE', 'AVAILABLE', 'RESERVED', 'ASSIGNED')),
  spare_note         text,
  spare_verified_by  uuid,
  spare_verified_at  timestamptz,
  reserved_case      bigint,
  reserved_by        uuid,
  reserved_at        timestamptz,
  unique (kind, sector, row_no, seat_no)
);

-- ---------------------------------------------------------------- biletlar (11 222 ta asl yozuv)
create table if not exists checkin.tickets (
  ticket_no          text primary key check (ticket_no ~ '^[0-9]{5}$'),
  seat_key           text not null unique references checkin.seats (seat_key),
  zone               text not null,
  kind               text not null,
  sector             text not null,
  row_no             int  not null,
  seat_no            int  not null,
  status             text not null default 'NOT_ADMITTED'
                     check (status in ('NOT_ADMITTED', 'ADMITTED', 'HELD_FOR_REVIEW', 'CANCELLED_BY_AUTHORIZED_SUPERVISOR')),
  admitted_at        timestamptz,
  admitted_gate      text,
  admitted_by        uuid,
  admitted_device    text,
  admit_request      uuid,
  admitted_offline_at timestamptz,
  status_changed_at  timestamptz,
  status_changed_by  uuid,
  status_reason      text,
  print_page         int,                     -- duseeeeeel_1.pdf varaq raqami (6 bilet/varaq), 005 seed
  print_slot         int,                     -- varaqdagi o'rni 1..6
  retired_to_spare_at timestamptz,            -- isbot bilan zaxiraga o'tkazilgan (ci_spare_from_stock)
  superseded_by_case bigint,                  -- almashtirish bileti uning o'rniga berilgan (asl hali kiritilmagan edi)
  check ((status = 'ADMITTED') = (admitted_at is not null))
);
create index if not exists tickets_print_page on checkin.tickets (print_page);

-- ---------------------------------------------------------------- ko'rib chiqish holatlari
create table if not exists checkin.review_cases (
  id                bigserial primary key,
  ticket_no         text references checkin.tickets (ticket_no),
  replacement_id    uuid,
  source            text not null check (source in ('GATE_REFERRAL', 'DUPLICATE_SCAN', 'HELD_STOCK_SCAN', 'INVENTORY', 'SUPERVISOR', 'OFFLINE_CONFLICT')),
  status            text not null default 'OPEN'
                    check (status in ('OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT', 'RESOLVED_ADMITTED', 'RESOLVED_REPLACEMENT', 'RESOLVED_REJECTED', 'CLOSED')),
  reason            text,
  attempts          int not null default 1,
  last_attempt_at   timestamptz not null default now(),
  gate              text,
  opened_by         uuid,
  opened_at         timestamptz not null default now(),
  customer_ref      text,      -- maxfiy: faqat nazoratchi/admin ko'radi
  evidence_summary  text,
  resolution_note   text,
  resolved_by       uuid,
  resolved_at       timestamptz
);
create unique index if not exists review_cases_one_open_per_ticket
  on checkin.review_cases (ticket_no) where status in ('OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT') and ticket_no is not null;

-- ---------------------------------------------------------------- almashtirilgan (yangi) biletlar
create table if not exists checkin.replacements (
  id                uuid primary key default gen_random_uuid(),
  token_hash        text not null unique,           -- sha256(token); tokenning o'zi saqlanmaydi
  token_hint        text not null,                  -- oxirgi 4 belgi (qidirish uchun)
  original_ticket   text references checkin.tickets (ticket_no),
  case_id           bigint not null references checkin.review_cases (id),
  seat_key          text not null references checkin.seats (seat_key),
  status            text not null default 'ACTIVE' check (status in ('ACTIVE', 'ADMITTED', 'CANCELLED')),
  reason            text not null,
  evidence_summary  text not null,
  issued_by         uuid not null,
  issued_at         timestamptz not null default now(),
  admitted_at       timestamptz,
  admitted_gate     text,
  admitted_by       uuid,
  admitted_device   text,
  admit_request     uuid,
  cancelled_at      timestamptz,
  cancelled_by      uuid,
  cancel_reason     text
);
create unique index if not exists replacements_one_active_per_seat
  on checkin.replacements (seat_key) where status <> 'CANCELLED';

-- ---------------------------------------------------------------- kirish hodisalari (o'zgarmas)
create table if not exists checkin.admission_events (
  id               bigserial primary key,
  request_id       uuid not null unique,               -- idempotentlik: bitta so'rov = bitta yozuv
  credential_type  text not null check (credential_type in ('TICKET', 'REPLACEMENT', 'NONE')),
  ticket_no        text,
  replacement_id   uuid,
  payload_kind     text not null,
  payload_sample   text,
  decision         text not null,
  gate             text,
  device           text,
  staff            uuid,
  at               timestamptz not null default now(),
  offline_at       timestamptz,
  note             text
);
create index if not exists admission_events_ticket on checkin.admission_events (ticket_no);
create index if not exists admission_events_at on checkin.admission_events (at);

-- har bir skan (ko'rish, kirish, inventar) — monitoring va tezlik cheklovi uchun
create table if not exists checkin.scan_log (
  id            bigserial primary key,
  at            timestamptz not null default now(),
  staff         uuid,
  gate          text,
  device        text,
  mode          text not null,
  payload_kind  text,
  ticket_no     text,
  result        text
);
create index if not exists scan_log_staff_at on checkin.scan_log (staff, at);

-- ---------------------------------------------------------------- jismoniy inventar
create table if not exists checkin.inventory_batches (
  id          bigserial primary key,
  name        text not null,
  location    text,
  sector      text,                 -- partiya qaysi sektor/quti/dasta uchun (ixtiyoriy)
  box         text,
  stack       text,
  device      text,
  created_by  uuid not null,
  created_at  timestamptz not null default now(),
  closed_at   timestamptz
);
create table if not exists checkin.inventory_scans (
  id             bigserial primary key,
  request_id     uuid not null unique,
  batch_id       bigint not null references checkin.inventory_batches (id),
  ticket_no      text references checkin.tickets (ticket_no),
  payload_kind   text not null,
  payload_sample text,
  seat_note      text,              -- qog'ozdagi joy QR'dagi master bilan farq qilsa
  seat_mismatch  boolean not null default false,
  operator       uuid not null,
  device         text,
  source         text check (source in ('CAMERA', 'SCANNER', 'MANUAL')),
  client_at      timestamptz,       -- skan qurilmada qachon qilingan (oflayn navbat uchun)
  at             timestamptz not null default now()
);
create index if not exists inventory_scans_ticket on checkin.inventory_scans (ticket_no);
create table if not exists checkin.inventory_voids (
  scan_id    bigint primary key references checkin.inventory_scans (id),
  reason     text not null,
  voided_by  uuid not null,
  voided_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------- tarqatish yozuvlari (ishonchli manbadan import)
create table if not exists checkin.distribution_records (
  id             bigserial primary key,
  ticket_no      text not null references checkin.tickets (ticket_no),
  status         text not null check (status in ('DISTRIBUTED', 'HELD', 'RETURNED')),
  recipient_ref  text,      -- maxfiy
  source         text not null,
  note           text,
  imported_by    uuid not null,
  imported_at    timestamptz not null default now()
);
create index if not exists distribution_ticket on checkin.distribution_records (ticket_no, id desc);

-- ---------------------------------------------------------------- audit jurnali (xesh-zanjir, o'zgarmas)
create table if not exists checkin.audit_log (
  id          bigserial primary key,
  at          timestamptz not null default clock_timestamp(),
  actor       uuid,
  actor_name  text,
  action      text not null,
  entity      text,
  entity_id   text,
  details     jsonb not null default '{}'::jsonb,
  prev_hash   text not null,
  hash        text not null
);

create or replace function checkin._audit_chain() returns trigger
language plpgsql security definer set search_path = checkin, extensions, public, pg_temp as $$
declare v_prev text;
begin
  perform pg_advisory_xact_lock(424242);                     -- zanjir ketma-ketligi
  select hash into v_prev from checkin.audit_log order by id desc limit 1;
  new.prev_hash := coalesce(v_prev, repeat('0', 64));
  new.at := clock_timestamp();
  new.hash := encode(extensions.digest(
      new.prev_hash || '|' || new.id::text || '|' || to_char(new.at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US') || '|' ||
      coalesce(new.actor::text, '') || '|' || new.action || '|' || coalesce(new.entity, '') || '|' ||
      coalesce(new.entity_id, '') || '|' || new.details::text, 'sha256'), 'hex');
  return new;
end $$;
drop trigger if exists audit_chain on checkin.audit_log;
create trigger audit_chain before insert on checkin.audit_log for each row execute function checkin._audit_chain();

create or replace function checkin._immutable() returns trigger language plpgsql as $$
begin
  raise exception 'IMMUTABLE: % jadvalidagi yozuvlarni o''zgartirib/o''chirib bo''lmaydi', tg_table_name;
end $$;
do $$ declare t text; begin
  foreach t in array array['audit_log', 'admission_events', 'inventory_scans', 'inventory_voids', 'distribution_records'] loop
    execute format('drop trigger if exists %I on checkin.%I', 'no_change_' || t, t);
    execute format('create trigger %I before update or delete on checkin.%I for each row execute function checkin._immutable()', 'no_change_' || t, t);
    execute format('drop trigger if exists %I on checkin.%I', 'no_truncate_' || t, t);
    execute format('create trigger %I before truncate on checkin.%I for each statement execute function checkin._immutable()', 'no_truncate_' || t, t);
  end loop;
end $$;

-- ---------------------------------------------------------------- to'g'ridan-to'g'ri kirishni yopish
do $$ declare t text; begin
  for t in select tablename from pg_tables where schemaname = 'checkin' loop
    execute format('alter table checkin.%I enable row level security', t);
  end loop;
end $$;
revoke all on schema checkin from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then execute 'revoke all on schema checkin from anon'; end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then execute 'revoke all on schema checkin from authenticated'; end if;
  revoke all on all tables in schema checkin from public;
  revoke all on all sequences in schema checkin from public;
end $$;

-- ---------------------------------------------------------------- tasdiqlangan sig'im o'zgarishlari (faqat tashkilotchi qarori bilan, o'zgarmas)
create table if not exists checkin.capacity_changes (
  id            bigserial primary key,
  at            timestamptz not null default now(),
  old_value     int not null,
  new_value     int not null,
  approval_ref  text not null,          -- tashkilotchining yozma qarori (sana, raqam, kim imzolagan)
  changed_by    uuid not null
);
alter table checkin.capacity_changes enable row level security;
revoke all on checkin.capacity_changes from public, anon, authenticated;
drop trigger if exists no_change_capacity_changes on checkin.capacity_changes;
create trigger no_change_capacity_changes before update or delete on checkin.capacity_changes for each row execute function checkin._immutable();

-- ============================================================ himoya triggerlari (funksiyalardagi xatoga qarshi ikkinchi qatlam)

-- 1) Tasdiqlangan sig'im va kirish holati faqat maxsus funksiyalar orqali o'zgaradi (migratsiya, seed yoki boshqa funksiya o'zgartira olmaydi)
create or replace function checkin._settings_guard() returns trigger language plpgsql as $$
begin
  if coalesce(old.key, new.key) = 'capacity' and coalesce(current_setting('checkin.capacity_change', true), '') <> 'approved' then
    raise exception 'CAPACITY_LOCKED' using hint = 'Sig''im faqat ci_capacity_change (tashkilotchi qarori) orqali o''zgaradi';
  end if;
  if coalesce(old.key, new.key) = 'admission_open' and coalesce(current_setting('checkin.admission_change', true), '') <> 'approved' then
    raise exception 'ADMISSION_LOCKED' using hint = 'Kirish faqat ci_admission_set orqali ochiladi/yopiladi';
  end if;
  if tg_op = 'DELETE' then return old; end if;
  return new;
end $$;
drop trigger if exists settings_guard on checkin.settings;
create trigger settings_guard before update or delete on checkin.settings for each row execute function checkin._settings_guard();

-- 2) Bilet holati: ADMITTED va CANCELLED — yakuniy. Bilet raqami/joyi o'zgarmaydi.
create or replace function checkin._tickets_guard() returns trigger language plpgsql as $$
begin
  if new.ticket_no <> old.ticket_no or new.seat_key <> old.seat_key or new.sector <> old.sector or new.row_no <> old.row_no or new.seat_no <> old.seat_no then
    raise exception 'TICKET_IDENTITY_IMMUTABLE';
  end if;
  if old.status in ('ADMITTED', 'CANCELLED_BY_AUTHORIZED_SUPERVISOR') and new.status <> old.status then
    raise exception 'TICKET_STATUS_FINAL' using hint = old.status || ' holatidan qaytarib bo''lmaydi';
  end if;
  if old.status = 'ADMITTED' and (new.admitted_at is distinct from old.admitted_at or new.admitted_gate is distinct from old.admitted_gate
                                  or new.admitted_by is distinct from old.admitted_by or new.admit_request is distinct from old.admit_request) then
    raise exception 'ADMISSION_RECORD_IMMUTABLE';
  end if;
  return new;
end $$;
drop trigger if exists tickets_guard on checkin.tickets;
create trigger tickets_guard before update on checkin.tickets for each row execute function checkin._tickets_guard();
drop trigger if exists tickets_no_delete on checkin.tickets;
create trigger tickets_no_delete before delete on checkin.tickets for each row execute function checkin._immutable();

-- 3) Almashtirish: joyda amaldagi bilet bo'lmasligi va jami ruxsatlar tasdiqlangan sig'imdan oshmasligi SHART
create or replace function checkin._replacements_guard() returns trigger language plpgsql security definer set search_path = checkin, pg_temp as $$
declare v_cap int := coalesce((select value::text::int from checkin.settings where key = 'capacity'), 11222);
begin
  if tg_op = 'INSERT' then
    perform pg_advisory_xact_lock(777001);       -- sig'im tekshiruvi parallel INSERT'larda ham ketma-ket
    v_cap := coalesce((select value::text::int from checkin.settings where key = 'capacity'), 11222);   -- qulfdan keyin o'qiladi
    if exists (select 1 from checkin.tickets where seat_key = new.seat_key and status <> 'CANCELLED_BY_AUTHORIZED_SUPERVISOR') then
      raise exception 'SEAT_OCCUPIED_BY_TICKET' using hint = 'Bu joyda amaldagi asl bilet bor';
    end if;
    if checkin._entitlements() + 1 > v_cap then
      raise exception 'CAPACITY_EXCEEDED' using hint = 'Ruxsatlar tasdiqlangan sig''imdan oshadi';
    end if;
    if new.status <> 'ACTIVE' then raise exception 'REPLACEMENT_MUST_START_ACTIVE'; end if;
  else
    if new.token_hash <> old.token_hash or new.seat_key <> old.seat_key or new.case_id <> old.case_id
       or new.original_ticket is distinct from old.original_ticket then
      raise exception 'REPLACEMENT_IDENTITY_IMMUTABLE';
    end if;
    if old.status <> new.status and not (old.status = 'ACTIVE' and new.status in ('ADMITTED', 'CANCELLED')) then
      raise exception 'REPLACEMENT_STATUS_FINAL';
    end if;
  end if;
  return new;
end $$;
drop trigger if exists replacements_guard on checkin.replacements;
create trigger replacements_guard before insert or update on checkin.replacements for each row execute function checkin._replacements_guard();
drop trigger if exists replacements_no_delete on checkin.replacements;
create trigger replacements_no_delete before delete on checkin.replacements for each row execute function checkin._immutable();

-- ---------------------------------------------------------------- INVENTAR ↔ KIRISH qat'iy ajratilgan (baza darajasida)
-- Har bir funksiya tranzaksiya boshida o'z rejimini belgilaydi: checkin.mode = 'INVENTORY' yoki 'ADMISSION'.
-- INVENTORY rejimida bilet holati, kirish hodisasi, almashtirish yoki ko'rib chiqish holatiga yozish — MUMKIN EMAS.
-- Inventar skanini faqat INVENTORY rejimi yoza oladi.
create or replace function checkin._mode_guard() returns trigger language plpgsql as $$
declare v_mode text := coalesce(current_setting('checkin.mode', true), '');
begin
  if tg_table_name in ('inventory_scans', 'inventory_verdicts') then
    if v_mode <> 'INVENTORY' then raise exception 'INVENTORY_WRITE_OUTSIDE_INVENTORY_MODE'; end if;
  elsif v_mode = 'INVENTORY' then
    raise exception 'INVENTORY_MODE_CANNOT_TOUCH_ADMISSION' using hint = tg_table_name || ' jadvaliga inventar rejimida yozib bo''lmaydi';
  end if;
  if tg_op = 'DELETE' then return old; end if;
  return new;
end $$;
do $$ declare t text; begin
  foreach t in array array['tickets', 'admission_events', 'replacements', 'review_cases', 'inventory_scans'] loop
    execute format('drop trigger if exists %I on checkin.%I', 'mode_guard_' || t, t);
    execute format('create trigger %I before insert or update or delete on checkin.%I for each row execute function checkin._mode_guard()', 'mode_guard_' || t, t);
  end loop;
end $$;

-- ---------------------------------------------------------------- inventar: takror skan ≠ ikkinchi qog'oz (operator/nazoratchi qarori, tarix saqlanadi)
-- Bir raqamning birinchi skanidan keyingi har bir skan "takror"; u qaror bo'lmaguncha nusxa hisoblanmaydi.
-- SAME_PAPER — o'sha qog'oz qayta skanerlangan; SECOND_COPY — qo'lda haqiqatan ikkinchi bosma qog'oz bor.
create table if not exists checkin.inventory_verdicts (
  id          bigserial primary key,
  scan_id     bigint not null references checkin.inventory_scans (id),
  verdict     text not null check (verdict in ('SAME_PAPER', 'SECOND_COPY')),
  note        text,
  decided_by  uuid not null,
  at          timestamptz not null default now()
);
create index if not exists inventory_verdicts_scan on checkin.inventory_verdicts (scan_id, id desc);
alter table checkin.inventory_verdicts enable row level security;
revoke all on checkin.inventory_verdicts from public, anon, authenticated;
drop trigger if exists no_change_inventory_verdicts on checkin.inventory_verdicts;
create trigger no_change_inventory_verdicts before update or delete on checkin.inventory_verdicts for each row execute function checkin._immutable();

-- ---------------------------------------------------------------- nazoratchi belgilari: bilet holatini O'ZGARTIRMAYDI (bekor qilmaydi, to'xtatmaydi)
create table if not exists checkin.ticket_flags (
  id           bigserial primary key,
  ticket_no    text not null references checkin.tickets (ticket_no),
  kind         text not null check (kind in ('DUPLICATE_PRINT_CONFIRMED', 'DISTRIBUTION_DISPUTED', 'DISTRIBUTED_BUT_IN_STOCK', 'SEAT_MISMATCH', 'OTHER')),
  details      text,
  source       text not null,             -- INVENTORY | IMPORT | SUPERVISOR
  source_ref   text,
  raised_by    uuid,
  raised_at    timestamptz not null default now(),
  status       text not null default 'OPEN' check (status in ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')),
  case_id      bigint,
  resolution   text,
  resolved_by  uuid,
  resolved_at  timestamptz
);
create unique index if not exists ticket_flags_one_active on checkin.ticket_flags (ticket_no, kind) where status <> 'RESOLVED';
alter table checkin.ticket_flags enable row level security;
revoke all on checkin.ticket_flags from public, anon, authenticated;
drop trigger if exists ticket_flags_no_delete on checkin.ticket_flags;
create trigger ticket_flags_no_delete before delete on checkin.ticket_flags for each row execute function checkin._immutable();
drop trigger if exists mode_guard_inventory_verdicts on checkin.inventory_verdicts;
create trigger mode_guard_inventory_verdicts before insert or update or delete on checkin.inventory_verdicts for each row execute function checkin._mode_guard();
