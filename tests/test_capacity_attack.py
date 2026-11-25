#!/usr/bin/env python3
"""
DUSEL — 11 222 sig'im cheklovini aylanib o'tishga urinishlar (yangi, toza sinov bazasida).
Foydalanish: python test_capacity_attack.py "host=/tmp port=5433 dbname=ci_cap user=postgres"
Qamrov: boshlang'ich zaxira 0; qo'lda sozlama; almashtirish oqimlari; parallel so'rovlar; to'g'ridan-to'g'ri INSERT; poygalar.
"""
import json, sys, time, uuid, threading, random
from concurrent.futures import ThreadPoolExecutor
import psycopg

DSN = sys.argv[1] if len(sys.argv) > 1 else "host=/tmp port=5433 dbname=ci_cap user=postgres"
R = []
def check(n, ok, d=""):
    R.append(dict(name=n, ok=bool(ok), detail=str(d)[:400])); print(("PASS " if ok else "FAIL ") + n + (f" — {d}" if d != "" else ""), flush=True)
admin = psycopg.connect(DSN, autocommit=True)
def sql(q, *a):
    with admin.cursor() as c:
        c.execute(q, a)
        try: return c.fetchall()
        except psycopg.ProgrammingError: return None
USERS = {}
names = [("admin", "ADMIN")] + [(f"sup{i}", "SUPERVISOR") for i in range(1, 11)] + [(f"gate{i}", "GATE") for i in range(1, 5)] + [("inv1", "INVENTORY")]
for n, role in names:
    uid = sql("insert into auth.users (email) values (%s) returning id", f"{n}@cap.local")[0][0]
    sql("insert into checkin.staff (user_id, username, display_name, role) values (%s,%s,%s,%s)", uid, f"{n}@cap.local", n, role)
    USERS[n] = str(uid)
def conn(user):
    c = psycopg.connect(DSN, autocommit=True)
    c.execute("set role authenticated")
    c.execute("select set_config('request.jwt.claims', %s, false)", (json.dumps({"sub": USERS[user], "role": "authenticated", "iat": int(time.time())}),))
    return c
def rpc(c, fn, *a):
    with c.cursor() as k:
        k.execute(f"select public.{fn}({', '.join(['%s'] * len(a))})", a); return k.fetchone()[0]
def err(c, fn, *a):
    try: rpc(c, fn, *a); return None
    except psycopg.Error as e: return (e.diag.message_primary or str(e)).split("\n")[0]
def call(user, fn, *a):
    c = conn(user)
    try: return rpc(c, fn, *a)
    except psycopg.Error as e: return {"error": e.diag.message_primary}
    finally: c.close()
U = lambda n: f"https://dusel.pages.dev/?code={n:05d}"
AD, S1, G1, I1 = conn("admin"), conn("sup1"), conn("gate1"), conn("inv1")
sql("update checkin.settings set value='100000' where key='rate_limit_per_10s'")
def cap(): return rpc(AD, "ci_capacity_status")

# ---------------------------------------------------------------- 0. Boshlang'ich holat: zaxira joy NOL
c0 = cap(); rd = rpc(AD, "ci_readiness", "STAGING")
check("C0 Yangi baza: tasdiqlangan zaxira joy 0, EXTRA 0, ruxsatlar 11 222 = sig'im, bo'sh o'rin 0; tayyorlik tekshiruvi (STAGING) o'tadi",
      c0["spares_available"] == 0 and c0["spares_reserved"] == 0 and c0["extra_seats"] == 0 and rpc(S1, "ci_spares", None) == []
      and c0["entitlements"] == 11222 and c0["approved_capacity"] == 11222 and c0["headroom"] == 0 and rd["ready"],
      [x["check"] for x in rd["checks"] if not x["ok"]])

# ---------------------------------------------------------------- 1. Qo'lda sozlama orqali
def raw(q, *a):
    try: sql(q, *a); return "allowed"
    except psycopg.Error as e: return e.diag.message_primary
