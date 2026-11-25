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

create or replace function checkin._dist(p_ticket text) returns text
language sql stable security definer set search_path = checkin, pg_temp as $$
  select coalesce((select status from checkin.distribution_records where ticket_no = p_ticket order by id desc limit 1), 'UNKNOWN')
$$;

create or replace function checkin._copies(p_ticket text) returns int
language sql stable security definer set search_path = checkin, pg_temp as $$
  select count(*)::int from checkin.inventory_scans s
  where s.ticket_no = p_ticket and not exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id)
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
    'row', t.row_no, 'seat', t.seat_no, 'status', t.status,
    'admitted_at', checkin._tz(t.admitted_at), 'admitted_gate', t.admitted_gate,
    'admitted_by', (select username from checkin.staff where user_id = t.admitted_by),
    'distribution', checkin._dist(t.ticket_no), 'inventory_copies', checkin._copies(t.ticket_no),
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
       'Inventarda bu raqamning ' || checkin._copies(t.ticket_no) || ' ta jismoniy nusxasi topilgan (bosmaxona dublikati)'); end if;
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
  me := checkin._me(array['GATE', 'SUPERVISOR', 'ADMIN']);
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
  pr := checkin._parse(p_payload);
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
  if p_request is null then raise exception 'REQUEST_ID_REQUIRED'; end if;
  -- 1) shu so'rov avval bajarilgan bo'lsa — aynan o'sha natijani qaytaramiz (qayta yuborish / ikki marta bosish)
  select * into ev from checkin.admission_events where request_id = p_request;
  if found then return checkin._event_json(ev) || jsonb_build_object('replay', true); end if;
  perform checkin._rate(me);
  perform checkin._gate_ok(p_gate);
  if p_offline_at is not null and (p_offline_at > now() + interval '5 minutes' or p_offline_at < now() - interval '2 days') then
    raise exception 'OFFLINE_TIME_INVALID';
  end if;
  pr := checkin._parse(p_payload);
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
  pr := checkin._parse(p_payload);
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
    'inventory', (select coalesce(jsonb_agg(jsonb_build_object('scan_id', s.id, 'batch', b.name, 'at', checkin._tz(s.at), 'seat_note', s.seat_note,
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
  if found then
    if not checkin._seat_free(v_key) then
      raise exception 'SEAT_OCCUPIED' using hint = 'Bu joy amaldagi biletga yoki almashtirishga biriktirilgan';
    end if;
    if s.spare_status <> 'NONE' then raise exception 'ALREADY_SPARE'; end if;
    update checkin.seats set spare_status = 'AVAILABLE', spare_note = p_note, spare_verified_by = me.user_id, spare_verified_at = now()
     where seat_key = v_key returning * into s;
  else
    insert into checkin.seats (seat_key, kind, zone, sector, row_no, seat_no, origin, spare_status, spare_note, spare_verified_by, spare_verified_at)
    values (v_key, upper(p_kind), p_zone, upper(p_sector), p_row, p_seat, 'EXTRA', 'AVAILABLE', p_note, me.user_id, now()) returning * into s;
  end if;
  perform checkin._audit(me, 'SPARE_ADD', 'seat', v_key, jsonb_build_object('origin', s.origin, 'note', p_note));
  return to_jsonb(s);
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

create or replace function public.ci_issue_replacement(p_case bigint, p_seat_key text, p_reason text, p_evidence text) returns jsonb
language plpgsql security definer set search_path = checkin, extensions, pg_temp as $$
declare me checkin.staff; c checkin.review_cases; s checkin.seats; v_token text; r checkin.replacements; v_cap int;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  if length(coalesce(p_reason, '')) < 5 or length(coalesce(p_evidence, '')) < 5 then raise exception 'REASON_AND_EVIDENCE_REQUIRED'; end if;
  select * into c from checkin.review_cases where id = p_case and status in ('OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT') for update;
  if not found then raise exception 'CASE_NOT_FOUND_OR_CLOSED'; end if;
  select * into s from checkin.seats where seat_key = p_seat_key for update;
  if not found or s.spare_status <> 'RESERVED' or s.reserved_case is distinct from p_case then
    raise exception 'SEAT_NOT_RESERVED_FOR_CASE' using hint = 'Avval joyni shu holat uchun band qiling';
  end if;
  if not checkin._seat_free(p_seat_key) then raise exception 'SEAT_OCCUPIED'; end if;
  perform pg_advisory_xact_lock(777001);                                    -- sig'im tekshiruvi ketma-ket
  v_cap := coalesce(checkin._setting('capacity')::text::int, 11222);
  if checkin._entitlements() + 1 > v_cap then
    -- xato qaytaramiz (exception emas), shunda holat 'ESCALATED_NO_SEAT' bo'lib saqlanadi
    update checkin.review_cases set status = 'ESCALATED_NO_SEAT', resolution_note = 'Sig''im to''lgan — tashkilotchi qarori kerak' where id = p_case;
    perform checkin._audit(me, 'REPLACEMENT_CAPACITY_BLOCK', 'case', p_case::text, jsonb_build_object('capacity', v_cap, 'entitlements', checkin._entitlements()));
    return jsonb_build_object('error', 'CAPACITY_EXCEEDED', 'message', 'Ruxsat etilgan sig''im to''lgan — tashkilotchi qarori kerak', 'case_id', p_case);
  end if;
  v_token := translate(encode(extensions.gen_random_bytes(18), 'base64'), '+/', '-_');   -- 144 bit, taxmin qilib bo'lmaydi
  insert into checkin.replacements (token_hash, token_hint, original_ticket, case_id, seat_key, reason, evidence_summary, issued_by)
  values (encode(extensions.digest(v_token, 'sha256'), 'hex'), right(v_token, 4), c.ticket_no, p_case, p_seat_key, p_reason, p_evidence, me.user_id)
  returning * into r;
  update checkin.seats set spare_status = 'ASSIGNED' where seat_key = p_seat_key;
  update checkin.review_cases set status = 'RESOLVED_REPLACEMENT', evidence_summary = p_evidence, resolution_note = p_reason,
         resolved_by = me.user_id, resolved_at = now() where id = p_case;
  perform checkin._audit(me, 'REPLACEMENT_ISSUE', 'replacement', r.id::text,
          jsonb_build_object('case', p_case, 'original_ticket', c.ticket_no, 'seat', p_seat_key, 'reason', p_reason, 'evidence', p_evidence, 'token_hint', r.token_hint));
  return checkin._repl_json(r) || jsonb_build_object('payload', 'DUSELR1:' || v_token,
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
create or replace function public.ci_inventory_batch_open(p_name text, p_location text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; b checkin.inventory_batches;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  insert into checkin.inventory_batches (name, location, created_by) values (left(p_name, 100), left(p_location, 100), me.user_id) returning * into b;
  perform checkin._audit(me, 'INVENTORY_BATCH_OPEN', 'batch', b.id::text, jsonb_build_object('name', p_name, 'location', p_location));
  return to_jsonb(b);
end $$;

create or replace function public.ci_inventory_batch_close(p_batch bigint) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; b checkin.inventory_batches;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  update checkin.inventory_batches set closed_at = now() where id = p_batch and closed_at is null returning * into b;
  if not found then raise exception 'BATCH_NOT_OPEN'; end if;
  perform checkin._audit(me, 'INVENTORY_BATCH_CLOSE', 'batch', p_batch::text, '{}');
  return to_jsonb(b);
end $$;

create or replace function public.ci_inventory_batches() returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['GATE', 'SUPERVISOR', 'ADMIN']);
  return (select coalesce(jsonb_agg(jsonb_build_object('id', b.id, 'name', b.name, 'location', b.location, 'open', b.closed_at is null,
            'created_at', checkin._tz(b.created_at),
            'scans', (select count(*) from checkin.inventory_scans s where s.batch_id = b.id and not exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id)))
            order by b.id desc), '[]') from checkin.inventory_batches b);
end $$;

create or replace function public.ci_inventory_scan(p_request uuid, p_batch bigint, p_payload text, p_seat_note text default null) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff; pr record; t checkin.tickets; s checkin.inventory_scans; w jsonb := '[]'::jsonb; v_copies int; v_in_batch int;
begin
  me := checkin._me(array['GATE', 'SUPERVISOR', 'ADMIN']);
  if p_request is null then raise exception 'REQUEST_ID_REQUIRED'; end if;
  select * into s from checkin.inventory_scans where request_id = p_request;
  if not found then
    perform checkin._rate(me);
    if not exists (select 1 from checkin.inventory_batches where id = p_batch and closed_at is null) then raise exception 'BATCH_NOT_OPEN'; end if;
    pr := checkin._parse(p_payload);
    if pr.kind <> 'TICKET' then
      return jsonb_build_object('result', pr.kind, 'message', case pr.kind when 'FOREIGN' then 'Kupon/vaucher — bilet emas' else 'Bilet QR emas' end);
    end if;
    insert into checkin.inventory_scans (request_id, batch_id, ticket_no, payload_kind, payload_sample, seat_note, seat_mismatch, operator)
    values (p_request, p_batch, pr.ticket_no, pr.kind, left(p_payload, 120), nullif(btrim(coalesce(p_seat_note, '')), ''),
            nullif(btrim(coalesce(p_seat_note, '')), '') is not null, me.user_id)
    on conflict (request_id) do nothing returning * into s;
    if s.id is null then select * into s from checkin.inventory_scans where request_id = p_request; end if;
    insert into checkin.scan_log (staff, gate, device, mode, payload_kind, ticket_no, result) values (me.user_id, null, null, 'INVENTORY', pr.kind, pr.ticket_no, 'RECORDED');
  end if;
  select * into t from checkin.tickets where ticket_no = s.ticket_no;
  v_copies := checkin._copies(t.ticket_no);
  select count(*) into v_in_batch from checkin.inventory_scans x where x.ticket_no = t.ticket_no and x.batch_id = s.batch_id
     and not exists (select 1 from checkin.inventory_voids v where v.scan_id = x.id);
  if v_copies > 1 then w := w || jsonb_build_object('code', 'DUPLICATE_COPY', 'text', 'Bu raqamning ' || v_copies || '-nusxasi'); end if;
  if t.status = 'ADMITTED' then w := w || jsonb_build_object('code', 'ALREADY_ADMITTED', 'text', 'Bu bilet bilan kirish qayd etilgan!'); end if;
  if checkin._dist(t.ticket_no) = 'DISTRIBUTED' then w := w || jsonb_build_object('code', 'RECORDED_DISTRIBUTED', 'text', 'Tarqatilgan deb qayd etilgan, lekin zaxirada turibdi'); end if;
  if s.seat_mismatch then w := w || jsonb_build_object('code', 'SEAT_MISMATCH', 'text', 'Qog''ozdagi joy masterdan farq qiladi: ' || s.seat_note); end if;
  return jsonb_build_object('result', 'RECORDED', 'scan_id', s.id, 'credential', checkin._ticket_json(t), 'copies_total', v_copies,
                            'copies_in_batch', v_in_batch, 'warnings', w);
end $$;

create or replace function public.ci_inventory_void(p_scan bigint, p_reason text) returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['SUPERVISOR', 'ADMIN']);
  if length(coalesce(p_reason, '')) < 3 then raise exception 'REASON_REQUIRED'; end if;
  insert into checkin.inventory_voids (scan_id, reason, voided_by) values (p_scan, p_reason, me.user_id);
  perform checkin._audit(me, 'INVENTORY_VOID', 'inventory_scan', p_scan::text, jsonb_build_object('reason', p_reason));
  return jsonb_build_object('voided', p_scan);
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
    'inventory', jsonb_build_object(
      'scans', (select count(*) from checkin.inventory_scans s where not exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id)),
      'distinct_tickets', (select count(distinct ticket_no) from checkin.inventory_scans s where not exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id)),
      'duplicate_tickets', (select count(*) from (select ticket_no from checkin.inventory_scans s where not exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id) group by ticket_no having count(*) > 1) q),
      'surplus_copies', (select coalesce(sum(n - 1), 0) from (select count(*) n from checkin.inventory_scans s where not exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id) group by ticket_no having count(*) > 1) q),
      'seat_mismatch', (select count(*) from checkin.inventory_scans where seat_mismatch)),
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
  with live as (select s.* from checkin.inventory_scans s where not exists (select 1 from checkin.inventory_voids v where v.scan_id = s.id)),
       cnt as (select ticket_no, count(*) copies, string_agg(distinct batch_id::text, ',') batches from live group by ticket_no)
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
        'copies', c.copies, 'batches', c.batches, 'status', t.status, 'distribution', checkin._dist(t.ticket_no)) order by t.ticket_no)
        from cnt c join checkin.tickets t using (ticket_no) where c.copies > 1)
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

