-- DUSEL check-in — 002: biznes mantiq (faqat shu funksiyalar orqali ishlanadi)
-- Hammasi SECURITY DEFINER, rol server tomonda tekshiriladi, muhim amallar audit jurnaliga yoziladi.

-- ============================================================ yordamchilar (checkin sxemasi, tashqariga yopiq)

create or replace function checkin._setting(p_key text) returns jsonb
language sql stable security definer set search_path = checkin, pg_temp as $$
  select value from checkin.settings where key = p_key
$$;

create or replace function checkin._me(p_roles text[]) returns checkin.staff
language plpgsql stable security definer set search_path = checkin, extensions, public, pg_temp as $$
declare v checkin.staff; v_iat bigint;
begin
  select * into v from checkin.staff where user_id = auth.uid();
  if v.user_id is null or not v.active then
    raise exception 'AUTH_DENIED' using errcode = '42501', hint = 'Xodim topilmadi yoki faol emas';
  end if;
  v_iat := nullif(auth.jwt() ->> 'iat', '')::bigint;
  if v_iat is null or to_timestamp(v_iat) < v.sessions_valid_after then
    raise exception 'SESSION_REVOKED' using errcode = '42501', hint = 'Sessiya bekor qilingan — qayta kiring';
  end if;
  if not (v.role = any (p_roles)) then
    raise exception 'ROLE_DENIED' using errcode = '42501', hint = 'Bu amal uchun huquq yo''q';
  end if;
  return v;
end $$;

create or replace function checkin._audit(p_me checkin.staff, p_action text, p_entity text, p_entity_id text, p_details jsonb)
returns void language sql security definer set search_path = checkin, pg_temp as $$
  insert into checkin.audit_log (actor, actor_name, action, entity, entity_id, details)
  values (p_me.user_id, p_me.username, p_action, p_entity, p_entity_id, coalesce(p_details, '{}'::jsonb));
$$;

create or replace function checkin._rate(p_me checkin.staff) returns void
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare v_lim int := coalesce((checkin._setting('rate_limit_per_10s'))::text::int, 40); v_n int;
begin
  select count(*) into v_n from checkin.scan_log where staff = p_me.user_id and at > now() - interval '10 seconds';
  if v_n >= v_lim then
    raise exception 'RATE_LIMIT' using errcode = 'P0001', hint = 'Juda tez skanerlash — bir necha soniya kuting';
  end if;
end $$;

-- QR / qo'lda kiritilgan qiymatni qat'iy tahlil qilish. Faqat konsert biletlari va almashtirilgan biletlar qabul qilinadi.
create or replace function checkin._parse(p text, out kind text, out ticket_no text, out token text, out reason text)
language plpgsql immutable as $$
declare s text := btrim(coalesce(p, ''), E' \t\r\n'); m text[];
begin
  if length(s) = 0 or length(s) > 300 then kind := 'INVALID'; reason := 'EMPTY_OR_TOO_LONG'; return; end if;
  m := regexp_match(s, '^DUSELR1:([A-Za-z0-9_-]{24})$');
  if m is not null then kind := 'REPLACEMENT'; token := m[1]; return; end if;
  -- SINOV QR (faqat STAGING'da bilet sifatida qabul qilinadi; production'da yaroqsiz): DUSELTEST:NNNNN yoki tarixiy URL + '&t=SINOV'
  m := regexp_match(s, '^DUSELTEST:([0-9]{5})$');
  if m is null then
    m := regexp_match(s, '^https?://(?:dusel\.pages\.dev/(?:ticket(?:\.html)?|index\.html)?|ravshanrakhmatullaev\.github\.io/dusel/(?:index\.html)?)\?code=([0-9]{5})&t=SINOV$', 'i');
  end if;
  if m is not null then kind := 'TEST'; ticket_no := m[1]; return; end if;
  m := regexp_match(s, '^([0-9]{5})$');                                         -- qo'lda kiritish
  if m is null then                                                            -- barcha tarixiy bilet QR formatlari
    m := regexp_match(s, '^https?://(?:dusel\.pages\.dev/(?:ticket(?:\.html)?|index\.html)?|ravshanrakhmatullaev\.github\.io/dusel/(?:index\.html)?)\?code=([0-9]{5})$', 'i');
  end if;
  if m is not null then
    if m[1]::int between 1 and 11222 then kind := 'TICKET'; ticket_no := m[1];
    else kind := 'INVALID'; reason := 'OUT_OF_RANGE'; end if;
    return;
  end if;
  if s ~* '^https?://dusel\.pages\.dev/(gold|silver|gal|coupon)(\.html)?([/?#]|$)' then
    kind := 'FOREIGN'; reason := 'COUPON_OR_VOUCHER'; return;
  end if;
  kind := 'INVALID'; reason := 'UNKNOWN_FORMAT';
end $$;

-- Muhitga bog'liq tahlil: SINOV QR faqat STAGING'da bilet; boshqa muhitda (PRODUCTION) — yaroqsiz
create or replace function checkin._parse_env(p text, out kind text, out ticket_no text, out token text, out reason text)
language plpgsql stable security definer set search_path = checkin, pg_temp as $$
declare pr record;
begin
  pr := checkin._parse(p); kind := pr.kind; ticket_no := pr.ticket_no; token := pr.token; reason := pr.reason;
  if pr.kind = 'TEST' then
    if (checkin._setting('environment') #>> '{}') = 'STAGING' and pr.ticket_no::int between 1 and 11222 then kind := 'TICKET';
    else kind := 'INVALID'; ticket_no := null; reason := 'TEST_QR_NOT_VALID_HERE'; end if;
  end if;
end $$;

create or replace function checkin._dist(p_ticket text) returns text
language sql stable security definer set search_path = checkin, pg_temp as $$
  select coalesce((select status from checkin.distribution_records where ticket_no = p_ticket order by id desc limit 1), 'UNKNOWN')
$$;

create or replace function checkin._copies(p_ticket text) returns int
language plpgsql stable security definer set search_path = checkin, pg_temp as $$
begin return coalesce((select copies from checkin._live_copies(p_ticket)), 0); end $$;

create or replace function checkin._pending(p_ticket text) returns int
language plpgsql stable security definer set search_path = checkin, pg_temp as $$
begin return coalesce((select pending from checkin._live_copies(p_ticket)), 0); end $$;

create or replace function checkin._flag_text(p_kind text) returns text language sql immutable as $$
  select case p_kind when 'DUPLICATE_PRINT_CONFIRMED' then 'Bosma dublikati tasdiqlangan (inventarda ikkinchi qog''oz) — nazoratchi kuzatuvida'
                     when 'DISTRIBUTION_DISPUTED' then 'Tarqatish yozuvlari ziddiyatli — nazoratchi kuzatuvida'
                     when 'DISTRIBUTED_BUT_IN_STOCK' then 'Tarqatilgan deb yozilgan, lekin qog''ozi zaxirada topilgan'
                     when 'SEAT_MISMATCH' then 'Qog''ozdagi joy masterdan farq qiladi'
                     else 'Nazoratchi belgisi' end
$$;

create or replace function checkin._tz(t timestamptz) returns text language sql immutable as $$
  select to_char(t at time zone 'Asia/Tashkent', 'DD.MM.YYYY HH24:MI:SS')
$$;

create or replace function checkin._ticket_json(t checkin.tickets, p_full boolean default false) returns jsonb
language plpgsql stable security definer set search_path = checkin, pg_temp as $$
declare j jsonb; v_case bigint;
begin
  select id into v_case from checkin.review_cases where ticket_no = t.ticket_no and status in ('OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT') limit 1;
  j := jsonb_build_object(
    'type', 'TICKET', 'ticket_no', t.ticket_no, 'zone', t.zone, 'kind', t.kind, 'sector', t.sector,
    'row', t.row_no, 'seat', t.seat_no, 'status', t.status, 'seat_key', t.seat_key, 'print_sheet', t.print_page,
    'admitted_at', checkin._tz(t.admitted_at), 'admitted_gate', t.admitted_gate,
    'admitted_by', (select username from checkin.staff where user_id = t.admitted_by),
    'distribution', checkin._dist(t.ticket_no), 'inventory_copies', checkin._copies(t.ticket_no),
    'inventory_pending_repeats', checkin._pending(t.ticket_no),
    'open_flags', (select coalesce(jsonb_agg(f.kind order by f.id), '[]') from checkin.ticket_flags f where f.ticket_no = t.ticket_no and f.status <> 'RESOLVED'),
    'open_case', v_case);
  return j;
end $$;

create or replace function checkin._warnings(t checkin.tickets) returns jsonb
language plpgsql stable security definer set search_path = checkin, pg_temp as $$
declare w jsonb := '[]'::jsonb; v_case bigint;
begin
  if t.status = 'ADMITTED' then w := w || jsonb_build_object('code', 'ALREADY_ADMITTED', 'text',
       'Bu bilet allaqachon kiritilgan: ' || checkin._tz(t.admitted_at) || ', ' || coalesce(t.admitted_gate, '?') || '-darvoza'); end if;
  if t.status = 'HELD_FOR_REVIEW' then w := w || jsonb_build_object('code', 'HELD_FOR_REVIEW', 'text', 'Ko''rib chiqish uchun to''xtatilgan — nazoratchiga yuboring'); end if;
  if t.status = 'CANCELLED_BY_AUTHORIZED_SUPERVISOR' then w := w || jsonb_build_object('code', 'CANCELLED', 'text', 'Nazoratchi tomonidan bekor qilingan'); end if;
  if checkin._dist(t.ticket_no) = 'HELD' then w := w || jsonb_build_object('code', 'HELD_STOCK', 'text', 'Tarqatish yozuvida: tashkilotchi zaxirasida (tarqatilmagan)'); end if;
  if checkin._copies(t.ticket_no) > 1 then w := w || jsonb_build_object('code', 'INVENTORY_DUPLICATE', 'text',
       'Inventarda bu raqamning ' || checkin._copies(t.ticket_no) || ' ta jismoniy nusxasi tasdiqlangan (bosmaxona dublikati)'); end if;
  w := w || coalesce((select jsonb_agg(jsonb_build_object('code', 'FLAG_' || f.kind, 'text', checkin._flag_text(f.kind) || ' (belgi #' || f.id || ')') order by f.id)
                      from checkin.ticket_flags f where f.ticket_no = t.ticket_no and f.status <> 'RESOLVED'), '[]'::jsonb);
  select id into v_case from checkin.review_cases where ticket_no = t.ticket_no and status in ('OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT') limit 1;
  if v_case is not null then w := w || jsonb_build_object('code', 'OPEN_CASE', 'text', 'Ochiq ko''rib chiqish holati #' || v_case); end if;
  return w;
end $$;

create or replace function checkin._repl_json(r checkin.replacements) returns jsonb
language sql stable security definer set search_path = checkin, pg_temp as $$
  select jsonb_build_object('type', 'REPLACEMENT', 'replacement_id', r.id, 'token_hint', r.token_hint,
    'original_ticket', r.original_ticket, 'case_id', r.case_id, 'zone', s.zone, 'kind', s.kind, 'sector', s.sector,
    'row', s.row_no, 'seat', s.seat_no, 'status', r.status, 'admitted_at', checkin._tz(r.admitted_at), 'admitted_gate', r.admitted_gate)
  from checkin.seats s where s.seat_key = r.seat_key
$$;

create or replace function checkin._case_touch(p_ticket text, p_source text, p_gate text, p_by uuid, p_reason text) returns bigint
language sql security definer set search_path = checkin, pg_temp as $$
  insert into checkin.review_cases (ticket_no, source, reason, gate, opened_by)
  values (p_ticket, p_source, p_reason, p_gate, p_by)
  on conflict (ticket_no) where status in ('OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT') and ticket_no is not null
  do update set attempts = checkin.review_cases.attempts + 1, last_attempt_at = now()
  returning id
$$;

create or replace function checkin._seat_free(p_seat text) returns boolean
language sql stable security definer set search_path = checkin, pg_temp as $$
  select not exists (select 1 from checkin.tickets where seat_key = p_seat and status <> 'CANCELLED_BY_AUTHORIZED_SUPERVISOR')
     and not exists (select 1 from checkin.replacements where seat_key = p_seat and status <> 'CANCELLED')
$$;

create or replace function checkin._entitlements() returns int
language sql stable security definer set search_path = checkin, pg_temp as $$
  select (select count(*) from checkin.tickets where status <> 'CANCELLED_BY_AUTHORIZED_SUPERVISOR')::int
       + (select count(*) from checkin.replacements where status <> 'CANCELLED')::int
$$;

create or replace function checkin._gate_ok(p_gate text) returns void
language plpgsql stable security definer set search_path = checkin, pg_temp as $$
begin
  if not exists (select 1 from checkin.gates where gate_id = p_gate and active) then
    raise exception 'GATE_INVALID' using errcode = 'P0001', hint = 'Darvoza tanlanmagan yoki faol emas';
  end if;
end $$;

create or replace function checkin._event_json(e checkin.admission_events) returns jsonb
language sql stable security definer set search_path = checkin, pg_temp as $$
  select jsonb_build_object('decision', e.decision, 'request_id', e.request_id, 'at', checkin._tz(e.at), 'gate', e.gate,
                            'ticket_no', e.ticket_no, 'replacement_id', e.replacement_id, 'note', e.note)
$$;

-- ============================================================ xodim: profil, darvozalar
create or replace function public.ci_me() returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['INVENTORY', 'GATE', 'SUPERVISOR', 'ADMIN']);
  return jsonb_build_object('username', me.username, 'display_name', me.display_name, 'role', me.role,
    'environment', checkin._setting('environment'), 'event', checkin._setting('event_label'),
    'admission_open', checkin._setting('admission_open'),
    'gates', (select coalesce(jsonb_agg(jsonb_build_object('gate_id', gate_id, 'name', name) order by gate_id), '[]') from checkin.gates where active),
    'server_time', checkin._tz(now()));
end $$;