tries = {
  "ci_setting_set": err(AD, "ci_setting_set", "capacity", "11300"),
  "sup_change": err(S1, "ci_capacity_change", 11300, "Tashkilotchi qarori №1 (sinov)", "SIGIM 11300"),
  "no_ref": err(AD, "ci_capacity_change", 11300, "", "SIGIM 11300"),
  "bad_confirm": err(AD, "ci_capacity_change", 11300, "Tashkilotchi qarori №1 (sinov)", "SIGIM 11301"),
  "sql_update": raw("update checkin.settings set value='11300' where key='capacity'"),
  "sql_upsert": raw("insert into checkin.settings (key, value) values ('capacity','11300') on conflict (key) do update set value = excluded.value"),
  "sql_delete": raw("delete from checkin.settings where key='capacity'"),
  "admission_sql": raw("update checkin.settings set value='true' where key='admission_open'"),
}
check("C1 Sig'imni qo'lda o'zgartirish: oddiy sozlama, nazoratchi, qarorsiz, noto'g'ri tasdiq, SQL UPDATE/UPSERT/DELETE — hammasi rad; 11 222",
      tries == {"ci_setting_set": "USE_CAPACITY_CHANGE", "sup_change": "ROLE_DENIED", "no_ref": "APPROVAL_REF_REQUIRED", "bad_confirm": "CONFIRMATION_MISMATCH",
                "sql_update": "CAPACITY_LOCKED", "sql_upsert": "CAPACITY_LOCKED", "sql_delete": "CAPACITY_LOCKED", "admission_sql": "ADMISSION_LOCKED"}
      and cap()["approved_capacity"] == 11222, tries)
rpc(AD, "ci_admission_set", True, "KIRISHNI OCHISH")

# ---------------------------------------------------------------- 2. 10 ta EXTRA joy + 10 holat, bo'sh o'rin 0 → 10 parallel almashtirish: 0 muvaffaqiyat
for k in range(10): rpc(AD, "ci_admin_spare_add", "SEKTOR", "2-qavat", "B206", 15, k + 16, "Zalda tekshirildi (sinov)")
cases = [rpc(G1, "ci_refer", U(1001 + k), "G1", "takror bilet da'vosi (sinov)")["case_id"] for k in range(10)]
for k, cid in enumerate(cases): rpc(conn(f"sup{k + 1}"), "ci_spare_reserve", cid, f"SEKTOR:B206:15:{k + 16}")
def issue(k): return call(f"sup{k + 1}", "ci_issue_replacement", cases[k], f"SEKTOR:B206:15:{k + 16}", "Haqiqiy xaridor (sinov)", "Chek ko'rildi (sinov)", False)
with ThreadPoolExecutor(10) as ex: r2 = list(ex.map(issue, range(10)))
ok2 = sum(1 for r in r2 if r.get("payload"))
check("C2 Bo'sh o'rin 0 da 10 nazoratchi bir vaqtda almashtirish beradi → 0 muvaffaqiyat, hammasi tashkilotchiga (ESCALATED_NO_SEAT); EXTRA joy sig'imni oshirmaydi",
      ok2 == 0 and all(r.get("error") == "CAPACITY_EXCEEDED" for r in r2) and cap()["entitlements"] == 11222, [r.get("error") for r in r2][:3])

# ---------------------------------------------------------------- 3. Isbotli zaxira 1 ta → 10 parallel almashtirish: aynan 1
def retire(tickets):
    rpc(AD, "ci_import_distribution", json.dumps([{"ticket_no": f"{t:05d}", "status": "HELD"} for t in tickets]), "Tashkilotchi zaxirasi (sinov)")
    b = rpc(I1, "ci_inventory_batch_open", "Zaxira (sinov)", "Seyf", None, None, None, "inv-x")["id"]
    for t in tickets: rpc(I1, "ci_inventory_scan", str(uuid.uuid4()), b, U(t), None, "SCANNER", "inv-x", None)
    rpc(I1, "ci_inventory_batch_close", b)
    return [rpc(AD, "ci_spare_from_stock", f"{t:05d}", "Tashkilotchi zaxirasi, seyf, inventar #%d (sinov)" % b) for t in tickets]
retire([2001])
with ThreadPoolExecutor(10) as ex: r3 = list(ex.map(issue, range(10)))
ok3 = sum(1 for r in r3 if r.get("payload"))
check("C3 Bitta isbotli bo'sh o'rin, 10 parallel almashtirish → aynan 1 muvaffaqiyat; ruxsatlar 11 222",
      ok3 == 1 and cap()["entitlements"] == 11222 and cap()["invariant_ok"], [r.get("error") or "OK" for r in r3])

# ---------------------------------------------------------------- 4. To'g'ridan-to'g'ri parallel INSERT (funksiyani chetlab): bo'sh o'rin 2 → aynan 2
retire([2002, 2003])
free = [k + 16 for k in range(10) if sql("select spare_status from checkin.seats where seat_key=%s", f"SEKTOR:B206:15:{k + 16}")[0][0] != "ASSIGNED"]
def raw_insert(k):
    c = psycopg.connect(DSN, autocommit=True)
    try:
        c.execute("insert into checkin.replacements (token_hash, token_hint, original_ticket, case_id, seat_key, reason, evidence_summary, issued_by) values (md5(random()::text), 'xxxx', null, %s, %s, 'r', 'e', %s)",
                  (cases[0], f"SEKTOR:B206:15:{k}", USERS["admin"])); return "OK"
    except psycopg.Error as e: return e.diag.message_primary
    finally: c.close()