create or replace function public.ci_staff_set(p_email text, p_display text, p_role text, p_active boolean) returns jsonb
language plpgsql security definer set search_path = checkin, auth, pg_temp as $$
declare me checkin.staff; v_uid uuid; s checkin.staff;
begin
  me := checkin._me(array['ADMIN']);
  select id into v_uid from auth.users where lower(email) = lower(p_email);
  if v_uid is null then raise exception 'AUTH_USER_NOT_FOUND' using hint = 'Avval Supabase Authentication da foydalanuvchi yarating'; end if;
  if v_uid = me.user_id and (not p_active or p_role <> 'ADMIN') then raise exception 'CANNOT_DEMOTE_SELF'; end if;
  insert into checkin.staff (user_id, username, display_name, role, active, created_by)
  values (v_uid, lower(p_email), p_display, p_role, p_active, me.user_id)
  on conflict (user_id) do update set display_name = excluded.display_name, role = excluded.role, active = excluded.active,
     sessions_valid_after = case when excluded.active = false or excluded.role <> checkin.staff.role then now() else checkin.staff.sessions_valid_after end
  returning * into s;
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
  if p_key not in ('admission_open', 'block_held_stock', 'capacity', 'rate_limit_per_10s', 'event_label') then raise exception 'SETTING_NOT_ALLOWED'; end if;
  if p_key in ('admission_open', 'block_held_stock') and jsonb_typeof(p_value) <> 'boolean' then raise exception 'BOOLEAN_REQUIRED'; end if;
  if p_key in ('capacity', 'rate_limit_per_10s') and jsonb_typeof(p_value) <> 'number' then raise exception 'NUMBER_REQUIRED'; end if;
  if p_key = 'capacity' and (p_value::text::int) < checkin._entitlements() then raise exception 'CAPACITY_BELOW_ENTITLEMENTS'; end if;
  v_old := checkin._setting(p_key);
  insert into checkin.settings (key, value, updated_at, updated_by) values (p_key, p_value, now(), me.user_id)
  on conflict (key) do update set value = excluded.value, updated_at = now(), updated_by = me.user_id;
  perform checkin._audit(me, 'SETTING_SET', 'setting', p_key, jsonb_build_object('old', v_old, 'new', p_value));
  return jsonb_build_object(p_key, p_value);