-- ============================================================ ko'rish (holatni o'zgartirmaydi)
create or replace function public.ci_lookup(p_payload text, p_gate text, p_device text) returns jsonb
language plpgsql security definer set search_path = checkin, extensions, pg_temp as $$
declare me checkin.staff; pr record; t checkin.tickets; r checkin.replacements; res jsonb;
begin
  me := checkin._me(array['GATE', 'SUPERVISOR', 'ADMIN']);
  perform checkin._rate(me);
  pr := checkin._parse_env(p_payload);
  if pr.kind = 'TICKET' then
    select * into t from checkin.tickets where ticket_no = pr.ticket_no;
    if not found then res := jsonb_build_object('result', 'NOT_FOUND');
    else res := jsonb_build_object('result', 'FOUND', 'credential', checkin._ticket_json(t), 'warnings', checkin._warnings(t),
                 'admissible', t.status = 'NOT_ADMITTED' and not (checkin._dist(t.ticket_no) = 'HELD' and coalesce(checkin._setting('block_held_stock')::text::boolean, true)));
    end if;
  elsif pr.kind = 'REPLACEMENT' then
    select * into r from checkin.replacements where token_hash = encode(extensions.digest(pr.token, 'sha256'), 'hex');
    if not found then res := jsonb_build_object('result', 'NOT_FOUND');
    else res := jsonb_build_object('result', 'FOUND', 'credential', checkin._repl_json(r), 'warnings', '[]'::jsonb, 'admissible', r.status = 'ACTIVE');
    end if;
  elsif pr.kind = 'FOREIGN' then
    res := jsonb_build_object('result', 'FOREIGN', 'message', 'Bu GOLD/SILVER kupon yoki GAL vaucher — konsert bileti EMAS');
  else
    res := jsonb_build_object('result', 'INVALID', 'reason', pr.reason, 'message', 'Konsert bileti QR kodi emas yoki noto''g''ri');
  end if;
  insert into checkin.scan_log (staff, gate, device, mode, payload_kind, ticket_no, result)
  values (me.user_id, p_gate, left(p_device, 80), 'LOOKUP', pr.kind, pr.ticket_no, res ->> 'result');
  return res;
end $$;

-- ============================================================ KIRITISH — atomik, idempotent
create or replace function public.ci_admit(p_request uuid, p_payload text, p_gate text, p_device text, p_offline_at timestamptz default null)
returns jsonb
language plpgsql security definer set search_path = checkin, extensions, pg_temp as $$
declare
  me checkin.staff; pr record; t checkin.tickets; r checkin.replacements; ev checkin.admission_events;
  v_decision text; v_case bigint; v_replay boolean := false; v_cred jsonb; v_prev jsonb; v_hold boolean;