with ThreadPoolExecutor(8) as ex: r4 = list(ex.map(raw_insert, free[:8]))
check("C4 Superuser 8 ta parallel to'g'ridan-to'g'ri INSERT (bo'sh o'rin 2) → aynan 2; trigger qulfi poygani to'xtatadi",
      r4.count("OK") == 2 and all(x in ("OK", "CAPACITY_EXCEEDED") for x in r4) and cap()["entitlements"] == 11222 and cap()["invariant_ok"], r4)

# ---------------------------------------------------------------- 5. Poyga: asl biletni kiritish ↔ uning o'rniga almashtirish (supersede)
res5 = []
for k in range(8):
    t = 3001 + k; seat = sql("select seat_key from checkin.tickets where ticket_no=%s", f"{t:05d}")[0][0]
    cid = rpc(G1, "ci_refer", U(t), "G1", "shikastlangan bilet (sinov)")["case_id"]
    bar = threading.Barrier(2)
    def a(): bar.wait(); time.sleep(random.random() * 0.03); return call("gate2", "ci_admit", str(uuid.uuid4()), U(t), "G2", "race")
    def b(): bar.wait(); time.sleep(random.random() * 0.03); return call("sup2", "ci_issue_replacement", cid, seat, "Shikastlangan (sinov)", "Pasport ko'rildi (sinov)", True)
    with ThreadPoolExecutor(2) as ex: fa, fb = ex.submit(a), ex.submit(b); ra, rb = fa.result(), fb.result()
    st = sql("select status from checkin.tickets where ticket_no=%s", f"{t:05d}")[0][0]
    live = sql("select count(*) from checkin.replacements where seat_key=%s and status <> 'CANCELLED'", seat)[0][0]
    res5.append((ra.get("decision"), "REPL" if rb.get("payload") else rb.get("error"), st, live))
both = [x for x in res5 if x[0] == "ADMITTED" and x[1] == "REPL"]
check("C5 8 poyga: asl bilet kiritish va uning o'rniga yangi QR bir vaqtda → hech qachon ikkalasi emas (bir joyga bitta huquq)",
      not both and all((x[0] == "ADMITTED" and x[2] == "ADMITTED" and x[3] == 0) or (x[1] == "REPL" and x[2] == "CANCELLED_BY_AUTHORIZED_SUPERVISOR" and x[3] == 1) for x in res5),
      res5[:4])

# ---------------------------------------------------------------- 6. Poyga: zaxiraga o'tkazish ↔ darvozada kiritish
rpc(AD, "ci_setting_set", "block_held_stock", json.dumps(False))
tk6 = [4001 + k for k in range(6)]
rpc(AD, "ci_import_distribution", json.dumps([{"ticket_no": f"{t:05d}", "status": "HELD"} for t in tk6]), "Zaxira (sinov)")
b6 = rpc(I1, "ci_inventory_batch_open", "Zaxira 2 (sinov)", "Seyf", None, None, None, "inv-x")["id"]
for t in tk6: rpc(I1, "ci_inventory_scan", str(uuid.uuid4()), b6, U(t), None, "SCANNER", "inv-x", None)
rpc(I1, "ci_inventory_batch_close", b6)
res6 = []
for t in tk6:
    bar = threading.Barrier(2)
    def a(): bar.wait(); time.sleep(random.random() * 0.03); return call("gate3", "ci_admit", str(uuid.uuid4()), U(t), "G3", "race6")
    def b(): bar.wait(); time.sleep(random.random() * 0.03); return call("admin", "ci_spare_from_stock", f"{t:05d}", "Tashkilotchi zaxirasi (sinov, poyga)")
    with ThreadPoolExecutor(2) as ex: fa, fb = ex.submit(a), ex.submit(b); ra, rb = fa.result(), fb.result()
    st = sql("select status from checkin.tickets where ticket_no=%s", f"{t:05d}")[0][0]
    sp = sql("select s.spare_status from checkin.seats s join checkin.tickets t using (seat_key) where t.ticket_no=%s", f"{t:05d}")[0][0]
    res6.append((ra.get("decision"), "SPARE" if rb.get("seat") else rb.get("error"), st, sp))
check("C6 6 poyga: bilet darvozada kiritilayotgan paytda zaxiraga o'tkazish → hech qachon ikkalasi emas (kirgan biletning joyi zaxiraga o'tmaydi)",
      all((x[0] == "ADMITTED" and x[1] != "SPARE" and x[2] == "ADMITTED" and x[3] == "NONE") or (x[1] == "SPARE" and x[0] == "DENIED_CANCELLED" and x[3] == "AVAILABLE") for x in res6), res6)
rpc(AD, "ci_setting_set", "block_held_stock", json.dumps(True))

