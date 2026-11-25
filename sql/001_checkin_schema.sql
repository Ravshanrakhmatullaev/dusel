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
  role                  text not null check (role in ('GATE', 'SUPERVISOR', 'ADMIN')),
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
  check ((status = 'ADMITTED') = (admitted_at is not null))
);

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