begin
  me := checkin._me(array['GATE', 'SUPERVISOR', 'ADMIN']);
  perform set_config('checkin.mode', 'ADMISSION', true);
  if p_request is null then raise exception 'REQUEST_ID_REQUIRED'; end if;
  -- 1) shu so'rov avval bajarilgan bo'lsa — aynan o'sha natijani qaytaramiz (qayta yuborish / ikki marta bosish)
  select * into ev from checkin.admission_events where request_id = p_request;
  if found then return checkin._event_json(ev) || jsonb_build_object('replay', true); end if;
  perform checkin._rate(me);
  perform checkin._gate_ok(p_gate);
  if p_offline_at is not null then
    -- nazoratli favqulodda rejim: faqat Admin belgilagan YAGONA qurilma va faqat nazoratchi/admin (darvozalar mustaqil oflayn kirita olmaydi)
    if me.role not in ('SUPERVISOR', 'ADMIN') or p_device is distinct from (checkin._setting('contingency_device') #>> '{}') then
      raise exception 'CONTINGENCY_DEVICE_ONLY' using hint = 'Oflayn yozuvni faqat belgilangan nazoratchi qurilmasi yubora oladi';
    end if;
    if p_offline_at > now() + interval '5 minutes' or p_offline_at < now() - interval '2 days' then raise exception 'OFFLINE_TIME_INVALID'; end if;
  end if;
  pr := checkin._parse_env(p_payload);
  v_hold := coalesce(checkin._setting('block_held_stock')::text::boolean, true);

  if not coalesce(checkin._setting('admission_open')::text::boolean, false) then
    v_decision := 'DENIED_ADMISSION_CLOSED';
  elsif pr.kind = 'TICKET' then
    -- ATOMIK: faqat NOT_ADMITTED holatdagi qatorni yangilaydi; parallel so'rovlardan faqat bittasi muvaffaqiyatli bo'ladi
    update checkin.tickets
       set status = 'ADMITTED', admitted_at = now(), admitted_gate = p_gate, admitted_by = me.user_id,
           admitted_device = left(p_device, 80), admit_request = p_request, admitted_offline_at = p_offline_at,
           status_changed_at = now(), status_changed_by = me.user_id
     where ticket_no = pr.ticket_no and status = 'NOT_ADMITTED'
       and not (v_hold and checkin._dist(ticket_no) = 'HELD')
    returning * into t;
    if found then
      v_decision := 'ADMITTED';
    else
      select * into t from checkin.tickets where ticket_no = pr.ticket_no;
      if not found then v_decision := 'DENIED_NOT_FOUND';
      elsif t.status = 'ADMITTED' and t.admit_request = p_request then v_decision := 'ADMITTED'; v_replay := true;
      elsif t.status = 'ADMITTED' then
        v_decision := 'DENIED_ALREADY_ADMITTED';
        v_prev := jsonb_build_object('at', checkin._tz(t.admitted_at), 'gate', t.admitted_gate,
                    'by', (select username from checkin.staff where user_id = t.admitted_by));
        v_case := checkin._case_touch(t.ticket_no, case when p_offline_at is null then 'DUPLICATE_SCAN' else 'OFFLINE_CONFLICT' end,
                    p_gate, me.user_id, 'Takroriy skan: avval ' || checkin._tz(t.admitted_at) || ' ' || coalesce(t.admitted_gate, ''));
      elsif t.status = 'HELD_FOR_REVIEW' then
        v_decision := 'DENIED_HELD_FOR_REVIEW';
        v_case := checkin._case_touch(t.ticket_no, 'GATE_REFERRAL', p_gate, me.user_id, 'To''xtatilgan bilet darvozada');
      elsif t.status = 'CANCELLED_BY_AUTHORIZED_SUPERVISOR' then
        v_decision := 'DENIED_CANCELLED';
        v_case := checkin._case_touch(t.ticket_no, 'GATE_REFERRAL', p_gate, me.user_id, 'Bekor qilingan bilet darvozada');
      else
        v_decision := 'REFER_HELD_STOCK';
        v_case := checkin._case_touch(t.ticket_no, 'HELD_STOCK_SCAN', p_gate, me.user_id, 'Zaxirada deb qayd etilgan bilet darvozada');
      end if;
    end if;
    if t.ticket_no is not null then v_cred := checkin._ticket_json(t); end if;
  elsif pr.kind = 'REPLACEMENT' then
    update checkin.replacements
       set status = 'ADMITTED', admitted_at = now(), admitted_gate = p_gate, admitted_by = me.user_id,
           admitted_device = left(p_device, 80), admit_request = p_request
     where token_hash = encode(extensions.digest(pr.token, 'sha256'), 'hex') and status = 'ACTIVE'
    returning * into r;
    if found then v_decision := 'ADMITTED';
    else
      select * into r from checkin.replacements where token_hash = encode(extensions.digest(pr.token, 'sha256'), 'hex');
      if not found then v_decision := 'DENIED_NOT_FOUND';
      elsif r.status = 'ADMITTED' and r.admit_request = p_request then v_decision := 'ADMITTED'; v_replay := true;
      elsif r.status = 'ADMITTED' then v_decision := 'DENIED_ALREADY_ADMITTED';
        v_prev := jsonb_build_object('at', checkin._tz(r.admitted_at), 'gate', r.admitted_gate);
      else v_decision := 'DENIED_CANCELLED';
      end if;
    end if;
    if r.id is not null then v_cred := checkin._repl_json(r); end if;
  elsif pr.kind = 'FOREIGN' then v_decision := 'DENIED_FOREIGN_SYSTEM';
  else v_decision := 'DENIED_INVALID';
  end if;

  insert into checkin.admission_events (request_id, credential_type, ticket_no, replacement_id, payload_kind, payload_sample,
                                        decision, gate, device, staff, offline_at, note)
  values (p_request, case pr.kind when 'TICKET' then 'TICKET' when 'REPLACEMENT' then 'REPLACEMENT' else 'NONE' end,
          coalesce(t.ticket_no, pr.ticket_no), r.id, pr.kind, left(p_payload, 120), v_decision, p_gate, left(p_device, 80),
          me.user_id, p_offline_at, case when v_replay then 'replay-after-race' end)
  on conflict (request_id) do nothing;
  if not found then          -- shu request_id bilan parallel so'rov allaqachon yozib bo'lgan
    select * into ev from checkin.admission_events where request_id = p_request;
    return checkin._event_json(ev) || jsonb_build_object('replay', true, 'credential', v_cred);
  end if;
  insert into checkin.scan_log (staff, gate, device, mode, payload_kind, ticket_no, result)
  values (me.user_id, p_gate, left(p_device, 80), 'ADMIT', pr.kind, coalesce(t.ticket_no, pr.ticket_no), v_decision);
  perform checkin._audit(me, 'ADMISSION_' || v_decision, case when r.id is not null then 'replacement' else 'ticket' end,
                         coalesce(t.ticket_no, r.id::text, pr.ticket_no),
                         jsonb_build_object('request_id', p_request, 'gate', p_gate, 'device', left(p_device, 80), 'offline_at', p_offline_at, 'case', v_case));
  return jsonb_build_object('decision', v_decision, 'replay', v_replay, 'request_id', p_request, 'credential', v_cred,
                            'previous', v_prev, 'case_id', v_case, 'at', checkin._tz(now()),
                            'message', case pr.kind when 'FOREIGN' then 'Bu GOLD/SILVER kupon yoki GAL vaucher — konsert bileti EMAS'
                                                    when 'INVALID' then 'Konsert bileti QR kodi emas yoki noto''g''ri' end);
end $$;

-- darvoza xodimi muammoli biletni nazoratchiga yuboradi
create or replace function public.ci_refer(p_payload text, p_gate text, p_reason text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; pr record; v_case bigint;
begin
  me := checkin._me(array['GATE', 'SUPERVISOR', 'ADMIN']);
  pr := checkin._parse_env(p_payload);
  if pr.kind <> 'TICKET' then raise exception 'REFER_TICKET_ONLY'; end if;
  v_case := checkin._case_touch(pr.ticket_no, 'GATE_REFERRAL', p_gate, me.user_id, left(coalesce(p_reason, 'Darvozadan yuborildi'), 500));
  perform checkin._audit(me, 'CASE_REFER', 'ticket', pr.ticket_no, jsonb_build_object('case', v_case, 'gate', p_gate, 'reason', p_reason));
  return jsonb_build_object('case_id', v_case);
end $$;

-- ============================================================ NAZORATCHI: holatlar
create or replace function public.ci_cases(p_status text default null) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  return (select coalesce(jsonb_agg(jsonb_build_object(
      'id', c.id, 'ticket_no', c.ticket_no, 'source', c.source, 'status', c.status, 'reason', c.reason, 'attempts', c.attempts,
      'gate', c.gate, 'opened_at', checkin._tz(c.opened_at), 'last_attempt_at', checkin._tz(c.last_attempt_at),
      'sector', t.sector, 'row', t.row_no, 'seat', t.seat_no, 'kind', t.kind, 'ticket_status', t.status) order by c.last_attempt_at desc), '[]')
    from checkin.review_cases c left join checkin.tickets t on t.ticket_no = c.ticket_no
    where p_status is null or c.status = p_status
       or (p_status = 'ACTIVE' and c.status in ('OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT')));
end $$;

create or replace function public.ci_case(p_id bigint) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; c checkin.review_cases; t checkin.tickets;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  select * into c from checkin.review_cases where id = p_id;
  if not found then raise exception 'CASE_NOT_FOUND'; end if;
  select * into t from checkin.tickets where ticket_no = c.ticket_no;
  return jsonb_build_object(
    'case', to_jsonb(c) || jsonb_build_object('opened_at', checkin._tz(c.opened_at), 'resolved_at', checkin._tz(c.resolved_at)),
    'ticket', case when t.ticket_no is not null then checkin._ticket_json(t) end,
    'warnings', case when t.ticket_no is not null then checkin._warnings(t) end,
    'admissions', (select coalesce(jsonb_agg(checkin._event_json(e) || jsonb_build_object('staff', (select username from checkin.staff where user_id = e.staff)) order by e.id), '[]')
                   from checkin.admission_events e where e.ticket_no = c.ticket_no),
    'flags', (select coalesce(jsonb_agg(to_jsonb(f) || jsonb_build_object('text', checkin._flag_text(f.kind), 'raised_at', checkin._tz(f.raised_at)) order by f.id), '[]')
              from checkin.ticket_flags f where f.ticket_no = c.ticket_no),
    'inventory', (select coalesce(jsonb_agg(jsonb_build_object('scan_id', s.id, 'batch', b.name, 'at', checkin._tz(s.at), 'seat_note', s.seat_note,
                       'verdict', (select v.verdict from checkin.inventory_verdicts v where v.scan_id = s.id order by v.id desc limit 1),
                       'voided', exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id)) order by s.id), '[]')
                  from checkin.inventory_scans s join checkin.inventory_batches b on b.id = s.batch_id where s.ticket_no = c.ticket_no),
    'distribution', (select coalesce(jsonb_agg(jsonb_build_object('status', d.status, 'source', d.source, 'recipient_ref', d.recipient_ref,
                       'note', d.note, 'at', checkin._tz(d.imported_at)) order by d.id), '[]') from checkin.distribution_records d where d.ticket_no = c.ticket_no),
    'replacements', (select coalesce(jsonb_agg(checkin._repl_json(r) order by r.issued_at), '[]') from checkin.replacements r where r.case_id = c.id or r.original_ticket = c.ticket_no));
end $$;

create or replace function public.ci_case_update(p_id bigint, p_status text, p_customer_ref text, p_evidence text, p_note text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; c checkin.review_cases;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  if p_status not in ('OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT', 'RESOLVED_REJECTED', 'CLOSED') then raise exception 'STATUS_NOT_ALLOWED'; end if;
  if p_status in ('RESOLVED_REJECTED', 'CLOSED', 'ESCALATED_NO_SEAT') and length(coalesce(p_note, '')) < 5 then raise exception 'NOTE_REQUIRED'; end if;
  update checkin.review_cases set status = p_status,
         customer_ref = coalesce(nullif(p_customer_ref, ''), customer_ref), evidence_summary = coalesce(nullif(p_evidence, ''), evidence_summary),
         resolution_note = coalesce(nullif(p_note, ''), resolution_note),
         resolved_by = case when p_status in ('RESOLVED_REJECTED', 'CLOSED') then me.user_id end,
         resolved_at = case when p_status in ('RESOLVED_REJECTED', 'CLOSED') then now() end
   where id = p_id and status not in ('RESOLVED_ADMITTED', 'RESOLVED_REPLACEMENT', 'RESOLVED_REJECTED', 'CLOSED')
  returning * into c;
  if not found then raise exception 'CASE_NOT_FOUND_OR_CLOSED'; end if;
  perform checkin._audit(me, 'CASE_UPDATE', 'case', p_id::text, jsonb_build_object('status', p_status, 'evidence', p_evidence, 'note', p_note, 'customer_ref_set', p_customer_ref is not null and p_customer_ref <> ''));
  return to_jsonb(c);
end $$;

-- nazoratchi qarori bilan ASL biletni kiritish (faqat hali kiritilmagan / to'xtatilgan bo'lsa)
create or replace function public.ci_supervisor_admit(p_case bigint, p_request uuid, p_gate text, p_device text, p_note text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; c checkin.review_cases; t checkin.tickets; ev checkin.admission_events;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  perform set_config('checkin.mode', 'ADMISSION', true);
  select * into ev from checkin.admission_events where request_id = p_request;
  if found then return checkin._event_json(ev) || jsonb_build_object('replay', true); end if;
  perform checkin._gate_ok(p_gate);
  if length(coalesce(p_note, '')) < 5 then raise exception 'NOTE_REQUIRED'; end if;
  select * into c from checkin.review_cases where id = p_case and status in ('OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT') for update;
  if not found then raise exception 'CASE_NOT_FOUND_OR_CLOSED'; end if;
  update checkin.tickets set status = 'ADMITTED', admitted_at = now(), admitted_gate = p_gate, admitted_by = me.user_id,
         admitted_device = left(p_device, 80), admit_request = p_request, status_changed_at = now(), status_changed_by = me.user_id,
         status_reason = 'Nazoratchi qarori: ' || p_note
   where ticket_no = c.ticket_no and status in ('NOT_ADMITTED', 'HELD_FOR_REVIEW')
  returning * into t;
  if not found then raise exception 'TICKET_NOT_ADMISSIBLE' using hint = 'Bilet allaqachon kiritilgan yoki bekor qilingan — almashtirish kerak'; end if;
  insert into checkin.admission_events (request_id, credential_type, ticket_no, payload_kind, decision, gate, device, staff, note)
  values (p_request, 'TICKET', t.ticket_no, 'SUPERVISOR', 'ADMITTED', p_gate, left(p_device, 80), me.user_id, 'case #' || p_case || ': ' || p_note);
  update checkin.review_cases set status = 'RESOLVED_ADMITTED', resolution_note = p_note, resolved_by = me.user_id, resolved_at = now() where id = p_case;
  perform checkin._audit(me, 'SUPERVISOR_ADMIT', 'ticket', t.ticket_no, jsonb_build_object('case', p_case, 'gate', p_gate, 'note', p_note, 'request_id', p_request));
  return jsonb_build_object('decision', 'ADMITTED', 'credential', checkin._ticket_json(t), 'case_id', p_case);
end $$;

create or replace function public.ci_ticket_set_status(p_ticket text, p_status text, p_reason text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; t checkin.tickets; v_from text[];
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  if length(coalesce(p_reason, '')) < 5 then raise exception 'REASON_REQUIRED'; end if;
  v_from := case p_status
    when 'HELD_FOR_REVIEW' then array['NOT_ADMITTED']
    when 'NOT_ADMITTED' then array['HELD_FOR_REVIEW']                                 -- qayta ochish (bekor qilinganni emas)
    when 'CANCELLED_BY_AUTHORIZED_SUPERVISOR' then array['NOT_ADMITTED', 'HELD_FOR_REVIEW']
    else null end;
  if v_from is null then raise exception 'STATUS_NOT_ALLOWED'; end if;
  update checkin.tickets set status = p_status, status_changed_at = now(), status_changed_by = me.user_id, status_reason = p_reason
   where ticket_no = p_ticket and status = any (v_from) returning * into t;
  if not found then raise exception 'TRANSITION_NOT_ALLOWED' using hint = 'Kiritilgan biletni bekor qilib/to''xtatib bo''lmaydi'; end if;
  perform checkin._audit(me, 'TICKET_STATUS', 'ticket', p_ticket, jsonb_build_object('to', p_status, 'reason', p_reason));
  return checkin._ticket_json(t);
end $$;

-- ============================================================ zaxira o'rindiqlar va almashtirish
create or replace function public.ci_spares(p_sector text default null) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  return (select coalesce(jsonb_agg(jsonb_build_object('seat_key', seat_key, 'kind', kind, 'zone', zone, 'sector', sector, 'row', row_no,
            'seat', seat_no, 'origin', origin, 'spare_status', spare_status, 'reserved_case', reserved_case, 'note', spare_note)
            order by sector, row_no, seat_no), '[]')
          from checkin.seats where spare_status in ('AVAILABLE', 'RESERVED') and (p_sector is null or sector = p_sector));
end $$;

create or replace function public.ci_admin_spare_add(p_kind text, p_zone text, p_sector text, p_row int, p_seat int, p_note text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; v_key text; s checkin.seats;
begin
  me := checkin._me(array['ADMIN']);
  if length(coalesce(p_note, '')) < 5 then raise exception 'NOTE_REQUIRED' using hint = 'Joy qanday tekshirilganini yozing'; end if;
  v_key := upper(p_kind) || ':' || upper(p_sector) || ':' || p_row || ':' || p_seat;
  select * into s from checkin.seats where seat_key = v_key for update;
  if found and s.origin = 'MASTER' then
    if not checkin._seat_free(v_key) then
      raise exception 'SEAT_OCCUPIED' using hint = 'Bu joy amaldagi biletga yoki almashtirishga biriktirilgan';
    end if;
    raise exception 'USE_STOCK_RETIREMENT' using hint = 'Asl joy faqat isbot bilan (ci_spare_from_stock) zaxiraga o''tadi';
  elsif found then
    if s.spare_status <> 'NONE' then raise exception 'ALREADY_SPARE'; end if;
    update checkin.seats set spare_status = 'AVAILABLE', spare_note = p_note, spare_verified_by = me.user_id, spare_verified_at = now()
     where seat_key = v_key returning * into s;
  else
    insert into checkin.seats (seat_key, kind, zone, sector, row_no, seat_no, origin, spare_status, spare_note, spare_verified_by, spare_verified_at)
    values (v_key, upper(p_kind), p_zone, upper(p_sector), p_row, p_seat, 'EXTRA', 'AVAILABLE', p_note, me.user_id, now()) returning * into s;
  end if;
  perform checkin._audit(me, 'SPARE_ADD', 'seat', v_key, jsonb_build_object('origin', s.origin, 'note', p_note,
          'warning', 'EXTRA joy sig''imni oshirmaydi; unga almashtirish faqat sig''imda bo''sh o''rin bo''lsa beriladi'));
  return to_jsonb(s) || jsonb_build_object('headroom', checkin._setting('capacity')::text::int - checkin._entitlements());
end $$;

create or replace function public.ci_admin_spare_remove(p_seat_key text, p_note text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; s checkin.seats;
begin
  me := checkin._me(array['ADMIN']);
  update checkin.seats set spare_status = 'NONE', spare_note = p_note where seat_key = p_seat_key and spare_status = 'AVAILABLE' returning * into s;
  if not found then raise exception 'NOT_AVAILABLE_SPARE'; end if;
  perform checkin._audit(me, 'SPARE_REMOVE', 'seat', p_seat_key, jsonb_build_object('note', p_note));
  return to_jsonb(s);
end $$;

-- ATOMIK band qilish: ikki nazoratchi bir joyni bir vaqtda ololmaydi
create or replace function public.ci_spare_reserve(p_case bigint, p_seat_key text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; s checkin.seats;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  if not exists (select 1 from checkin.review_cases where id = p_case and status in ('OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT')) then
    raise exception 'CASE_NOT_FOUND_OR_CLOSED';
  end if;
  update checkin.seats set spare_status = 'RESERVED', reserved_case = p_case, reserved_by = me.user_id, reserved_at = now()
   where seat_key = p_seat_key and spare_status = 'AVAILABLE' and checkin._seat_free(seat_key)
  returning * into s;
  if not found then raise exception 'SEAT_NOT_AVAILABLE' using hint = 'Joy band, egallangan yoki zaxira ro''yxatida yo''q'; end if;
  perform checkin._audit(me, 'SPARE_RESERVE', 'seat', p_seat_key, jsonb_build_object('case', p_case));
  return to_jsonb(s);
end $$;

create or replace function public.ci_spare_release(p_seat_key text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; s checkin.seats;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  update checkin.seats set spare_status = 'AVAILABLE', reserved_case = null, reserved_by = null, reserved_at = null
   where seat_key = p_seat_key and spare_status = 'RESERVED' returning * into s;
  if not found then raise exception 'NOT_RESERVED'; end if;
  perform checkin._audit(me, 'SPARE_RELEASE', 'seat', p_seat_key, '{}');
  return to_jsonb(s);
end $$;

create or replace function public.ci_issue_replacement(p_case bigint, p_seat_key text, p_reason text, p_evidence text, p_supersede boolean default false)
returns jsonb
language plpgsql security definer set search_path = checkin, extensions, pg_temp as $$
declare me checkin.staff; c checkin.review_cases; s checkin.seats; t checkin.tickets; v_token text; r checkin.replacements;
        v_cap int; v_after int; v_same_seat boolean := false;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  if length(coalesce(p_reason, '')) < 5 or length(coalesce(p_evidence, '')) < 5 then raise exception 'REASON_AND_EVIDENCE_REQUIRED'; end if;
  select * into c from checkin.review_cases where id = p_case and status in ('OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT') for update;
  if not found then raise exception 'CASE_NOT_FOUND_OR_CLOSED'; end if;
  if p_supersede then
    -- asl bilet hali kiritilmagan: yangi xavfsiz QR uning O'RNIGA beriladi (shikastlangan/yo'qolgan bilet). Ruxsatlar soni o'zgarmaydi.
    if c.ticket_no is null then raise exception 'NO_ORIGINAL_TICKET'; end if;
    select * into t from checkin.tickets where ticket_no = c.ticket_no for update;
    if t.status not in ('NOT_ADMITTED', 'HELD_FOR_REVIEW') then
      raise exception 'ORIGINAL_NOT_SUPERSEDABLE' using hint = 'Asl bilet holati: ' || t.status;
    end if;
    v_same_seat := (p_seat_key = t.seat_key);
  end if;
  select * into s from checkin.seats where seat_key = p_seat_key for update;
  if not found then raise exception 'SEAT_NOT_FOUND'; end if;
  if not v_same_seat and (s.spare_status <> 'RESERVED' or s.reserved_case is distinct from p_case) then
    raise exception 'SEAT_NOT_RESERVED_FOR_CASE' using hint = 'Avval joyni shu holat uchun band qiling';
  end if;
  perform pg_advisory_xact_lock(777001);                                    -- sig'im tekshiruvi ketma-ket
  v_cap := coalesce(checkin._setting('capacity')::text::int, 11222);
  v_after := checkin._entitlements() + 1 - case when p_supersede then 1 else 0 end;
  if v_after > v_cap then
    -- sig'im OSHIRILMAYDI: holat tashkilotchiga o'tadi (exception emas — holat saqlanadi)
    update checkin.review_cases set status = 'ESCALATED_NO_SEAT', resolution_note = 'Sig''im to''lgan — tashkilotchi qarori kerak' where id = p_case;
    perform checkin._audit(me, 'REPLACEMENT_CAPACITY_BLOCK', 'case', p_case::text, jsonb_build_object('capacity', v_cap, 'entitlements', checkin._entitlements()));
    return jsonb_build_object('error', 'CAPACITY_EXCEEDED', 'message', 'Ruxsat etilgan sig''im to''lgan — tashkilotchi qarori kerak', 'case_id', p_case);
  end if;
  if p_supersede then
    update checkin.tickets set status = 'CANCELLED_BY_AUTHORIZED_SUPERVISOR', status_changed_at = now(), status_changed_by = me.user_id,
           status_reason = 'SUPERSEDED_BY_REPLACEMENT case #' || p_case || ': ' || p_reason, superseded_by_case = p_case
     where ticket_no = t.ticket_no;
  end if;
  if not checkin._seat_free(p_seat_key) then raise exception 'SEAT_OCCUPIED'; end if;
  v_token := translate(encode(extensions.gen_random_bytes(18), 'base64'), '+/', '-_');   -- 144 bit, taxmin qilib bo'lmaydi
  insert into checkin.replacements (token_hash, token_hint, original_ticket, case_id, seat_key, reason, evidence_summary, issued_by)
  values (encode(extensions.digest(v_token, 'sha256'), 'hex'), right(v_token, 4), c.ticket_no, p_case, p_seat_key, p_reason, p_evidence, me.user_id)
  returning * into r;
  update checkin.seats set spare_status = 'ASSIGNED', reserved_case = p_case where seat_key = p_seat_key;
  update checkin.review_cases set status = 'RESOLVED_REPLACEMENT', evidence_summary = p_evidence, resolution_note = p_reason,
         resolved_by = me.user_id, resolved_at = now() where id = p_case;
  perform checkin._audit(me, 'REPLACEMENT_ISSUE', 'replacement', r.id::text,
          jsonb_build_object('case', p_case, 'original_ticket', c.ticket_no, 'seat', p_seat_key, 'supersede', p_supersede,
                             'reason', p_reason, 'evidence', p_evidence, 'token_hint', r.token_hint));
  return checkin._repl_json(r) || jsonb_build_object('payload', 'DUSELR1:' || v_token, 'superseded_original', p_supersede,
         'notice', 'Token faqat hozir ko''rsatiladi — QR''ni chop eting yoki saqlang');
end $$;

create or replace function public.ci_replacement_cancel(p_id uuid, p_reason text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; r checkin.replacements;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  if length(coalesce(p_reason, '')) < 5 then raise exception 'REASON_REQUIRED'; end if;
  update checkin.replacements set status = 'CANCELLED', cancelled_at = now(), cancelled_by = me.user_id, cancel_reason = p_reason
   where id = p_id and status = 'ACTIVE' returning * into r;
  if not found then raise exception 'NOT_ACTIVE'; end if;
  update checkin.seats set spare_status = 'AVAILABLE', reserved_case = null, reserved_by = null, reserved_at = null where seat_key = r.seat_key;
  perform checkin._audit(me, 'REPLACEMENT_CANCEL', 'replacement', p_id::text, jsonb_build_object('reason', p_reason));
  return checkin._repl_json(r);
end $$;

-- ============================================================ INVENTAR (kirishga ta'sir qilmaydi)
drop function if exists public.ci_inventory_batch_open(text, text);
create or replace function public.ci_inventory_batch_open(p_name text, p_location text, p_sector text default null, p_box text default null, p_stack text default null, p_device text default null) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; b checkin.inventory_batches;
begin
  me := checkin._me(array['INVENTORY', 'SUPERVISOR', 'ADMIN']);
  perform set_config('checkin.mode', 'INVENTORY', true);
  if length(btrim(coalesce(p_name, ''))) < 2 then raise exception 'NAME_REQUIRED'; end if;
  insert into checkin.inventory_batches (name, location, sector, box, stack, device, created_by)
  values (left(btrim(p_name), 100), left(p_location, 100), nullif(upper(btrim(coalesce(p_sector, ''))), ''), left(nullif(btrim(coalesce(p_box, '')), ''), 60),
          left(nullif(btrim(coalesce(p_stack, '')), ''), 60), left(p_device, 80), me.user_id) returning * into b;
  perform checkin._audit(me, 'INVENTORY_BATCH_OPEN', 'batch', b.id::text, jsonb_build_object('name', p_name, 'location', p_location, 'sector', b.sector, 'box', b.box, 'stack', b.stack));
  return to_jsonb(b);
end $$;

create or replace function public.ci_inventory_batch_close(p_batch bigint) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; b checkin.inventory_batches;
begin
  me := checkin._me(array['INVENTORY', 'SUPERVISOR', 'ADMIN']);
  perform set_config('checkin.mode', 'INVENTORY', true);
  update checkin.inventory_batches set closed_at = now()
   where id = p_batch and closed_at is null and (created_by = me.user_id or me.role in ('SUPERVISOR', 'ADMIN')) returning * into b;
  if not found then raise exception 'BATCH_NOT_OPEN' using hint = 'Partiya yopiq yoki boshqa xodimniki'; end if;
  perform checkin._audit(me, 'INVENTORY_BATCH_CLOSE', 'batch', p_batch::text,
          jsonb_build_object('scans', (select count(*) from checkin.inventory_scans where batch_id = p_batch)));
  return to_jsonb(b);
end $$;

create or replace function public.ci_inventory_batches() returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['INVENTORY', 'SUPERVISOR', 'ADMIN']);
  return (select coalesce(jsonb_agg(jsonb_build_object('id', b.id, 'name', b.name, 'location', b.location, 'sector', b.sector, 'box', b.box,
            'stack', b.stack, 'open', b.closed_at is null, 'created_at', checkin._tz(b.created_at), 'closed_at', checkin._tz(b.closed_at),
            'operator', (select username from checkin.staff where user_id = b.created_by), 'mine', b.created_by = me.user_id,
            'scans', (select count(*) from checkin.inventory_scans s where s.batch_id = b.id and s.ticket_no is not null and not exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id)),
            'rejected', (select count(*) from checkin.inventory_scans s where s.batch_id = b.id and s.ticket_no is null))
            order by b.id desc), '[]') from checkin.inventory_batches b);
end $$;

drop function if exists public.ci_inventory_scan(uuid, bigint, text, text);
create or replace function public.ci_inventory_scan(p_request uuid, p_batch bigint, p_payload text, p_seat_note text default null,
                                                    p_source text default null, p_device text default null, p_client_at timestamptz default null) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
-- FAQAT inventar: biletlar, kirish hodisalari, almashtirishlar va holatlarga TEGMAYDI (bundan tashqari _mode_guard trigger buni bazada taqiqlaydi)
declare me checkin.staff; pr record; t checkin.tickets; s checkin.inventory_scans; w jsonb := '[]'::jsonb; v_copies int; v_in_batch int;
        v_replay boolean := false; v_first_dup boolean := false; v_pending int; v_obs int; v_verdict text;
begin
  me := checkin._me(array['INVENTORY', 'SUPERVISOR', 'ADMIN']);
  perform set_config('checkin.mode', 'INVENTORY', true);
  if p_request is null then raise exception 'REQUEST_ID_REQUIRED'; end if;
  if p_source is not null and p_source not in ('CAMERA', 'SCANNER', 'MANUAL') then raise exception 'SOURCE_INVALID'; end if;
  if p_client_at is not null and (p_client_at > now() + interval '5 minutes' or p_client_at < now() - interval '30 days') then raise exception 'CLIENT_TIME_INVALID'; end if;
  select * into s from checkin.inventory_scans where request_id = p_request;
  if found then
    v_replay := true;                                      -- oflayn navbat qayta yuborgan: yangi nusxa qo'shilmaydi
  else
    perform checkin._rate(me);
    if not exists (select 1 from checkin.inventory_batches where id = p_batch and closed_at is null) then raise exception 'BATCH_NOT_OPEN'; end if;
    pr := checkin._parse_env(p_payload);
    insert into checkin.inventory_scans (request_id, batch_id, ticket_no, payload_kind, payload_sample, seat_note, seat_mismatch, operator, device, source, client_at)
    values (p_request, p_batch, case when pr.kind = 'TICKET' then pr.ticket_no end,
            case when pr.kind = 'TICKET' then 'TICKET' else pr.kind end, left(p_payload, 120),
            nullif(btrim(coalesce(p_seat_note, '')), ''), nullif(btrim(coalesce(p_seat_note, '')), '') is not null,
            me.user_id, left(p_device, 80), p_source, p_client_at)
    on conflict (request_id) do nothing returning * into s;
    if s.id is null then select * into s from checkin.inventory_scans where request_id = p_request; v_replay := true; end if;
    insert into checkin.scan_log (staff, gate, device, mode, payload_kind, ticket_no, result)
    values (me.user_id, null, left(p_device, 80), 'INVENTORY', pr.kind, pr.ticket_no, 'RECORDED');
  end if;
  if s.ticket_no is null then
    return jsonb_build_object('result', s.payload_kind, 'scan_id', s.id, 'replay', v_replay,
      'message', case s.payload_kind when 'FOREIGN' then 'GOLD/SILVER/GAL kupon — konsert bileti emas' when 'REPLACEMENT' then 'Almashtirish bileti — inventarga kirmaydi'
                 else 'Noma''lum yoki noto''g''ri QR' end);
  end if;
  select * into t from checkin.tickets where ticket_no = s.ticket_no;
  select coalesce(lc.copies, 0), coalesce(lc.pending, 0) into v_copies, v_pending from checkin._live_copies(t.ticket_no) lc;
  v_copies := coalesce(v_copies, 0); v_pending := coalesce(v_pending, 0);
  select count(*) into v_in_batch from checkin.inventory_scans x where x.ticket_no = t.ticket_no and x.batch_id = s.batch_id
     and not exists (select 1 from checkin.inventory_voids v where v.scan_id = x.id);
  select count(*) into v_obs from checkin.inventory_scans x where x.ticket_no = t.ticket_no and x.id <= s.id
     and not exists (select 1 from checkin.inventory_voids v where v.scan_id = x.id);
  select v.verdict into v_verdict from checkin.inventory_verdicts v where v.scan_id = s.id order by v.id desc limit 1;
  v_first_dup := v_obs = 2 and not v_replay;
  if v_obs > 1 and v_verdict is null then w := w || jsonb_build_object('code', 'REPEAT_NEEDS_VERDICT', 'text',
       'TAKROR SKAN: bu raqam avval ham skanerlangan. Qo''lingizda IKKI xil qog''oz bormi? Qaror bering.'); end if;
  if v_copies > 1 then w := w || jsonb_build_object('code', 'DUPLICATE_COPY', 'text', 'TASDIQLANGAN DUBLIKAT: ' || v_copies || ' ta qog''oz'); end if;
  -- avtomatik belgilar (bilet holatiga tegmaydi)
  if not v_replay and checkin._dist(t.ticket_no) = 'DISTRIBUTED' then
    insert into checkin.ticket_flags (ticket_no, kind, details, source, source_ref, raised_by)
    values (t.ticket_no, 'DISTRIBUTED_BUT_IN_STOCK', 'Inventarda topildi (skan #' || s.id || ')', 'INVENTORY', 'scan:' || s.id, me.user_id)
    on conflict (ticket_no, kind) where status <> 'RESOLVED' do nothing;
  end if;
  if not v_replay and s.seat_mismatch then
    insert into checkin.ticket_flags (ticket_no, kind, details, source, source_ref, raised_by)
    values (t.ticket_no, 'SEAT_MISMATCH', 'Qog''ozda: ' || s.seat_note, 'INVENTORY', 'scan:' || s.id, me.user_id)
    on conflict (ticket_no, kind) where status <> 'RESOLVED' do nothing;
  end if;
  if t.status = 'ADMITTED' then w := w || jsonb_build_object('code', 'ALREADY_ADMITTED', 'text', 'Bu bilet bilan kirish qayd etilgan!'); end if;
  if checkin._dist(t.ticket_no) = 'DISTRIBUTED' then w := w || jsonb_build_object('code', 'RECORDED_DISTRIBUTED', 'text', 'Tarqatilgan deb qayd etilgan, lekin zaxirada turibdi'); end if;
  if s.seat_mismatch then w := w || jsonb_build_object('code', 'SEAT_MISMATCH', 'text', 'Qog''ozdagi joy masterdan farq qiladi: ' || s.seat_note); end if;
  return jsonb_build_object('result', 'RECORDED', 'scan_id', s.id, 'replay', v_replay, 'credential', checkin._ticket_json(t),
                            'copies_total', v_copies, 'confirmed_copies', v_copies, 'pending_repeats', v_pending, 'copies_in_batch', v_in_batch,
                            'observation_no', v_obs, 'repeat', v_obs > 1, 'needs_verdict', v_obs > 1 and v_verdict is null, 'verdict', v_verdict,
                            'first_duplicate', v_first_dup, 'print_sheet', t.print_page, 'warnings', w);
end $$;

create or replace function public.ci_inventory_void(p_scan bigint, p_reason text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  perform set_config('checkin.mode', 'INVENTORY', true);
  if length(coalesce(p_reason, '')) < 3 then raise exception 'REASON_REQUIRED'; end if;
  if not exists (select 1 from checkin.inventory_scans where id = p_scan) then raise exception 'SCAN_NOT_FOUND'; end if;
  insert into checkin.inventory_voids (scan_id, reason, voided_by) values (p_scan, p_reason, me.user_id);
  perform checkin._audit(me, 'INVENTORY_VOID', 'inventory_scan', p_scan::text, jsonb_build_object('reason', p_reason));
  return jsonb_build_object('voided', p_scan);
end $$;

-- Takror skan bo'yicha qaror: SAME_PAPER (o'sha qog'oz) yoki SECOND_COPY (ikkinchi bosma qog'oz). Tarix o'chmaydi; nazoratchi keyin o'zgartira oladi.
create or replace function public.ci_inventory_verdict(p_scan bigint, p_verdict text, p_note text default null) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; s checkin.inventory_scans; v_obs int; v_prev text; lc record;
begin
  me := checkin._me(array['INVENTORY', 'SUPERVISOR', 'ADMIN']);
  perform set_config('checkin.mode', 'INVENTORY', true);
  if p_verdict not in ('SAME_PAPER', 'SECOND_COPY') then raise exception 'VERDICT_INVALID'; end if;
  select * into s from checkin.inventory_scans where id = p_scan for update;
  if not found or s.ticket_no is null then raise exception 'SCAN_NOT_FOUND'; end if;
  if exists (select 1 from checkin.inventory_voids v where v.scan_id = p_scan) then raise exception 'SCAN_VOIDED'; end if;
  select count(*) into v_obs from checkin.inventory_scans x where x.ticket_no = s.ticket_no and x.id <= s.id
     and not exists (select 1 from checkin.inventory_voids v where v.scan_id = x.id);
  if v_obs < 2 then raise exception 'NOT_A_REPEAT' using hint = 'Birinchi skan uchun qaror kerak emas'; end if;
  select verdict into v_prev from checkin.inventory_verdicts where scan_id = p_scan order by id desc limit 1;
  if me.role = 'INVENTORY' then
    if s.operator <> me.user_id then raise exception 'NOT_YOUR_SCAN'; end if;
    if v_prev is not null then raise exception 'ALREADY_DECIDED' using hint = 'O''zgartirish faqat nazoratchi orqali'; end if;
  elsif v_prev is not null and length(btrim(coalesce(p_note, ''))) < 5 then
    raise exception 'NOTE_REQUIRED' using hint = 'Qarorni o''zgartirish sababini yozing';
  end if;
  if p_verdict = 'SECOND_COPY' and length(btrim(coalesce(p_note, ''))) < 2 then
    raise exception 'NOTE_REQUIRED' using hint = 'Ikkinchi qog''oz qayerga qo''yilganini yozing (masalan: D-konvert 3)';
  end if;
  insert into checkin.inventory_verdicts (scan_id, verdict, note, decided_by) values (p_scan, p_verdict, nullif(btrim(coalesce(p_note, '')), ''), me.user_id);
  if p_verdict = 'SECOND_COPY' then
    insert into checkin.ticket_flags (ticket_no, kind, details, source, source_ref, raised_by)
    values (s.ticket_no, 'DUPLICATE_PRINT_CONFIRMED', 'Ikkinchi qog''oz tasdiqlandi (skan #' || p_scan || ', ' || coalesce(p_note, '') || ')', 'INVENTORY', 'scan:' || p_scan, me.user_id)
    on conflict (ticket_no, kind) where status <> 'RESOLVED' do nothing;
  end if;
  perform checkin._audit(me, 'INVENTORY_VERDICT', 'inventory_scan', p_scan::text,
          jsonb_build_object('ticket', s.ticket_no, 'verdict', p_verdict, 'previous', v_prev, 'note', p_note));
  select * into lc from checkin._live_copies(s.ticket_no);
  return jsonb_build_object('scan_id', p_scan, 'ticket_no', s.ticket_no, 'verdict', p_verdict, 'previous', v_prev,
                            'confirmed_copies', coalesce(lc.copies, 0), 'pending_repeats', coalesce(lc.pending, 0), 'observations', coalesce(lc.observations, 0));
end $$;

-- Qaror kutilayotgan takror skanlar
create or replace function public.ci_inventory_pending(p_batch bigint default null) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['INVENTORY', 'SUPERVISOR', 'ADMIN']);
  return (with o as (
      select s.*, row_number() over (partition by s.ticket_no order by s.id) rn,
             first_value(s.id) over (partition by s.ticket_no order by s.id) first_id,
             (select v.verdict from checkin.inventory_verdicts v where v.scan_id = s.id order by v.id desc limit 1) verdict
      from checkin.inventory_scans s
      where s.ticket_no is not null and not exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id))
    select coalesce(jsonb_agg(jsonb_build_object('scan_id', o.id, 'ticket_no', o.ticket_no, 'sector', t.sector, 'row', t.row_no, 'seat', t.seat_no,
             'print_sheet', t.print_page, 'observation_no', o.rn, 'batch', o.batch_id, 'batch_name', b.name, 'at', checkin._tz(o.at),
             'first_scan', o.first_id, 'first_batch', (select f.batch_id from checkin.inventory_scans f where f.id = o.first_id),
             'operator', (select username from checkin.staff where user_id = o.operator), 'mine', o.operator = me.user_id) order by o.id), '[]')
    from o join checkin.tickets t using (ticket_no) join checkin.inventory_batches b on b.id = o.batch_id
    where o.rn > 1 and o.verdict is null and (p_batch is null or o.batch_id = p_batch));
end $$;

-- ============================================================ nazoratchi belgilari (bilet holatini o'zgartirmaydi)
create or replace function public.ci_flags(p_status text default 'ACTIVE') returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  return (select coalesce(jsonb_agg(to_jsonb(f) || jsonb_build_object('raised_at', checkin._tz(f.raised_at), 'resolved_at', checkin._tz(f.resolved_at),
            'text', checkin._flag_text(f.kind), 'sector', t.sector, 'row', t.row_no, 'seat', t.seat_no, 'ticket_status', t.status,
            'raised_by_name', (select username from checkin.staff where user_id = f.raised_by)) order by f.id desc), '[]')
          from checkin.ticket_flags f join checkin.tickets t using (ticket_no)
          where p_status is null or (p_status = 'ACTIVE' and f.status <> 'RESOLVED') or f.status = p_status);
end $$;

create or replace function public.ci_flag_raise(p_ticket text, p_kind text, p_details text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; f checkin.ticket_flags;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  perform set_config('checkin.mode', 'REVIEW', true);
  if length(btrim(coalesce(p_details, ''))) < 5 then raise exception 'DETAILS_REQUIRED'; end if;
  if not exists (select 1 from checkin.tickets where ticket_no = p_ticket) then raise exception 'TICKET_NOT_FOUND'; end if;
  insert into checkin.ticket_flags (ticket_no, kind, details, source, raised_by) values (p_ticket, p_kind, p_details, 'SUPERVISOR', me.user_id)
  on conflict (ticket_no, kind) where status <> 'RESOLVED' do update set details = checkin.ticket_flags.details || ' | ' || excluded.details
  returning * into f;
  perform checkin._audit(me, 'FLAG_RAISE', 'ticket', p_ticket, jsonb_build_object('flag', f.id, 'kind', p_kind, 'details', p_details));
  return to_jsonb(f);
end $$;

create or replace function public.ci_flag_update(p_id bigint, p_status text, p_note text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; f checkin.ticket_flags;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  perform set_config('checkin.mode', 'REVIEW', true);
  if p_status not in ('ACKNOWLEDGED', 'RESOLVED') then raise exception 'STATUS_NOT_ALLOWED'; end if;
  if length(btrim(coalesce(p_note, ''))) < 5 then raise exception 'NOTE_REQUIRED'; end if;
  update checkin.ticket_flags set status = p_status, resolution = coalesce(resolution || ' | ', '') || p_note,
         resolved_by = case when p_status = 'RESOLVED' then me.user_id end, resolved_at = case when p_status = 'RESOLVED' then now() end
   where id = p_id and status <> 'RESOLVED' returning * into f;
  if not found then raise exception 'FLAG_NOT_ACTIVE'; end if;
  perform checkin._audit(me, 'FLAG_' || p_status, 'flag', p_id::text, jsonb_build_object('ticket', f.ticket_no, 'note', p_note));
  return to_jsonb(f);
end $$;

-- Belgidan ko'rib chiqish holati ochish (bilet baribir kiritilishi mumkin — holat faqat kuzatuv uchun)
create or replace function public.ci_flag_open_case(p_id bigint) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; f checkin.ticket_flags; v_case bigint;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  perform set_config('checkin.mode', 'REVIEW', true);
  select * into f from checkin.ticket_flags where id = p_id and status <> 'RESOLVED' for update;
  if not found then raise exception 'FLAG_NOT_ACTIVE'; end if;
  v_case := checkin._case_touch(f.ticket_no, 'INVENTORY', null, me.user_id, 'Belgi #' || f.id || ': ' || checkin._flag_text(f.kind));
  update checkin.ticket_flags set case_id = v_case, status = case when status = 'OPEN' then 'ACKNOWLEDGED' else status end where id = p_id;
  perform checkin._audit(me, 'FLAG_CASE', 'flag', p_id::text, jsonb_build_object('case', v_case, 'ticket', f.ticket_no));
  return jsonb_build_object('case_id', v_case, 'flag', p_id);
end $$;

-- Inventar xodimi uchun hisobotlar (kirish ma'lumotlarini o'zgartirmaydi; tarqatish oluvchilari ko'rsatilmaydi)
create or replace function public.ci_inventory_report(p_name text, p_sector text default null) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; v jsonb;
begin
  me := checkin._me(array['INVENTORY', 'SUPERVISOR', 'ADMIN']);
  if p_name not in ('observed', 'not_observed', 'duplicates', 'rejected_scans', 'scans') then raise exception 'UNKNOWN_REPORT'; end if;
  -- 'not_observed' = hech skanerlanmagan; 'duplicates' = tasdiqlangan ikkinchi qog'oz YOKI qarorsiz takror
  with lc as materialized (select * from checkin._live_copies()),
  dist as materialized (select distinct on (ticket_no) ticket_no, status from checkin.distribution_records order by ticket_no, id desc),
  tk as materialized (select t.ticket_no, t.kind, t.zone, t.sector, t.row_no, t.seat_no, t.print_page, t.print_slot, t.status,
                coalesce(d.status, 'UNKNOWN') dist, coalesce(lc.copies, 0) copies, coalesce(lc.pending, 0) pending_repeats, coalesce(lc.observations, 0) observations,
                checkin._recon_category(t.status, coalesce(d.status, 'UNKNOWN'), coalesce(lc.copies, 0), t.retired_to_spare_at is not null) cat
         from checkin.tickets t left join dist d using (ticket_no) left join lc using (ticket_no) where p_sector is null or t.sector = upper(p_sector))
  select case p_name
    when 'observed' then (select jsonb_agg(to_jsonb(tk) - 'cat' order by ticket_no) from tk where observations > 0)
    when 'not_observed' then (select jsonb_agg(jsonb_build_object('ticket_no', ticket_no, 'kind', kind, 'sector', sector, 'row', row_no, 'seat', seat_no,
         'print_sheet', print_page, 'distribution', dist, 'status', status,
         'category', case when status = 'ADMITTED' then 'ADMITTED' when dist = 'DISTRIBUTED' then 'NOT_OBSERVED_DISTRIBUTED'
                          when dist in ('HELD', 'RETURNED') then 'NOT_OBSERVED_HELD_BUT_MISSING' else 'NOT_OBSERVED_UNKNOWN' end) order by ticket_no) from tk where observations = 0)
    when 'duplicates' then (select jsonb_agg(to_jsonb(tk) - 'cat' order by ticket_no) from tk where copies > 1 or pending_repeats > 0)
    when 'rejected_scans' then (select jsonb_agg(jsonb_build_object('scan_id', s.id, 'at', checkin._tz(s.at), 'batch', s.batch_id, 'kind', s.payload_kind,
         'payload', s.payload_sample, 'operator', (select username from checkin.staff where user_id = s.operator)) order by s.id)
         from checkin.inventory_scans s where s.ticket_no is null)
    when 'scans' then (select jsonb_agg(jsonb_build_object('scan_id', s.id, 'at', checkin._tz(s.at), 'client_at', checkin._tz(s.client_at), 'batch', s.batch_id,
         'batch_name', b.name, 'box', b.box, 'stack', b.stack, 'ticket_no', s.ticket_no, 'kind', s.payload_kind, 'source', s.source, 'device', s.device,
         'seat_note', s.seat_note, 'voided', exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id),
         'verdict', (select v.verdict from checkin.inventory_verdicts v where v.scan_id = s.id order by v.id desc limit 1),
         'operator', (select username from checkin.staff where user_id = s.operator)) order by s.id)
         from checkin.inventory_scans s join checkin.inventory_batches b on b.id = s.batch_id
         where p_sector is null or b.sector = upper(p_sector) or s.ticket_no in (select ticket_no from tk))
    end into v;
  perform checkin._audit(me, 'INVENTORY_REPORT_EXPORT', 'report', p_name, jsonb_build_object('sector', p_sector));
  return coalesce(v, '[]'::jsonb);
end $$;

-- ============================================================ ADMIN: tarqatish importi
create or replace function public.ci_import_distribution(p_rows jsonb, p_source text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; v_bad jsonb; v_n int;
begin
  me := checkin._me(array['ADMIN']);
  if length(coalesce(p_source, '')) < 3 then raise exception 'SOURCE_REQUIRED'; end if;
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) = 0 or jsonb_array_length(p_rows) > 20000 then raise exception 'ROWS_INVALID'; end if;
  select jsonb_agg(x) into v_bad from jsonb_array_elements(p_rows) x
   where not (x ->> 'ticket_no' ~ '^[0-9]{5}$' and exists (select 1 from checkin.tickets t where t.ticket_no = x ->> 'ticket_no'))
      or coalesce(x ->> 'status', '') not in ('DISTRIBUTED', 'HELD', 'RETURNED');
  if v_bad is not null then
    return jsonb_build_object('imported', 0, 'rejected', jsonb_array_length(v_bad), 'errors', (select jsonb_agg(e) from (select e from jsonb_array_elements(v_bad) e limit 20) q),
                              'message', 'Import bekor qilindi: noto''g''ri qatorlar bor (hech narsa yozilmadi)');
  end if;
  insert into checkin.distribution_records (ticket_no, status, recipient_ref, source, note, imported_by)
  select x ->> 'ticket_no', x ->> 'status', nullif(x ->> 'recipient_ref', ''), p_source, nullif(x ->> 'note', ''), me.user_id
  from jsonb_array_elements(p_rows) x;
  get diagnostics v_n = row_count;
  -- Nizo: DISTRIBUTED yozuvlarida turli oluvchilar, yoki turli manbalar turli holat aytadi → nazoratchi belgisi (bilet o'zgarmaydi)
  insert into checkin.ticket_flags (ticket_no, kind, details, source, source_ref, raised_by)
  select d.ticket_no, 'DISTRIBUTION_DISPUTED',
         'Zid yozuvlar: ' || string_agg(d.status || coalesce(' → ' || d.recipient_ref, '') || ' [' || d.source || ']', '; ' order by d.id),
         'IMPORT', p_source, me.user_id
  from checkin.distribution_records d
  where d.ticket_no in (select x ->> 'ticket_no' from jsonb_array_elements(p_rows) x)
  group by d.ticket_no
  having count(distinct d.recipient_ref) filter (where d.status = 'DISTRIBUTED' and d.recipient_ref is not null) > 1
      or (count(distinct d.source) > 1 and count(distinct d.status) > 1)
  on conflict (ticket_no, kind) where status <> 'RESOLVED' do nothing;
  insert into checkin.ticket_flags (ticket_no, kind, details, source, source_ref, raised_by)
  select l.ticket_no, 'DISTRIBUTED_BUT_IN_STOCK', 'Import: tarqatilgan deb yozildi, lekin inventarda ' || l.copies || ' qog''oz', 'IMPORT', p_source, me.user_id
  from checkin._live_copies() l where checkin._dist(l.ticket_no) = 'DISTRIBUTED'
    and l.ticket_no in (select x ->> 'ticket_no' from jsonb_array_elements(p_rows) x)
  on conflict (ticket_no, kind) where status <> 'RESOLVED' do nothing;
  perform checkin._audit(me, 'DISTRIBUTION_IMPORT', 'distribution', p_source, jsonb_build_object('rows', v_n,
          'by_status', (select jsonb_object_agg(st, n) from (select x ->> 'status' st, count(*) n from jsonb_array_elements(p_rows) x group by 1) q)));
  return jsonb_build_object('imported', v_n, 'rejected', 0);
end $$;

-- ============================================================ hisobotlar va boshqaruv paneli
create or replace function public.ci_dashboard() returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  return jsonb_build_object(
    'environment', checkin._setting('environment'), 'admission_open', checkin._setting('admission_open'),
    'capacity', checkin._setting('capacity'), 'server_time', checkin._tz(now()),
    'allocated', (select count(*) from checkin.tickets),
    'admission', jsonb_build_object(
      'admitted_tickets', (select count(*) from checkin.tickets where status = 'ADMITTED'),
      'admitted_replacements', (select count(*) from checkin.replacements where status = 'ADMITTED'),
      'entitlements', checkin._entitlements(),
      'remaining', checkin._entitlements() - (select count(*) from checkin.tickets where status = 'ADMITTED') - (select count(*) from checkin.replacements where status = 'ADMITTED'),
      'held_for_review', (select count(*) from checkin.tickets where status = 'HELD_FOR_REVIEW'),
      'cancelled', (select count(*) from checkin.tickets where status = 'CANCELLED_BY_AUTHORIZED_SUPERVISOR'),
      'duplicate_scans', (select count(*) from checkin.admission_events where decision = 'DENIED_ALREADY_ADMITTED'),
      'duplicate_scan_tickets', (select count(distinct ticket_no) from checkin.admission_events where decision = 'DENIED_ALREADY_ADMITTED'),
      'foreign_rejected', (select count(*) from checkin.admission_events where decision = 'DENIED_FOREIGN_SYSTEM'),
      'invalid_rejected', (select count(*) from checkin.admission_events where decision = 'DENIED_INVALID')),
    'cases', jsonb_build_object(
      'open', (select count(*) from checkin.review_cases where status in ('OPEN', 'IN_REVIEW')),
      'escalated', (select count(*) from checkin.review_cases where status = 'ESCALATED_NO_SEAT'),
      'resolved', (select count(*) from checkin.review_cases where status like 'RESOLVED%' or status = 'CLOSED')),
    'replacements', jsonb_build_object('issued', (select count(*) from checkin.replacements),
      'active', (select count(*) from checkin.replacements where status = 'ACTIVE'),
      'cancelled', (select count(*) from checkin.replacements where status = 'CANCELLED')),
    'spares', jsonb_build_object('available', (select count(*) from checkin.seats where spare_status = 'AVAILABLE'),
      'reserved', (select count(*) from checkin.seats where spare_status = 'RESERVED'),
      'assigned', (select count(*) from checkin.seats where spare_status = 'ASSIGNED')),
    'inventory', (select jsonb_build_object('scans', coalesce(sum(observations), 0), 'distinct_tickets', count(*),
                    'duplicate_tickets', count(*) filter (where copies > 1), 'surplus_copies', coalesce(sum(greatest(copies - 1, 0)), 0),
                    'pending_repeats', coalesce(sum(pending), 0), 'rejected', (select count(*) from checkin.inventory_scans where ticket_no is null),
                    'seat_mismatch', (select count(*) from checkin.inventory_scans where seat_mismatch)) from checkin._live_copies()),
    'flags', (select jsonb_build_object('active', count(*) filter (where status <> 'RESOLVED'), 'open', count(*) filter (where status = 'OPEN')) from checkin.ticket_flags),
    'distribution', (select jsonb_build_object('DISTRIBUTED', count(*) filter (where d = 'DISTRIBUTED'), 'HELD', count(*) filter (where d = 'HELD'),
                       'RETURNED', count(*) filter (where d = 'RETURNED'), 'UNKNOWN', count(*) filter (where d = 'UNKNOWN'))
                     from (select checkin._dist(ticket_no) d from checkin.tickets) q),
    'gates', (select coalesce(jsonb_agg(jsonb_build_object('gate', g.gate_id, 'name', g.name,
                'admitted', (select count(*) from checkin.admission_events e where e.gate = g.gate_id and e.decision = 'ADMITTED'),
                'denied', (select count(*) from checkin.admission_events e where e.gate = g.gate_id and e.decision <> 'ADMITTED'),
                'last_15min', (select count(*) from checkin.admission_events e where e.gate = g.gate_id and e.decision = 'ADMITTED' and e.at > now() - interval '15 minutes'),
                'last_scan', (select checkin._tz(max(at)) from checkin.scan_log l where l.gate = g.gate_id)) order by g.gate_id), '[]') from checkin.gates g));
end $$;

create or replace function public.ci_report(p_name text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; v jsonb;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  with live as (select s.* from checkin.inventory_scans s where s.ticket_no is not null and not exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id)),
       cnt as (select l.ticket_no, l.copies, l.pending, (select string_agg(distinct x.batch_id::text, ',') from live x where x.ticket_no = l.ticket_no) batches
               from checkin._live_copies() l)
  select case p_name
    when 'sector_summary' then (select jsonb_agg(row_to_json(q) order by q.kind, q.sector) from (
        select t.kind, t.zone, t.sector, count(*) allocated,
               count(*) filter (where t.status = 'ADMITTED') admitted,
               count(*) filter (where t.status = 'HELD_FOR_REVIEW') held_for_review,
               count(*) filter (where t.status = 'CANCELLED_BY_AUTHORIZED_SUPERVISOR') cancelled,
               count(c.ticket_no) physically_scanned, coalesce(sum(c.copies), 0) physical_copies,
               count(*) filter (where c.copies > 1) duplicate_numbers, coalesce(sum(greatest(c.copies - 1, 0)), 0) surplus_copies,
               count(*) filter (where checkin._dist(t.ticket_no) = 'DISTRIBUTED') distributed,
               count(*) filter (where checkin._dist(t.ticket_no) = 'HELD') held_stock,
               count(*) filter (where checkin._dist(t.ticket_no) = 'UNKNOWN') distribution_unknown,
               count(*) filter (where c.ticket_no is null and checkin._dist(t.ticket_no) <> 'DISTRIBUTED') not_scanned_not_distributed
        from checkin.tickets t left join cnt c on c.ticket_no = t.ticket_no group by t.kind, t.zone, t.sector) q)
    when 'inventory_duplicates' then (select jsonb_agg(jsonb_build_object('ticket_no', t.ticket_no, 'kind', t.kind, 'sector', t.sector, 'row', t.row_no, 'seat', t.seat_no,
        'copies', c.copies, 'pending_repeats', c.pending, 'batches', c.batches, 'status', t.status, 'distribution', checkin._dist(t.ticket_no)) order by t.ticket_no)
        from cnt c join checkin.tickets t using (ticket_no) where c.copies > 1 or c.pending > 0)
    when 'inventory_missing' then (select jsonb_agg(jsonb_build_object('ticket_no', t.ticket_no, 'kind', t.kind, 'sector', t.sector, 'row', t.row_no, 'seat', t.seat_no,
        'status', t.status, 'distribution', checkin._dist(t.ticket_no),
        'category', case when t.status = 'ADMITTED' then 'ADMITTED' when checkin._dist(t.ticket_no) = 'DISTRIBUTED' then 'DISTRIBUTED_NOT_IN_STOCK'
                         when checkin._dist(t.ticket_no) = 'HELD' then 'HELD_BUT_NOT_FOUND' else 'UNKNOWN_NOT_IN_STOCK' end) order by t.ticket_no)
        from checkin.tickets t where not exists (select 1 from cnt c where c.ticket_no = t.ticket_no))
    when 'seat_conflicts' then (select jsonb_agg(x) from (
        select jsonb_build_object('type', 'PRINTED_SEAT_MISMATCH', 'ticket_no', s.ticket_no, 'master_seat', t.seat_key, 'printed', s.seat_note, 'scan_id', s.id) x
          from live s join checkin.tickets t using (ticket_no) where s.seat_mismatch
        union all
        select jsonb_build_object('type', 'MULTIPLE_ENTITLEMENTS', 'seat_key', k.seat_key, 'count', k.n)
          from (select seat_key, count(*) n from (select seat_key from checkin.tickets where status <> 'CANCELLED_BY_AUTHORIZED_SUPERVISOR'
                 union all select seat_key from checkin.replacements where status <> 'CANCELLED') a group by seat_key having count(*) > 1) k) q)
    when 'distribution' then (select jsonb_agg(jsonb_build_object('ticket_no', t.ticket_no, 'sector', t.sector, 'row', t.row_no, 'seat', t.seat_no,
        'distribution', checkin._dist(t.ticket_no), 'status', t.status, 'copies', coalesce(c.copies, 0)) order by t.ticket_no)
        from checkin.tickets t left join cnt c using (ticket_no))
    when 'admissions' then (select jsonb_agg(jsonb_build_object('at', checkin._tz(e.at), 'decision', e.decision, 'ticket_no', e.ticket_no,
        'replacement_id', e.replacement_id, 'gate', e.gate, 'staff', (select username from checkin.staff where user_id = e.staff),
        'device', e.device, 'offline_at', checkin._tz(e.offline_at), 'payload_kind', e.payload_kind) order by e.id) from checkin.admission_events e)
    when 'cases' then public.ci_cases(null)
    when 'replacements' then (select jsonb_agg(checkin._repl_json(r) || jsonb_build_object('reason', r.reason, 'evidence', r.evidence_summary,
        'issued_at', checkin._tz(r.issued_at), 'issued_by', (select username from checkin.staff where user_id = r.issued_by)) order by r.issued_at) from checkin.replacements r)
    else null end into v;
  if v is null and p_name not in ('sector_summary', 'inventory_duplicates', 'inventory_missing', 'seat_conflicts', 'distribution', 'admissions', 'cases', 'replacements') then
    raise exception 'UNKNOWN_REPORT';
  end if;
  perform checkin._audit(me, 'REPORT_EXPORT', 'report', p_name, '{}');
  return coalesce(v, '[]'::jsonb);
end $$;

-- favqulodda vaziyat uchun to'liq ro'yxat (faqat o'qish)
create or replace function public.ci_roster() returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  perform checkin._audit(me, 'ROSTER_EXPORT', 'roster', null, '{}');
  return jsonb_build_object('generated_at', checkin._tz(now()), 'rows', (select jsonb_agg(jsonb_build_array(t.ticket_no, t.kind, t.sector, t.row_no, t.seat_no,
           t.status, checkin._tz(t.admitted_at), t.admitted_gate) order by t.ticket_no) from checkin.tickets t));
end $$;

-- ============================================================ ADMIN: xodimlar, darvozalar, sozlamalar, audit
create or replace function public.ci_staff_list() returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['ADMIN']);
  return (select coalesce(jsonb_agg(jsonb_build_object('username', username, 'display_name', display_name, 'role', role, 'active', active,
           'last_scan', (select checkin._tz(max(at)) from checkin.scan_log l where l.staff = s.user_id)) order by role, username), '[]') from checkin.staff s);
end $$;

-- Supabase Auth sessiyalari va refresh tokenlarini bekor qilish (aks holda eski refresh token yangi access token olishi mumkin)
create or replace function checkin._kill_auth_sessions(p_users uuid[]) returns int
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare n int := 0;
begin
  if to_regclass('auth.refresh_tokens') is not null then
    execute 'update auth.refresh_tokens set revoked = true where user_id = any ($1) and not revoked' using (select array_agg(x::text) from unnest(p_users) x);
  end if;
  if to_regclass('auth.sessions') is not null then
    execute 'delete from auth.sessions where user_id = any ($1)' using p_users;
    get diagnostics n = row_count;
  end if;
  return n;
end $$;

create or replace function public.ci_staff_set(p_email text, p_display text, p_role text, p_active boolean) returns jsonb
language plpgsql security definer set search_path = checkin, auth, pg_temp as $$
declare me checkin.staff; v_uid uuid; s checkin.staff;
begin
  me := checkin._me(array['ADMIN']);
  select id into v_uid from auth.users where lower(email) = lower(p_email);
  if v_uid is null then raise exception 'AUTH_USER_NOT_FOUND' using hint = 'Avval Supabase Authentication da foydalanuvchi yarating'; end if;
  if v_uid = me.user_id and (not p_active or p_role <> 'ADMIN') then raise exception 'CANNOT_DEMOTE_SELF'; end if;
  if (checkin._setting('environment') #>> '{}') = 'PRODUCTION' and lower(p_email) ~ '(@dusel\.test|@test\.local|^load-|^load[0-9])' then raise exception 'TEST_ACCOUNT_IN_PRODUCTION'; end if;
  insert into checkin.staff (user_id, username, display_name, role, active, created_by)
  values (v_uid, lower(p_email), p_display, p_role, p_active, me.user_id)
  on conflict (user_id) do update set display_name = excluded.display_name, role = excluded.role, active = excluded.active,
     sessions_valid_after = case when excluded.active = false or excluded.role <> checkin.staff.role then now() else checkin.staff.sessions_valid_after end
  returning * into s;
  if not s.active or s.sessions_valid_after > now() - interval '1 second' then perform checkin._kill_auth_sessions(array[s.user_id]); end if;
  perform checkin._audit(me, 'STAFF_SET', 'staff', s.username, jsonb_build_object('role', p_role, 'active', p_active));
  return jsonb_build_object('username', s.username, 'role', s.role, 'active', s.active);
end $$;

create or replace function public.ci_staff_revoke_sessions(p_username text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; n int;
begin
  me := checkin._me(array['ADMIN']);
  update checkin.staff set sessions_valid_after = now() where username = lower(p_username) or p_username = '*';
  get diagnostics n = row_count;
  perform checkin._kill_auth_sessions(array(select user_id from checkin.staff where username = lower(p_username) or p_username = '*'));
  perform checkin._audit(me, 'SESSIONS_REVOKE', 'staff', p_username, jsonb_build_object('count', n));
  return jsonb_build_object('revoked', n);
end $$;

create or replace function public.ci_gate_set(p_gate text, p_name text, p_active boolean) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; g checkin.gates;
begin
  me := checkin._me(array['ADMIN']);
  insert into checkin.gates (gate_id, name, active) values (upper(p_gate), p_name, p_active)
  on conflict (gate_id) do update set name = excluded.name, active = excluded.active returning * into g;
  perform checkin._audit(me, 'GATE_SET', 'gate', g.gate_id, jsonb_build_object('name', p_name, 'active', p_active));
  return to_jsonb(g);
end $$;

create or replace function public.ci_setting_set(p_key text, p_value jsonb) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; v_old jsonb;
begin
  me := checkin._me(array['ADMIN']);
  if p_key = 'capacity' then raise exception 'USE_CAPACITY_CHANGE' using hint = 'Sig''im faqat tashkilotchi qarori bilan (ci_capacity_change)'; end if;
  if p_key = 'admission_open' then raise exception 'USE_ADMISSION_SET'; end if;
  if p_key not in ('block_held_stock', 'rate_limit_per_10s', 'event_label') then raise exception 'SETTING_NOT_ALLOWED'; end if;
  if p_key = 'block_held_stock' and jsonb_typeof(p_value) <> 'boolean' then raise exception 'BOOLEAN_REQUIRED'; end if;
  if p_key = 'rate_limit_per_10s' and (jsonb_typeof(p_value) <> 'number' or (p_value::text::numeric) not between 5 and 200) then raise exception 'NUMBER_5_200_REQUIRED'; end if;
  if p_key = 'event_label' and (jsonb_typeof(p_value) <> 'string' or length(p_value #>> '{}') > 120) then raise exception 'TEXT_REQUIRED'; end if;
  v_old := checkin._setting(p_key);
  insert into checkin.settings (key, value, updated_at, updated_by) values (p_key, p_value, now(), me.user_id)
  on conflict (key) do update set value = excluded.value, updated_at = now(), updated_by = me.user_id;
  perform checkin._audit(me, 'SETTING_SET', 'setting', p_key, jsonb_build_object('old', v_old, 'new', p_value));
  return jsonb_build_object(p_key, p_value);
end $$;

-- oflayn favqulodda rejim kodi (faqat tuzli xeshi saqlanadi)
create or replace function checkin._pbkdf2_sha256(p_pass text, p_salt text, p_iter int) returns text
language plpgsql immutable security definer set search_path = checkin, extensions, pg_temp as $$
-- PBKDF2-HMAC-SHA256, bitta 32 baytli blok (WebCrypto deriveBits(256) bilan bir xil)
declare u bytea; acc bit(256);
begin
  u := extensions.hmac(convert_to(p_salt, 'UTF8') || '\x00000001'::bytea, convert_to(p_pass, 'UTF8'), 'sha256');
  acc := ('x' || encode(u, 'hex'))::bit(256);
  for i in 2 .. p_iter loop
    u := extensions.hmac(u, convert_to(p_pass, 'UTF8'), 'sha256');
    acc := acc # ('x' || encode(u, 'hex'))::bit(256);
  end loop;
  return (select string_agg(lpad(to_hex(substring(acc from k * 64 + 1 for 64)::bit(64)::bigint), 16, '0'), '' order by k) from generate_series(0, 3) k);
end $$;

create or replace function public.ci_set_contingency_code(p_code text) returns jsonb
language plpgsql security definer set search_path = checkin, extensions, pg_temp as $$
declare me checkin.staff; v_salt text := encode(extensions.gen_random_bytes(16), 'hex'); v_iter int := 300000;
begin
  me := checkin._me(array['ADMIN']);
  if p_code !~ '^[0-9]{10,12}$' then raise exception 'CODE_FORMAT' using hint = '10–12 raqam'; end if;
  insert into checkin.settings (key, value, updated_at, updated_by)
  values ('contingency', jsonb_build_object('alg', 'PBKDF2-SHA256', 'iter', v_iter, 'salt', v_salt, 'hash', checkin._pbkdf2_sha256(p_code, v_salt, v_iter)), now(), me.user_id)
  on conflict (key) do update set value = excluded.value, updated_at = now(), updated_by = me.user_id;
  perform checkin._audit(me, 'CONTINGENCY_CODE_SET', 'setting', 'contingency', '{}');
  return jsonb_build_object('ok', true);
end $$;

-- Favqulodda rejim faqat bitta, oldindan belgilangan nazoratchi qurilmasida (mustaqil ko'p darvozali oflayn kirish taqiqlangan)
create or replace function public.ci_contingency_device_set(p_device text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; v_old jsonb;
begin
  me := checkin._me(array['ADMIN']);
  if p_device is not null and p_device !~ '^[A-Za-z0-9_-]{8,80}$' then raise exception 'DEVICE_INVALID'; end if;
  v_old := checkin._setting('contingency_device');
  insert into checkin.settings (key, value, updated_at, updated_by) values ('contingency_device', to_jsonb(p_device), now(), me.user_id)
  on conflict (key) do update set value = excluded.value, updated_at = now(), updated_by = me.user_id;
  perform checkin._audit(me, 'CONTINGENCY_DEVICE_SET', 'setting', 'contingency_device', jsonb_build_object('old', v_old, 'new', p_device));
  return jsonb_build_object('contingency_device', p_device);
end $$;

drop function if exists public.ci_contingency();
create or replace function public.ci_contingency(p_device text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; v_dev text := checkin._setting('contingency_device') #>> '{}';
begin
  me := checkin._me(array['GATE', 'SUPERVISOR', 'ADMIN']);
  if me.role not in ('SUPERVISOR', 'ADMIN') or v_dev is null or p_device is distinct from v_dev then
    return jsonb_build_object('allowed', false);
  end if;
  return jsonb_build_object('allowed', true) || coalesce(checkin._setting('contingency'), '{}'::jsonb);
end $$;

create or replace function public.ci_audit_verify() returns jsonb
language plpgsql security definer set search_path = checkin, extensions, pg_temp as $$
declare me checkin.staff; a record; v_prev text := repeat('0', 64); v_h text; n int := 0;
begin
  me := checkin._me(array['ADMIN']);
  for a in select * from checkin.audit_log order by id loop
    n := n + 1;
    v_h := encode(extensions.digest(a.prev_hash || '|' || a.id::text || '|' || to_char(a.at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US') || '|' ||
              coalesce(a.actor::text, '') || '|' || a.action || '|' || coalesce(a.entity, '') || '|' || coalesce(a.entity_id, '') || '|' || a.details::text, 'sha256'), 'hex');
    if a.prev_hash <> v_prev or a.hash <> v_h then
      return jsonb_build_object('ok', false, 'checked', n, 'first_bad_id', a.id);
    end if;
    v_prev := a.hash;
  end loop;
  return jsonb_build_object('ok', true, 'checked', n, 'head', v_prev);
end $$;

create or replace function public.ci_audit_tail(p_limit int default 100) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['ADMIN']);
  return (select coalesce(jsonb_agg(jsonb_build_object('id', id, 'at', checkin._tz(at), 'actor', actor_name, 'action', action, 'entity', entity,
            'entity_id', entity_id, 'details', details) order by id desc), '[]')
          from (select * from checkin.audit_log order by id desc limit least(greatest(p_limit, 1), 1000)) q);
end $$;

-- ============================================================ yordamchilar
drop function if exists checkin._live_copies();
create or replace function checkin._live_copies(p_ticket text default null)
returns table (ticket_no text, copies int, closed_copies int, pending int, observations int)
language sql stable security definer set search_path = checkin, pg_temp as $$
  -- copies = tasdiqlangan qog'ozlar: birinchi kuzatuv + SECOND_COPY qarorli takrorlar. Qarorsiz takror — "pending", nusxa EMAS.
  with o as (
    select s.id, s.ticket_no, b.closed_at is not null closed,
           row_number() over (partition by s.ticket_no order by s.id) rn,
           (select v.verdict from checkin.inventory_verdicts v where v.scan_id = s.id order by v.id desc limit 1) verdict
    from checkin.inventory_scans s join checkin.inventory_batches b on b.id = s.batch_id
    where s.ticket_no is not null and (p_ticket is null or s.ticket_no = p_ticket)
      and not exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id))
  select o.ticket_no, (count(*) filter (where rn = 1) + count(*) filter (where rn > 1 and verdict = 'SECOND_COPY'))::int,
         count(*) filter (where closed)::int, count(*) filter (where rn > 1 and verdict is null)::int, count(*)::int
  from o group by o.ticket_no
$$;

-- Bilet bo'yicha solishtiruv toifasi (bir-birini istisno qiladi). "Noma'lum" hech qachon "sotilmagan" deb hisoblanmaydi.
create or replace function checkin._recon_category(p_status text, p_dist text, p_copies int, p_retired boolean) returns text
language sql immutable as $$
  select case
    when p_status = 'ADMITTED' then 'ADMITTED'
    when p_retired then 'RETIRED_TO_SPARE'
    when p_status = 'CANCELLED_BY_AUTHORIZED_SUPERVISOR' then 'CANCELLED'
    when p_dist = 'DISTRIBUTED' and p_copies > 0 then 'CONFLICT_DISTRIBUTED_BUT_IN_STOCK'
    when p_dist = 'DISTRIBUTED' then 'DISTRIBUTED_CONFIRMED'
    when p_dist in ('HELD', 'RETURNED') and p_copies > 0 then 'IN_STOCK_CONFIRMED'
    when p_dist in ('HELD', 'RETURNED') then 'HELD_BUT_NOT_FOUND'
    when p_copies > 0 then 'IN_STOCK_NO_RECORD'
    else 'UNKNOWN' end
$$;

-- ============================================================ tasdiqlangan sig'im (faqat tashkilotchi qarori bilan)
create or replace function public.ci_capacity_change(p_new int, p_approval_ref text, p_confirm text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; v_old int;
begin
  me := checkin._me(array['ADMIN']);
  if length(btrim(coalesce(p_approval_ref, ''))) < 10 then
    raise exception 'APPROVAL_REF_REQUIRED' using hint = 'Tashkilotchining yozma qarori (sana, raqam, imzolagan shaxs) kerak';
  end if;
  if p_confirm is distinct from ('SIGIM ' || p_new) then raise exception 'CONFIRMATION_MISMATCH' using hint = 'Tasdiq matni: SIGIM <yangi qiymat>'; end if;
  perform pg_advisory_xact_lock(777001);
  v_old := checkin._setting('capacity')::text::int;
  if p_new < checkin._entitlements() then raise exception 'CAPACITY_BELOW_ENTITLEMENTS'; end if;
  if p_new = v_old then raise exception 'NO_CHANGE'; end if;
  insert into checkin.capacity_changes (old_value, new_value, approval_ref, changed_by) values (v_old, p_new, btrim(p_approval_ref), me.user_id);
  perform set_config('checkin.capacity_change', 'approved', true);
  update checkin.settings set value = to_jsonb(p_new), updated_at = now(), updated_by = me.user_id where key = 'capacity';
  perform set_config('checkin.capacity_change', '', true);
  perform checkin._audit(me, 'CAPACITY_CHANGE', 'setting', 'capacity', jsonb_build_object('old', v_old, 'new', p_new, 'approval_ref', p_approval_ref));
  return jsonb_build_object('capacity', p_new, 'old', v_old);
end $$;


-- ============================================================ kirishni ochish/yopish (avtomatik ochilmaydi)
create or replace function public.ci_admission_set(p_open boolean, p_confirm text default null) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; v_old jsonb;
begin
  me := checkin._me(array['ADMIN']);
  if p_open is null then raise exception 'BOOLEAN_REQUIRED'; end if;
  if p_open and p_confirm is distinct from 'KIRISHNI OCHISH' then
    raise exception 'CONFIRMATION_MISMATCH' using hint = 'Ochish uchun tasdiq matni: KIRISHNI OCHISH';
  end if;
  v_old := checkin._setting('admission_open');
  perform set_config('checkin.admission_change', 'approved', true);
  update checkin.settings set value = to_jsonb(p_open), updated_at = now(), updated_by = me.user_id where key = 'admission_open';
  perform set_config('checkin.admission_change', '', true);
  perform checkin._audit(me, case when p_open then 'ADMISSION_OPEN' else 'ADMISSION_CLOSE' end, 'setting', 'admission_open',
                         jsonb_build_object('old', v_old, 'new', p_open));
  return jsonb_build_object('admission_open', p_open);
end $$;

-- ============================================================ isbotli zaxira joy
-- Tashkilotchi zaxirasidagi biletni (isbot bilan) chiqarib, uning joyini zaxiraga o'tkazish.
-- Natija: asl bilet bekor bo'ladi (-1 ruxsat), joy zaxiraga o'tadi; keyingi almashtirish (+1) — jami sig'im o'zgarmaydi.
create or replace function public.ci_spare_from_stock(p_ticket text, p_evidence text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; t checkin.tickets; v_dist text; c record; v_sheet_dup int; s checkin.seats;
begin
  me := checkin._me(array['ADMIN']);
  if length(btrim(coalesce(p_evidence, ''))) < 10 then raise exception 'EVIDENCE_REQUIRED' using hint = 'Isbot: tarqatish hujjati, inventar partiyasi, kim tekshirdi'; end if;
  select * into t from checkin.tickets where ticket_no = p_ticket for update;
  if not found then raise exception 'TICKET_NOT_FOUND'; end if;
  if t.status <> 'NOT_ADMITTED' then raise exception 'TICKET_NOT_ELIGIBLE' using hint = 'Holati: ' || t.status; end if;
  v_dist := checkin._dist(p_ticket);
  if v_dist not in ('HELD', 'RETURNED') then
    raise exception 'NO_DISTRIBUTION_PROOF' using hint = 'Tarqatish yozuvida HELD/RETURNED emas (' || v_dist || ') — noma''lum bilet zaxira bo''lmaydi';
  end if;
  select * into c from checkin._live_copies() x where x.ticket_no = p_ticket;
  if c.ticket_no is null or c.closed_copies < 1 then
    raise exception 'NOT_PHYSICALLY_VERIFIED' using hint = 'Bilet yopilgan inventar partiyasida skanerlanmagan';
  end if;
  if c.pending > 0 then
    raise exception 'DUPLICATE_UNRESOLVED' using hint = 'Bu raqamda qarorsiz takror skan bor — avval inventar qarori';
  end if;
  if exists (select 1 from checkin.ticket_flags f where f.ticket_no = p_ticket and f.status <> 'RESOLVED') then
    raise exception 'TICKET_FLAGGED' using hint = 'Biletda faol nazoratchi belgisi bor';
  end if;
  if c.copies > 1 then
    raise exception 'DUPLICATE_COPIES_RISK' using hint = 'Bu raqamning ' || c.copies || ' nusxasi topilgan — boshqa nusxa mijozda bo''lishi mumkin';
  end if;
  select count(*) into v_sheet_dup from checkin.tickets x join checkin._live_copies() lc on lc.ticket_no = x.ticket_no
   where x.print_page = t.print_page and (lc.copies > 1 or lc.pending > 0);       -- tasdiqlangan YOKI qarorsiz takror
  if t.print_page is not null and v_sheet_dup > 0 then
    raise exception 'SHEET_REPRINT_RISK' using hint = t.print_page || '-varaqda dublikat bor — varaq ikki marta bosilgan bo''lishi mumkin';
  end if;
  if exists (select 1 from checkin.admission_events where ticket_no = p_ticket)
     or exists (select 1 from checkin.review_cases where ticket_no = p_ticket) then
    raise exception 'GATE_ACTIVITY_EXISTS' using hint = 'Bu bilet darvozada skanerlangan yoki holat ochilgan';
  end if;
  update checkin.tickets set status = 'CANCELLED_BY_AUTHORIZED_SUPERVISOR', status_changed_at = now(), status_changed_by = me.user_id,
         status_reason = 'RETIRED_TO_SPARE: ' || btrim(p_evidence), retired_to_spare_at = now()
   where ticket_no = p_ticket returning * into t;
  update checkin.seats set spare_status = 'AVAILABLE', spare_note = 'Zaxiradan chiqarilgan bilet ' || p_ticket || ': ' || btrim(p_evidence),
         spare_verified_by = me.user_id, spare_verified_at = now()
   where seat_key = t.seat_key returning * into s;
  perform checkin._audit(me, 'SPARE_FROM_STOCK', 'ticket', p_ticket, jsonb_build_object('seat', t.seat_key, 'distribution', v_dist,
          'copies', c.copies, 'print_page', t.print_page, 'evidence', p_evidence));
  return jsonb_build_object('ticket', checkin._ticket_json(t), 'seat', to_jsonb(s),
         'notice', 'Asl bilet bekor qilindi; uning nusxasi darvozada skanerlansa — rad etiladi va nazoratga tushadi');
end $$;

-- ============================================================ boshqaruv paneli: sig'im modeli aniq ko'rsatiladi
create or replace function public.ci_capacity_status() returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; v_cap int; v_ent int;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  v_cap := checkin._setting('capacity')::text::int; v_ent := checkin._entitlements();
  return jsonb_build_object(
    'approved_capacity', v_cap,
    'original_tickets', (select count(*) from checkin.tickets),
    'original_active', (select count(*) from checkin.tickets where status <> 'CANCELLED_BY_AUTHORIZED_SUPERVISOR'),
    'retired_to_spare', (select count(*) from checkin.tickets where retired_to_spare_at is not null),
    'superseded', (select count(*) from checkin.tickets where superseded_by_case is not null),
    'cancelled_other', (select count(*) from checkin.tickets where status = 'CANCELLED_BY_AUTHORIZED_SUPERVISOR' and retired_to_spare_at is null and superseded_by_case is null),
    'replacements_live', (select count(*) from checkin.replacements where status <> 'CANCELLED'),
    'entitlements', v_ent, 'headroom', v_cap - v_ent,
    'extra_seats', (select count(*) from checkin.seats where origin = 'EXTRA'),
    'spares_available', (select count(*) from checkin.seats where spare_status = 'AVAILABLE'),
    'spares_reserved', (select count(*) from checkin.seats where spare_status = 'RESERVED'),
    'capacity_changes', (select coalesce(jsonb_agg(jsonb_build_object('at', checkin._tz(at), 'old', old_value, 'new', new_value, 'approval_ref', approval_ref) order by id), '[]') from checkin.capacity_changes),
    'invariant_ok', v_ent <= v_cap
       and not exists (select seat_key from (select seat_key from checkin.tickets where status <> 'CANCELLED_BY_AUTHORIZED_SUPERVISOR'
                       union all select seat_key from checkin.replacements where status <> 'CANCELLED') a group by seat_key having count(*) > 1));
end $$;

-- ============================================================ fizik bilet solishtiruvi
-- Sektor bo'yicha (p_sector null = hamma sektorlar). Toifalar bir-birini istisno qiladi.
create or replace function public.ci_reconciliation(p_sector text default null) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; v jsonb;
begin
  me := checkin._me(array['INVENTORY', 'SUPERVISOR', 'ADMIN']);
  with lc as materialized (select * from checkin._live_copies()),
  dist as materialized (select distinct on (ticket_no) ticket_no, status from checkin.distribution_records order by ticket_no, id desc),
  tk as materialized (
    select t.ticket_no, t.kind, t.zone, t.sector, t.status, t.print_page, coalesce(d.status, 'UNKNOWN') dist, coalesce(lc.copies, 0) copies, coalesce(lc.pending, 0) pending,
           checkin._recon_category(t.status, coalesce(d.status, 'UNKNOWN'), coalesce(lc.copies, 0), t.retired_to_spare_at is not null) cat
    from checkin.tickets t left join dist d using (ticket_no) left join lc using (ticket_no)
    where p_sector is null or t.print_page in (select print_page from checkin.tickets where sector = upper(p_sector))),
  shc as materialized (
    select print_page, case
             when max(copies) > 1 then 'REPRINTED_SUSPECTED'
             when max(pending) > 0 then 'REPEAT_UNVERIFIED'
             when count(*) filter (where copies > 0) = count(*) then 'FULL_SHEET_IN_STOCK'
             when count(*) filter (where copies > 0) > 0 then 'PARTIAL_SHEET_IN_STOCK'
             when count(*) filter (where dist = 'DISTRIBUTED' or status = 'ADMITTED') = count(*) then 'SHEET_ACCOUNTED_OUTSIDE'
             when count(*) filter (where dist = 'UNKNOWN') = count(*) then 'SHEET_NOT_FOUND_NO_RECORD'
             else 'SHEET_NOT_FOUND_PARTIAL_RECORD' end sheet_cat
    from tk where print_page is not null group by print_page),
  sp as (select distinct sector, print_page from tk where print_page is not null),
  ssc as (select sp.sector, shc.sheet_cat, count(*) n from sp join shc using (print_page) group by 1, 2),
  ss as (select sp.sector,
           coalesce(jsonb_agg(sp.print_page order by sp.print_page) filter (where shc.sheet_cat = 'REPRINTED_SUSPECTED'), '[]') reprinted_sheets,
           coalesce(jsonb_agg(sp.print_page order by sp.print_page) filter (where shc.sheet_cat = 'SHEET_NOT_FOUND_NO_RECORD'), '[]') sheets_not_found_no_record
         from sp join shc using (print_page) group by sp.sector),
  sso as (select sector, jsonb_object_agg(sheet_cat, n) sheets_by_status from ssc group by sector),
  agg as (
    select kind, zone, sector, count(*) allocated, min(ticket_no) first_ticket, max(ticket_no) last_ticket,
      min(print_page) first_sheet, max(print_page) last_sheet, count(distinct print_page) sheets,
      count(*) filter (where cat = 'ADMITTED') admitted,
      count(*) filter (where cat = 'DISTRIBUTED_CONFIRMED') distributed_confirmed,
      count(*) filter (where cat = 'IN_STOCK_CONFIRMED') in_stock_confirmed,
      count(*) filter (where cat = 'IN_STOCK_NO_RECORD') in_stock_no_record,
      count(*) filter (where cat = 'CONFLICT_DISTRIBUTED_BUT_IN_STOCK') conflict_distributed_in_stock,
      count(*) filter (where cat = 'HELD_BUT_NOT_FOUND') held_but_not_found,
      count(*) filter (where cat = 'RETIRED_TO_SPARE') retired_to_spare,
      count(*) filter (where cat = 'CANCELLED') cancelled,
      count(*) filter (where cat = 'UNKNOWN') unknown,
      coalesce(sum(copies), 0) physical_copies_scanned,
      count(*) filter (where copies > 1) duplicate_numbers,
      coalesce(sum(greatest(copies - 1, 0)), 0) surplus_copies,
      coalesce(sum(pending), 0) pending_repeats
    from tk where p_sector is null or sector = upper(p_sector) group by kind, zone, sector)
  select jsonb_agg(to_jsonb(agg) || jsonb_build_object('sheets_by_status', coalesce(sso.sheets_by_status, '{}'),
                   'reprinted_sheets', coalesce(ss.reprinted_sheets, '[]'), 'sheets_not_found_no_record', coalesce(ss.sheets_not_found_no_record, '[]'))
                   order by agg.kind, agg.sector)
    into v from agg left join ss using (sector) left join sso using (sector);
  perform checkin._audit(me, 'REPORT_EXPORT', 'report', 'reconciliation', jsonb_build_object('sector', p_sector));
  return coalesce(v, '[]'::jsonb);
end $$;

-- Varaq bo'yicha batafsil (bitta sektor)
create or replace function public.ci_reconciliation_sheets(p_sector text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['INVENTORY', 'SUPERVISOR', 'ADMIN']);
  if p_sector is null or p_sector !~ '^[A-Za-z0-9]{1,8}$' then raise exception 'SECTOR_REQUIRED'; end if;
  return (with lc as materialized (select * from checkin._live_copies()),
    dist as materialized (select distinct on (ticket_no) ticket_no, status from checkin.distribution_records order by ticket_no, id desc),
    tk as (select t.ticket_no, t.sector, t.row_no, t.seat_no, t.print_page, t.print_slot, t.status, coalesce(d.status, 'UNKNOWN') dist,
                  coalesce(lc.copies, 0) copies, coalesce(lc.pending, 0) pending,
                  checkin._recon_category(t.status, coalesce(d.status, 'UNKNOWN'), coalesce(lc.copies, 0), t.retired_to_spare_at is not null) cat
           from checkin.tickets t left join dist d using (ticket_no) left join lc using (ticket_no)
           where t.print_page in (select print_page from checkin.tickets where sector = upper(p_sector)))
    select coalesce(jsonb_agg(jsonb_build_object('sheet', print_page, 'tickets', tickets, 'in_stock', in_stock, 'max_copies', max_copies,
             'pending_repeats', pending_n,
             'status', case when max_copies > 1 then 'REPRINTED_SUSPECTED' when pending_n > 0 then 'REPEAT_UNVERIFIED' when in_stock = n then 'FULL_SHEET_IN_STOCK'
                            when in_stock > 0 then 'PARTIAL_SHEET_IN_STOCK' when acc = n then 'SHEET_ACCOUNTED_OUTSIDE'
                            when unknown_n = n then 'SHEET_NOT_FOUND_NO_RECORD' else 'SHEET_NOT_FOUND_PARTIAL_RECORD' end)
             order by print_page), '[]')
    from (select print_page, count(*) n, count(*) filter (where copies > 0) in_stock, max(copies) max_copies, sum(pending) pending_n,
                 count(*) filter (where dist = 'DISTRIBUTED' or status = 'ADMITTED') acc, count(*) filter (where dist = 'UNKNOWN') unknown_n,
                 jsonb_agg(jsonb_build_object('ticket_no', ticket_no, 'sector', sector, 'row', row_no, 'seat', seat_no, 'slot', print_slot,
                           'copies', copies, 'pending', pending, 'distribution', dist, 'category', cat) order by print_slot) tickets
          from tk group by print_page) g);
end $$;

-- ============================================================ xodimlarni dastlabki yaratish (FAQAT service_role: admin noutbukidagi tools/create_staff.mjs)
create or replace function public.ci_staff_bootstrap(p_rows jsonb) returns jsonb
language plpgsql security definer set search_path = checkin, auth, pg_temp as $$
declare me checkin.staff; x jsonb; v_uid uuid; n int := 0; v_env text := checkin._setting('environment') #>> '{}'; out jsonb := '[]'::jsonb;
begin
  if coalesce(auth.jwt() ->> 'role', '') <> 'service_role' then raise exception 'SERVICE_ROLE_ONLY' using errcode = '42501'; end if;
  me.username := 'service_role (create_staff)';
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) = 0 or jsonb_array_length(p_rows) > 500 then raise exception 'ROWS_INVALID'; end if;
  for x in select * from jsonb_array_elements(p_rows) loop
    if coalesce(x ->> 'role', '') not in ('INVENTORY', 'GATE', 'SUPERVISOR', 'ADMIN') then raise exception 'ROLE_INVALID: %', x ->> 'email'; end if;
    if v_env = 'PRODUCTION' and lower(x ->> 'email') ~ '(@dusel\.test|@test\.local|^load-|^load[0-9])' then
      raise exception 'TEST_ACCOUNT_IN_PRODUCTION: %', x ->> 'email';
    end if;
    select id into v_uid from auth.users where lower(email) = lower(x ->> 'email');
    if v_uid is null then raise exception 'AUTH_USER_NOT_FOUND: %', x ->> 'email'; end if;
    insert into checkin.staff (user_id, username, display_name, role, active) values (v_uid, lower(x ->> 'email'), coalesce(nullif(x ->> 'display_name', ''), x ->> 'email'), x ->> 'role', true)
    on conflict (user_id) do update set display_name = excluded.display_name, role = excluded.role, active = true,
       sessions_valid_after = case when excluded.role <> checkin.staff.role then now() else checkin.staff.sessions_valid_after end;
    n := n + 1; out := out || jsonb_build_object('email', lower(x ->> 'email'), 'role', x ->> 'role');
  end loop;
  perform checkin._audit(me, 'STAFF_BOOTSTRAP', 'staff', n::text, jsonb_build_object('rows', out, 'environment', v_env));
  return jsonb_build_object('staff', n, 'rows', out);
end $$;

-- ============================================================ production tayyorligi (faqat o'qish)
create or replace function public.ci_readiness(p_expect_env text default 'PRODUCTION') returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; c jsonb := '[]'::jsonb; v_audit jsonb;
begin
  me := checkin._me(array['ADMIN']);
  v_audit := public.ci_audit_verify();
  with k(name, ok, value) as (values
    ('environment', (checkin._setting('environment') #>> '{}') = p_expect_env, checkin._setting('environment') #>> '{}'),
    ('tickets_11222', (select count(*) from checkin.tickets) = 11222, (select count(*) from checkin.tickets)::text),
    ('master_sha256', (checkin._setting('master_sha256') #>> '{}') = 'e50b9a597d5e7f5f74a3270ad6689968c8f1572c3a2fbdeac71eadc417b831bb', checkin._setting('master_sha256') #>> '{}'),
    ('print_layout_sha256', (checkin._setting('print_layout_sha256') #>> '{}') = '3e35be16c86f445b1c551b46f5a11add694a9c0d6f42790c405a1dce472e13d4', checkin._setting('print_layout_sha256') #>> '{}'),
    ('print_pages_11222', (select count(*) from checkin.tickets where print_page is not null) = 11222, (select count(*) from checkin.tickets where print_page is not null)::text),
    ('all_not_admitted', not exists (select 1 from checkin.tickets where status <> 'NOT_ADMITTED'), (select count(*) from checkin.tickets where status <> 'NOT_ADMITTED')::text),
    ('no_admission_events', not exists (select 1 from checkin.admission_events), (select count(*) from checkin.admission_events)::text),
    ('no_admit_scans', not exists (select 1 from checkin.scan_log where mode = 'ADMIT'), (select count(*) from checkin.scan_log where mode = 'ADMIT')::text),
    ('no_replacements', not exists (select 1 from checkin.replacements), (select count(*) from checkin.replacements)::text),
    ('no_review_cases', not exists (select 1 from checkin.review_cases), (select count(*) from checkin.review_cases)::text),
    ('spare_pool_zero', not exists (select 1 from checkin.seats where spare_status <> 'NONE'), (select count(*) from checkin.seats where spare_status <> 'NONE')::text),
    ('no_extra_seats', not exists (select 1 from checkin.seats where origin = 'EXTRA'), (select count(*) from checkin.seats where origin = 'EXTRA')::text),
    ('capacity_11222', (checkin._setting('capacity') #>> '{}') = '11222', checkin._setting('capacity') #>> '{}'),
    ('no_capacity_changes', not exists (select 1 from checkin.capacity_changes), (select count(*) from checkin.capacity_changes)::text),
    ('admission_closed', (checkin._setting('admission_open') #>> '{}') = 'false', checkin._setting('admission_open') #>> '{}'),
    ('no_test_staff', not exists (select 1 from checkin.staff where username ~* '(@dusel\.test|@test\.local|^load-|^load[0-9])'), (select count(*) from checkin.staff where username ~* '(@dusel\.test|@test\.local|^load-|^load[0-9])')::text),
    ('active_admin_exists', exists (select 1 from checkin.staff where role = 'ADMIN' and active), (select count(*) from checkin.staff where role = 'ADMIN' and active)::text),
    ('contingency_device_unset_or_set', true, coalesce(checkin._setting('contingency_device') #>> '{}', '(belgilanmagan)')),
    ('audit_chain_ok', (v_audit ->> 'ok')::boolean, v_audit ->> 'checked'))
  select jsonb_agg(jsonb_build_object('check', name, 'ok', ok, 'value', value)) into c from k;
  return jsonb_build_object('ready', not exists (select 1 from jsonb_array_elements(c) x where not (x ->> 'ok')::boolean),
                            'expected_environment', p_expect_env, 'checks', c,
                            'info', jsonb_build_object('inventory_observations', (select count(*) from checkin.inventory_scans),
                                                       'distribution_records', (select count(*) from checkin.distribution_records),
                                                       'active_flags', (select count(*) from checkin.ticket_flags where status <> 'RESOLVED'),
                                                       'staff', (select count(*) from checkin.staff where active)));
end $$;

-- ============================================================ huquqlar: faqat tizimga kirgan xodimlar
do $$ declare f record; begin
  for f in select p.oid::regprocedure sig from pg_proc p join pg_namespace n on n.oid = p.pronamespace
           where n.nspname = 'public' and p.proname like 'ci\_%' loop
    execute format('revoke all on function %s from public', f.sig);
    if exists (select 1 from pg_roles where rolname = 'anon') then execute format('revoke all on function %s from anon', f.sig); end if;
    if f.sig::text like 'ci_staff_bootstrap%' then
      if exists (select 1 from pg_roles where rolname = 'authenticated') then execute format('revoke all on function %s from authenticated', f.sig); end if;
      if exists (select 1 from pg_roles where rolname = 'service_role') then execute format('grant execute on function %s to service_role', f.sig); end if;
    elsif exists (select 1 from pg_roles where rolname = 'authenticated') then execute format('grant execute on function %s to authenticated', f.sig); end if;
  end loop;
  for f in select p.oid::regprocedure sig from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'checkin' loop
    execute format('revoke all on function %s from public', f.sig);
    if exists (select 1 from pg_roles where rolname = 'anon') then execute format('revoke all on function %s from anon', f.sig); end if;
    if exists (select 1 from pg_roles where rolname = 'authenticated') then execute format('revoke all on function %s from authenticated', f.sig); end if;
  end loop;
end $$;