# ---------------------------------------------------------------- 7. Boshqa yo'llar
ret_case = rpc(S1, "ci_refer", U(2001), "G1", "zaxiraga o'tgan bilet (sinov)")["case_id"]
e7a = err(S1, "ci_supervisor_admit", ret_case, str(uuid.uuid4()), "G1", "sup-dev", "zaxiraga o'tgan biletni kiritishga urinish")
tok = [r for r in r3 if r.get("payload")][0]
adm = rpc(G1, "ci_admit", str(uuid.uuid4()), tok["payload"], "G1", "dev")
e7b = err(S1, "ci_replacement_cancel", tok["replacement_id"], "kiritilgan almashtirishni bekor qilishga urinish")
r_unadm = raw("update checkin.replacements set status='CANCELLED' where id=%s", tok["replacement_id"])
e7c = err(AD, "ci_capacity_change", 11000, "Tashkilotchi qarori (sinov)", "SIGIM 11000")
check("C7 Zaxiraga o'tgan asl biletni nazoratchi ham kirita olmaydi; kiritilgan almashtirishni bekor qilib joyni qayta berib bo'lmaydi; sig'imni ruxsatlardan pastga tushirib bo'lmaydi",
      e7a in ("TICKET_NOT_ADMISSIBLE", "CASE_NOT_FOUND_OR_CLOSED") and adm["decision"] == "ADMITTED" and e7b == "NOT_ACTIVE"
      and r_unadm == "REPLACEMENT_STATUS_FINAL" and e7c == "CAPACITY_BELOW_ENTITLEMENTS", (e7a, e7b, r_unadm, e7c))

# ---------------------------------------------------------------- 8. To'liq zal: hamma kiritilsa ham ≤ 11 222
with admin.cursor() as k:
    k.execute("select ticket_no from checkin.tickets where status = 'NOT_ADMITTED' order by ticket_no")
    rest = [r[0] for r in k.fetchall()]
def admit_chunk(ch):
    c = conn("gate4"); n = 0
    for t in ch: n += rpc(c, "ci_admit", str(uuid.uuid4()), U(int(t)), "G4", "fill")["decision"] == "ADMITTED"
    c.close(); return n
with ThreadPoolExecutor(8) as ex: sum(ex.map(admit_chunk, [rest[i::8] for i in range(8)]))
for r in r3 + [x for x in r2]:
    if r.get("payload"): rpc(G1, "ci_admit", str(uuid.uuid4()), r["payload"], "G1", "dev")
rows = sql("select replacement_id from checkin.admission_events where decision='ADMITTED' and replacement_id is not null")
for (rid,) in sql("select id from checkin.replacements where status='ACTIVE'"): pass
total = sql("select (select count(*) from checkin.tickets where status='ADMITTED') + (select count(*) from checkin.replacements where status='ADMITTED')")[0][0]
final = cap()
conf = [c for c in rpc(S1, "ci_report", "seat_conflicts") if c["type"] == "MULTIPLE_ENTITLEMENTS"]
head0 = final["headroom"]
for k in range(head0 + 3): rpc(AD, "ci_admin_spare_add", "SEKTOR", "2-qavat", "B206", 15, 26 + k, "Zalda tekshirildi (sinov)")
newc = [rpc(G1, "ci_refer", U(5001 + k), "G1", "oxirgi da'vo (sinov)")["case_id"] for k in range(head0 + 3)]
for k, cid in enumerate(newc): rpc(S1, "ci_spare_reserve", cid, f"SEKTOR:B206:15:{26 + k}")
r8 = [call("sup3", "ci_issue_replacement", cid, f"SEKTOR:B206:15:{26 + k}", "oxirgi urinish (sinov)", "dalil (sinov)", False) for k, cid in enumerate(newc)]
issued8 = sum(1 for r in r8 if r.get("payload"))
final2 = cap()
check("C8 Zal to'ldi: jami kirishlar ≤ ruxsatlar ≤ 11 222; qolgan bo'sh o'rin (%d) aynan to'ldi, keyingi almashtirishlar rad; bir joyga ikki huquq yo'q" % head0,
      total <= final["entitlements"] <= 11222 and final["invariant_ok"] and conf == [] and issued8 == head0
      and all(r.get("error") == "CAPACITY_EXCEEDED" for r in r8[head0:]) and final2["entitlements"] == 11222 and final2["headroom"] == 0 and final2["invariant_ok"],
      dict(total=total, ent=final["entitlements"], issued=issued8, ent_after=final2["entitlements"]))

json.dump(R, open("capacity_attack_results.json", "w"), ensure_ascii=False, indent=1)
print(f"\n{sum(r['ok'] for r in R)}/{len(R)} PASS")
sys.exit(0 if all(r["ok"] for r in R) else 1)