end $$;

-- oflayn favqulodda rejim kodi (faqat tuzli xeshi saqlanadi)
create or replace function public.ci_set_contingency_code(p_code text) returns jsonb
language plpgsql security definer set search_path = checkin, extensions, pg_temp as $$
declare me checkin.staff; v_salt text := encode(extensions.gen_random_bytes(12), 'hex');
begin
  me := checkin._me(array['ADMIN']);
  if p_code !~ '^[0-9]{8,12}$' then raise exception 'CODE_FORMAT' using hint = '8–12 raqam'; end if;
  insert into checkin.settings (key, value, updated_at, updated_by)
  values ('contingency', jsonb_build_object('salt', v_salt, 'hash', encode(extensions.digest(v_salt || ':' || p_code, 'sha256'), 'hex')), now(), me.user_id)
  on conflict (key) do update set value = excluded.value, updated_at = now(), updated_by = me.user_id;
  perform checkin._audit(me, 'CONTINGENCY_CODE_SET', 'setting', 'contingency', '{}');
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.ci_contingency() returns jsonb
language plpgsql security definer set search_path = checkin, pg_temp as $$
declare me checkin.staff;
begin
  me := checkin._me(array['GATE', 'SUPERVISOR', 'ADMIN']);
  return coalesce(checkin._setting('contingency'), '{}'::jsonb);
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

-- ============================================================ huquqlar: faqat tizimga kirgan xodimlar
do $$ declare f record; begin
  for f in select p.oid::regprocedure sig from pg_proc p join pg_namespace n on n.oid = p.pronamespace
           where n.nspname = 'public' and p.proname like 'ci\_%' loop
    execute format('revoke all on function %s from public', f.sig);
    if exists (select 1 from pg_roles where rolname = 'anon') then execute format('revoke all on function %s from anon', f.sig); end if;
    if exists (select 1 from pg_roles where rolname = 'authenticated') then execute format('grant execute on function %s to authenticated', f.sig); end if;
  end loop;
  for f in select p.oid::regprocedure sig from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'checkin' loop
    execute format('revoke all on function %s from public', f.sig);
  end loop;
end $$;
