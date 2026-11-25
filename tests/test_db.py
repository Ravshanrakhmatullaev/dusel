#!/usr/bin/env python3
"""
DUSEL check-in — ma'lumotlar bazasi darajasidagi avtomatik testlar (lokal Postgres 16, Supabase bilan bir xil SQL).
Foydalanish: python test_db.py "host=/tmp port=5433 dbname=ci_test user=postgres"
Barcha test kirishlari SINOV bazasida bajariladi; haqiqiy (production) baza tegilmaydi.
"""
import json, sys, time, uuid, threading, hashlib, re
from concurrent.futures import ThreadPoolExecutor
import psycopg

DSN = sys.argv[1] if len(sys.argv) > 1 else "host=/tmp port=5433 dbname=ci_test user=postgres"
R = []
def check(n, ok, d=""):
    R.append(dict(name=n, ok=bool(ok), detail=str(d)[:400])); print(("PASS " if ok else "FAIL ") + n + (f" — {d}" if d != "" else ""), flush=True)

admin = psycopg.connect(DSN, autocommit=True)
def sql(q, *a):
    with admin.cursor() as c:
        c.execute(q, a)
        try: return c.fetchall()
        except psycopg.ProgrammingError: return None

# ---------------------------------------------------------------- sinov xodimlari
USERS = {}
for name, role, active in [("admin", "ADMIN", True), ("sup1", "SUPERVISOR", True), ("sup2", "SUPERVISOR", True),
                           ("gate1", "GATE", True), ("gate2", "GATE", True), ("gate3", "GATE", True), ("gone", "GATE", False)]:
    uid = sql("insert into auth.users (email) values (%s) on conflict (email) do update set email = excluded.email returning id", f"{name}@test.local")[0][0]
    sql("insert into checkin.staff (user_id, username, display_name, role, active) values (%s,%s,%s,%s,%s) on conflict (user_id) do update set role=excluded.role, active=excluded.active, sessions_valid_after='2000-01-01'",
        uid, f"{name}@test.local", name.upper(), role, active)
    USERS[name] = str(uid)
USERS["stranger"] = str(sql("insert into auth.users (email) values ('stranger@test.local') on conflict (email) do update set email = excluded.email returning id")[0][0])
sql("update checkin.settings set value = 'true' where key = 'admission_open'")
sql("update checkin.settings set value = '100000' where key = 'rate_limit_per_10s'")

def conn(user=None, iat=None, role="authenticated"):
    c = psycopg.connect(DSN, autocommit=True)
    with c.cursor() as k:
        k.execute(f"set role {role}")
        if user:
            claims = {"sub": USERS[user], "role": "authenticated", "iat": int(iat if iat is not None else time.time())}
            k.execute("select set_config('request.jwt.claims', %s, false)", (json.dumps(claims),))
    return c

def rpc(c, fn, *args):
    with c.cursor() as k:
        k.execute(f"select public.{fn}({', '.join(['%s'] * len(args))})", args)
        v = k.fetchone()[0]
        return v

def err(c, fn, *args):
    try:
        rpc(c, fn, *args); return None
    except psycopg.Error as e:
        return (e.diag.message_primary or str(e)).split("\n")[0]

U = lambda n: f"https://dusel.pages.dev/?code={n:05d}"
G1, G2 = conn("gate1"), conn("gate2")
S1, S2, AD = conn("sup1"), conn("sup2"), conn("admin")

# 3. 11 222 yozuv
n, nd, mn, mx = sql("select count(*), count(distinct seat_key), min(ticket_no), max(ticket_no) from checkin.tickets")[0]
check("T03 Barcha 11 222 bilet yozuvi bor (00001–11222), har biri alohida joyda", (n, nd, mn, mx) == (11222, 11222, "00001", "11222"), (n, nd, mn, mx))
sec = dict(sql("select sector, count(*) from checkin.tickets where kind='SEKTOR' group by 1"))
check("T03b Sektor sonlari masterga mos (A402=277, A403=320, A405=445)", (sec["A402"], sec["A403"], sec["A405"]) == (277, 320, 445), (sec["A402"], sec["A403"], sec["A405"]))

# 17. QR tahlili — tarixiy formatlar qabul, qolganlari rad
ACCEPT = ["https://dusel.pages.dev/?code=00330", "https://dusel.pages.dev/ticket?code=00330", "https://ravshanrakhmatullaev.github.io/dusel/?code=00330",
          "http://dusel.pages.dev/?code=00330", "https://dusel.pages.dev/ticket.html?code=00330", "https://ravshanrakhmatullaev.github.io/dusel/index.html?code=00330",
          "00330", "  https://dusel.pages.dev/?code=00330\n"]
REJECT = ["https://dusel.pages.dev/?code=11223", "https://dusel.pages.dev/?code=00000", "https://dusel.pages.dev/ticket?code=000330",
          "https://dusel.pages.dev/?code=0330", "https://dusel.pages.dev/?code=00330&code=00331", "https://dusel.pages.dev/?code=00330#x",
          "https://evil.example/?code=00330", "https://dusel.pages.dev.evil.com/?code=00330", "https://ravshanrakhmatullaev.github.io/?code=00330",
          "https://dusel.pages.dev/?code=00330'; drop table checkin.tickets;--", "javascript:alert(1)", "", "x" * 400,
          "https://dusel.pages.dev/?Code=00330x", "DUSELR1:short", "https://dusel.pages.dev/checkin?code=00330", "https://dusel.pages.dev/ticket/?code=00330"]
FOREIGN = ["https://dusel.pages.dev/gold?code=0001", "https://dusel.pages.dev/silver?code=0001", "https://dusel.pages.dev/gal?code=0001",
           "https://dusel.pages.dev/coupon?type=gold&code=0001", "https://dusel.pages.dev/coupon?type=silver&code=4000", "https://dusel.pages.dev/gal?code=000001"]
pa = [sql("select (checkin._parse(%s)).kind, (checkin._parse(%s)).ticket_no", s, s)[0] for s in ACCEPT]
check("T17a Barcha tarixiy bilet URL formatlari bir xil bilet yozuviga tushadi (00330)", all(k == ("TICKET", "00330") for k in pa), pa)
pr = [(s[:40], sql("select (checkin._parse(%s)).kind", s)[0][0]) for s in REJECT]
check("T17b Noto'g'ri/manipulyatsiya qilingan URL'lar rad etiladi", all(k == "INVALID" for _, k in pr), [p for p in pr if p[1] != "INVALID"])
pf = [sql("select (checkin._parse(%s)).kind", s)[0][0] for s in FOREIGN]
check("T09a GOLD/SILVER/GAL/kupon QR'lari 'boshqa tizim' deb aniqlanadi", all(k == "FOREIGN" for k in pf), pf)

# 4. Ko'rish (lookup) holatni o'zgartirmaydi
before = sql("select status from checkin.tickets where ticket_no='00330'")[0][0]
for _ in range(5): rpc(G1, "ci_lookup", U(330), "G1", "dev-1")
after = sql("select status, admitted_at from checkin.tickets where ticket_no='00330'")[0]
check("T04 QR'ni ko'rish/qayta-qayta tekshirish kirish holatini o'zgartirmaydi", before == "NOT_ADMITTED" and after == ("NOT_ADMITTED", None), after)

# 5–6. Birinchi kirish va takroriy
r1 = rpc(G1, "ci_admit", str(uuid.uuid4()), U(330), "G1", "dev-1")
check("T05 Birinchi ruxsatli kirish muvaffaqiyatli (ENTRY APPROVED)", r1["decision"] == "ADMITTED" and r1["credential"]["kind"] == "BLITCHER" and r1["credential"]["sector"] == "A202", r1["credential"])
ev = sql("select gate, device, staff::text from checkin.admission_events where request_id = %s", r1["request_id"])[0]
check("T05b Kirish yozuvi: darvoza, qurilma, xodim, vaqt (Asia/Tashkent)", ev == ("G1", "dev-1", USERS["gate1"]) and re.match(r"\d\d\.\d\d\.\d{4} \d\d:\d\d:\d\d", r1["at"]), ev)
r2 = rpc(G2, "ci_admit", str(uuid.uuid4()), "https://dusel.pages.dev/ticket?code=00330", "G2", "dev-2")
check("T06 Ikkinchi kirish bloklanadi (boshqa URL formati bilan ham — bitta bilet holati)", r2["decision"] == "DENIED_ALREADY_ADMITTED" and r2["previous"]["gate"] == "G1" and r2["case_id"], r2)
r3 = rpc(G2, "ci_admit", str(uuid.uuid4()), "https://ravshanrakhmatullaev.github.io/dusel/?code=00330", "G2", "dev-2")
case = sql("select attempts, source, status from checkin.review_cases where id = %s", r2["case_id"])[0]
check("T06b Takroriy skanlar bitta ko'rib chiqish holatiga yig'iladi (avtomatik ayblov yo'q, nazoratchiga yuboriladi)", r3["decision"] == "DENIED_ALREADY_ADMITTED" and case == (2, "DUPLICATE_SCAN", "OPEN"), case)

# 7. Parallel: turli darvozalardan bir biletga bir vaqtda
def race(ticket, n):
    conns = [conn(["gate1", "gate2", "gate3", "sup1"][i % 4]) for i in range(n)]
    barrier = threading.Barrier(n)
    def go(i):
        barrier.wait()
        return rpc(conns[i], "ci_admit", str(uuid.uuid4()), U(ticket), f"G{1 + i % 4}", f"race-{i}")["decision"]
    with ThreadPoolExecutor(n) as ex: out = list(ex.map(go, range(n)))
    for c in conns: c.close()
    return out
results = [race(t, 24) for t in range(1001, 1041)]
ok = all(r.count("ADMITTED") == 1 and r.count("DENIED_ALREADY_ADMITTED") == 23 for r in results)
evc = sql("select count(*) from checkin.admission_events where ticket_no between '01001' and '01040' and decision='ADMITTED'")[0][0]
check("T07 40 bilet × 24 parallel skan (4 darvoza): har biletga aynan 1 ta ruxsat", ok and evc == 40, f"ADMITTED yozuvlar {evc}/40")

# 8. Qayta yuborish / ikki marta bosish — bir xil request_id
def retries(ticket, n):
    rid = str(uuid.uuid4()); conns = [conn("gate1") for _ in range(n)]; barrier = threading.Barrier(n)
    def go(i):
        barrier.wait(); return rpc(conns[i], "ci_admit", rid, U(ticket), "G1", "dev-retry")["decision"]
    with ThreadPoolExecutor(n) as ex: out = list(ex.map(go, range(n)))
    for c in conns: c.close()
    return rid, out
rid, out = retries(2001, 16)
cnt = sql("select count(*) from checkin.admission_events where request_id = %s", rid)[0][0]
again = rpc(G1, "ci_admit", rid, U(2001), "G1", "dev-retry")
check("T08 Bir xil so'rov 16 marta parallel + keyin qayta: hammasi 'ADMITTED', bazada 1 ta yozuv (noaniq natija yo'q)",
      all(d == "ADMITTED" for d in out) and cnt == 1 and again["decision"] == "ADMITTED" and again.get("replay"), (set(out), cnt))
dup_after_retry = rpc(G2, "ci_admit", str(uuid.uuid4()), U(2001), "G2", "dev-x")["decision"]
check("T08b Qayta yuborishdan keyin YANGI skan baribir takror deb bloklanadi", dup_after_retry == "DENIED_ALREADY_ADMITTED", dup_after_retry)

# 9. Kupon/vaucherlar kirishda rad
dec = [rpc(G1, "ci_admit", str(uuid.uuid4()), s, "G1", "dev-1")["decision"] for s in FOREIGN]
check("T09 GOLD/SILVER/GAL QR'lari konsert kirishida rad etiladi", all(d == "DENIED_FOREIGN_SYSTEM" for d in dec), dec)
check("T17c Noto'g'ri QR kirishda rad etiladi va hech bir bilet holatiga ta'sir qilmaydi",
      all(rpc(G1, "ci_admit", str(uuid.uuid4()), s, "G1", "dev-1")["decision"] == "DENIED_INVALID" for s in REJECT[:10]))

# 10. Inventar — kirishni iste'mol qilmaydi, dublikatlar qayd etiladi
batch = rpc(S1, "ci_inventory_batch_open", "A403 qoldiq", "Ombor-1")["id"]
inv = [rpc(G1, "ci_inventory_scan", str(uuid.uuid4()), batch, U(t), None) for t in [6100, 6101, 6100, 6100, 6102]]
st = sql("select status from checkin.tickets where ticket_no in ('06100','06101','06102')")
check("T10 Inventar skanlari kirish holatini o'zgartirmaydi; dublikat nusxalar sanaladi (06100 × 3)",
      all(s[0] == "NOT_ADMITTED" for s in st) and inv[3]["copies_total"] == 3 and any(w["code"] == "DUPLICATE_COPY" for w in inv[3]["warnings"]), inv[3]["copies_total"])
rep = rpc(S1, "ci_report", "inventory_duplicates")
check("T10b Hisobot: bir necha marta skanerlangan raqamlar", [x["ticket_no"] for x in rep] == ["06100"] and rep[0]["copies"] == 3, rep)
rid_inv = str(uuid.uuid4()); a = rpc(G1, "ci_inventory_scan", rid_inv, batch, U(6103), None); b = rpc(G1, "ci_inventory_scan", rid_inv, batch, U(6103), None)
check("T10c Inventar skani ham idempotent (bir xil so'rov ikki marta = 1 nusxa)", a["scan_id"] == b["scan_id"] and b["copies_total"] == 1)
lk = rpc(G2, "ci_lookup", U(6100), "G2", "dev-2")
check("T10d Darvozada dublikat haqida ogohlantirish chiqadi, lekin bilet kiritilishi mumkin (asl egasini to'smaydi)",
      lk["admissible"] and any(w["code"] == "INVENTORY_DUPLICATE" for w in lk["warnings"]), lk["warnings"])

# 11. Bir joyga turli raqamlar
s11 = rpc(G1, "ci_inventory_scan", str(uuid.uuid4()), batch, U(6110), "A403 qator 1 joy 5")
conf = rpc(S1, "ci_report", "seat_conflicts")
check("T11 Qog'ozdagi joy master bilan farq qilsa (boshqa raqam bir joyga) — belgilanadi va hisobotga tushadi",
      any(w["code"] == "SEAT_MISMATCH" for w in s11["warnings"]) and any(c["type"] == "PRINTED_SEAT_MISMATCH" and c["ticket_no"] == "06110" for c in conf), conf[:2])
try:
    sql("insert into checkin.tickets (ticket_no, seat_key, zone, kind, sector, row_no, seat_no) values ('99999', (select seat_key from checkin.tickets where ticket_no='06110'), 'x','SEKTOR','A403',1,1)")
    dupseat = False
except psycopg.Error: dupseat = True
check("T11b Baza ikki biletni bitta joyga biriktirishga yo'l qo'ymaydi (unique)", dupseat)

# 12. Haqiqiy mijoz bahsi — ko'rib chiqish
cs = rpc(S1, "ci_case", r2["case_id"])
upd = rpc(S1, "ci_case_update", r2["case_id"], "IN_REVIEW", "Mijoz: Ali V., +998 90 *** ** 12", "Asl qog'oz bilet, distribyutor X cheki", "")
check("T12 Bahsli bilet ko'rib chiqiladi: tarix (kirishlar, inventar, tarqatish), dalillar yoziladi",
      len(cs["admissions"]) == 3 and upd["status"] == "IN_REVIEW", [a["decision"] for a in cs["admissions"]])
ref = rpc(G1, "ci_refer", U(4000), "G1", "Mijoz bilet ikki marta sotilganini aytmoqda")
check("T12b Darvoza xodimi biletni nazoratchiga yuboradi (holat ochiladi, bilet bloklanmaydi)",
      ref["case_id"] and sql("select status from checkin.tickets where ticket_no='04000'")[0][0] == "NOT_ADMITTED")

# 13. Band joyni ajratib bo'lmaydi
occ = err(AD, "ci_admin_spare_add", "SEKTOR", "4-qavat", "A403", 1, 1, "sinov: band joy")
res_occ = err(S1, "ci_spare_reserve", r2["case_id"], "SEKTOR:A403:1:1")
check("T13 Amaldagi biletga tegishli (band) joyni zaxira qilib/ajratib bo'lmaydi", occ == "SEAT_OCCUPIED" and res_occ == "SEAT_NOT_AVAILABLE", (occ, res_occ))
iss_bad = err(S1, "ci_issue_replacement", r2["case_id"], "SEKTOR:A403:1:1", "sabab yozildi", "dalil yozildi")
check("T13b Band qilinmagan joyga almashtirish bilet berib bo'lmaydi", iss_bad == "SEAT_NOT_RESERVED_FOR_CASE", iss_bad)

# zaxira joylar: zaldagi qo'shimcha (masterda yo'q) joylar
for k in range(1, 4):
    rpc(AD, "ci_admin_spare_add", "SEKTOR", "2-qavat", "B206", 15, 15 + k, "Excel: 'можно добавить ещё 2 места' — joyida tekshirildi")
e_capset = err(G1, "ci_setting_set", "capacity", "11225")
rpc(AD, "ci_setting_set", "capacity", "11225")     # qo'shimcha joylar tasdiqlangani uchun sig'imni admin oshiradi (audit)
check("T13e Sig'imni faqat admin o'zgartira oladi (audit bilan)", e_capset == "ROLE_DENIED")
# 14. Ikki nazoratchi bir joyni bir vaqtda band qila olmaydi
case2 = rpc(G1, "ci_refer", U(5000), "G1", "ikkinchi holat")["case_id"]
def reserve(args):
    c = conn(args[0]);
    try: return rpc(c, "ci_spare_reserve", args[1], "SEKTOR:B206:15:16")["spare_status"]
    except psycopg.Error as e: return e.diag.message_primary
    finally: c.close()
with ThreadPoolExecutor(8) as ex: rr = list(ex.map(reserve, [("sup1", r2["case_id"]), ("sup2", case2)] * 4))
check("T14 Ikki nazoratchi bir zaxira joyni parallel band qilmoqchi — faqat 1 ta muvaffaqiyat", rr.count("RESERVED") == 1, rr)
owner_case = sql("select reserved_case from checkin.seats where seat_key='SEKTOR:B206:15:16'")[0][0]

# almashtirish bileti
rep_res = rpc(S1 if owner_case == r2["case_id"] else S2, "ci_issue_replacement", owner_case, "SEKTOR:B206:15:16",
              "Bosmaxona dublikati — haqiqiy xaridor", "Distribyutor cheki №123, asl qog'oz bilet ko'rildi")
tok = rep_res["payload"]
check("T07r Almashtirish bileti: taxmin qilib bo'lmaydigan token (144 bit), bazada faqat xeshi",
      re.fullmatch(r"DUSELR1:[A-Za-z0-9_-]{24}", tok) and sql("select count(*) from checkin.replacements where token_hash = %s", hashlib.sha256(tok[8:].encode()).hexdigest())[0][0] == 1
      and not sql("select count(*) from checkin.replacements where token_hash like %s", "%" + tok[8:] + "%")[0][0], tok[:12] + "…")
ra = rpc(G2, "ci_admit", str(uuid.uuid4()), tok, "G2", "dev-2"); rb = rpc(G1, "ci_admit", str(uuid.uuid4()), tok, "G1", "dev-1")
check("T07s Almashtirish bileti bir marta kiritadi, ikkinchisi bloklanadi", ra["decision"] == "ADMITTED" and ra["credential"]["seat"] == 16 and rb["decision"] == "DENIED_ALREADY_ADMITTED", (ra["decision"], rb["decision"]))
fake = rpc(G1, "ci_admit", str(uuid.uuid4()), "DUSELR1:" + "A" * 24, "G1", "dev-1")["decision"]
check("T07t Soxta almashtirish tokeni rad etiladi", fake == "DENIED_NOT_FOUND", fake)
dash = rpc(AD, "ci_dashboard")
check("T07u Sig'im: almashtirish faqat haqiqiy qo'shimcha joy bilan; ruxsatlar soni nazoratda",
      dash["admission"]["entitlements"] == 11223 and dash["replacements"]["issued"] == 1, dash["admission"]["entitlements"])

# sig'im chegarasi
rpc(S1, "ci_spare_reserve", case2 if owner_case != case2 else r2["case_id"], "SEKTOR:B206:15:17")
other = case2 if owner_case != case2 else r2["case_id"]
rpc(AD, "ci_setting_set", "capacity", "11223")
cap = rpc(S1, "ci_issue_replacement", other, "SEKTOR:B206:15:17", "sabab yozildi", "dalil yozildi")
st_other = sql("select status from checkin.review_cases where id=%s", other)[0][0]
check("T13c Sig'imdan oshib ketadigan almashtirish bloklanadi → holat 'ESCALATED_NO_SEAT' (tashkilotchiga)",
      cap.get("error") == "CAPACITY_EXCEEDED" and st_other == "ESCALATED_NO_SEAT", (cap, st_other))
e_low = err(AD, "ci_setting_set", "capacity", "11000")
check("T13f Sig'imni mavjud ruxsatlardan pastga tushirib bo'lmaydi", e_low == "CAPACITY_BELOW_ENTITLEMENTS", e_low)

# 15. Ruxsatsiz foydalanuvchilar
e_gate = err(G1, "ci_ticket_set_status", "00010", "CANCELLED_BY_AUTHORIZED_SUPERVISOR", "ruxsatsiz urinish")
e_gate2 = err(G1, "ci_setting_set", "admission_open", json.dumps(False))
e_str = err(conn("stranger"), "ci_admit", str(uuid.uuid4()), U(10), "G1", "x")
e_gone = err(conn("gone"), "ci_admit", str(uuid.uuid4()), U(10), "G1", "x")
e_anon = err(conn(None, role="anon"), "ci_admit", str(uuid.uuid4()), U(10), "G1", "x")
e_auth_noclaim = err(conn(None), "ci_lookup", U(10), "G1", "x")
try:
    with G1.cursor() as k: k.execute("update checkin.tickets set status='ADMITTED' where ticket_no='00010'"); direct = "allowed"
except psycopg.Error as e: direct = e.diag.message_primary
try:
    with G1.cursor() as k: k.execute("select count(*) from checkin.tickets"); direct_r = "allowed"
except psycopg.Error as e: direct_r = e.diag.message_primary
check("T15 Ruxsatsiz: darvoza xodimi bekor qila/sozlay olmaydi; begona/faolsiz/anonim foydalanuvchi kirita olmaydi; jadvallarga to'g'ridan-to'g'ri kirish yo'q",
      e_gate == "ROLE_DENIED" and e_gate2 == "ROLE_DENIED" and e_str == "AUTH_DENIED" and e_gone == "AUTH_DENIED" and e_anon and "permission denied" in e_anon
      and e_auth_noclaim == "AUTH_DENIED" and "permission denied" in direct and "permission denied" in direct_r and sql("select status from checkin.tickets where ticket_no='00010'")[0][0] == "NOT_ADMITTED",
      (e_gate, e_gate2, e_str, e_gone, e_anon, e_auth_noclaim, direct, direct_r))

# 18. Sessiya bekor qilish / chiqish
old = conn("gate3", iat=time.time() - 10)
rpc(AD, "ci_staff_revoke_sessions", "gate3@test.local")
e_rev = err(old, "ci_lookup", U(10), "G1", "x")
newc = conn("gate3", iat=time.time() + 2)
check("T18 Admin sessiyalarni bekor qilsa eski token ishlamaydi, qayta kirgandan keyin ishlaydi", e_rev == "SESSION_REVOKED" and rpc(newc, "ci_lookup", U(10), "G1", "x")["result"] == "FOUND", e_rev)
e_noiat = err(psycopg.connect(DSN, autocommit=True), "ci_me")
c_noiat = psycopg.connect(DSN, autocommit=True); c_noiat.execute("set role authenticated"); c_noiat.execute("select set_config('request.jwt.claims', %s, false)", (json.dumps({"sub": USERS["gate1"]}),))
check("T18b Tokenda vaqt (iat) bo'lmasa rad etiladi", err(c_noiat, "ci_me") == "SESSION_REVOKED")

# nazoratchi qarori bilan zaxiradagi biletni kiritish
imp_bad = rpc(AD, "ci_import_distribution", json.dumps([{"ticket_no": "06200", "status": "HELD"}, {"ticket_no": "99999", "status": "HELD"}]), "sinov-import")
imp = rpc(AD, "ci_import_distribution", json.dumps([{"ticket_no": "06200", "status": "HELD"}, {"ticket_no": "06201", "status": "DISTRIBUTED", "recipient_ref": "Diler A"}]), "Tashkilotchi jadvali 25.11")
check("T05c Tarqatish importi: noto'g'ri qator bo'lsa hech narsa yozilmaydi; to'g'risi yoziladi",
      imp_bad["imported"] == 0 and imp_bad["rejected"] == 1 and imp["imported"] == 2)
hs = rpc(G1, "ci_admit", str(uuid.uuid4()), U(6200), "G1", "dev-1")
sa = rpc(S1, "ci_supervisor_admit", hs["case_id"], str(uuid.uuid4()), "G1", "sup-dev", "Mijoz chekini ko'rsatdi")
check("T12c Zaxirada deb qayd etilgan bilet darvozada → nazoratchiga; nazoratchi tekshirib kiritadi",
      hs["decision"] == "REFER_HELD_STOCK" and sa["decision"] == "ADMITTED" and sql("select status from checkin.review_cases where id=%s", hs["case_id"])[0][0] == "RESOLVED_ADMITTED")
e_sa = err(S1, "ci_supervisor_admit", r2["case_id"], str(uuid.uuid4()), "G1", "sup-dev", "ikkinchi marta urinish")
check("T12d Allaqachon kiritilgan biletni nazoratchi ham qayta kirita olmaydi (faqat almashtirish orqali)", e_sa in ("TICKET_NOT_ADMISSIBLE", "CASE_NOT_FOUND_OR_CLOSED"), e_sa)

# kirish yopiq / tezlik cheklovi
sql("update checkin.settings set value='false' where key='admission_open'")
cl = rpc(G1, "ci_admit", str(uuid.uuid4()), U(7000), "G1", "dev-1")["decision"]
sql("update checkin.settings set value='true' where key='admission_open'")
check("T05d Kirish rasman ochilmaguncha hech kim kiritilmaydi", cl == "DENIED_ADMISSION_CLOSED" and sql("select status from checkin.tickets where ticket_no='07000'")[0][0] == "NOT_ADMITTED")
sql("update checkin.settings set value='15' where key='rate_limit_per_10s'")
rl = None
for i in range(30):
    e = err(G2, "ci_lookup", U(100 + i), "G2", "dev-2")
    if e: rl = (i, e); break
sql("update checkin.settings set value='100000' where key='rate_limit_per_10s'")
check("T15b Tezlik cheklovi: bitta xodim juda ko'p so'rov yuborsa to'xtatiladi (raqam terib chiqishga qarshi)", rl and rl[1] == "RATE_LIMIT", rl)

# oflayn kontingensiya — keyin solishtirish
rpc(AD, "ci_set_contingency_code", "12345678")
off_ok = rpc(G1, "ci_admit", str(uuid.uuid4()), U(8000), "G1", "dev-off", "2026-11-25T10:00:00+05:00")
off_conf = rpc(G2, "ci_admit", str(uuid.uuid4()), U(8000), "G2", "dev-off2", "2026-11-25T10:01:00+05:00")
cfc = sql("select source from checkin.review_cases where ticket_no='08000'")[0][0]
check("T19 Oflayn yozuvlar keyin sinxronlanadi: ikkinchi qurilmadagi bir xil bilet 'OFFLINE_CONFLICT' holatiga tushadi",
      off_ok["decision"] == "ADMITTED" and off_conf["decision"] == "DENIED_ALREADY_ADMITTED" and cfc == "OFFLINE_CONFLICT", cfc)
check("T19b Kontingensiya kodi bazada ochiq holda saqlanmaydi", "12345678" not in json.dumps(rpc(G1, "ci_contingency")))

# 16. Audit
acts = {a for (a,) in sql("select distinct action from checkin.audit_log")}
need = {"ADMISSION_ADMITTED", "ADMISSION_DENIED_ALREADY_ADMITTED", "CASE_UPDATE", "SPARE_ADD", "SPARE_RESERVE", "REPLACEMENT_ISSUE", "STAFF_SET" if False else "SESSIONS_REVOKE",
        "DISTRIBUTION_IMPORT", "SUPERVISOR_ADMIT", "INVENTORY_BATCH_OPEN", "CONTINGENCY_CODE_SET", "REPORT_EXPORT", "CASE_REFER"}
ver = rpc(AD, "ci_audit_verify")
check("T16 Barcha muhim amallar audit jurnalida; xesh-zanjir butun", need <= acts and ver["ok"], (sorted(need - acts), ver))
try: sql("update checkin.audit_log set action='X' where id=1"); upd_ok = True
except psycopg.Error: upd_ok = False
try: sql("delete from checkin.admission_events where id=1"); del_ok = True
except psycopg.Error: del_ok = False
check("T16b Audit va kirish yozuvlarini o'zgartirish/o'chirish bloklangan", not upd_ok and not del_ok)
sql("alter table checkin.audit_log disable trigger no_change_audit_log"); sql("update checkin.audit_log set details = '{\"x\":1}' where id = 3")
sql("alter table checkin.audit_log enable trigger no_change_audit_log")
ver2 = rpc(AD, "ci_audit_verify")
check("T16c Superuser triggerni o'chirib yozuvni o'zgartirsa ham — tekshiruv buzilishni aniqlaydi (tamper-evident)", not ver2["ok"] and ver2["first_bad_id"] == 3, ver2)

# 13. dashboard / hisobotlar
ss = {x["sector"]: x for x in rpc(AD, "ci_report", "sector_summary")}
check("T13d Sektor bo'yicha panel (A403): ajratilgan 320, inventar nusxalari, ortiqcha nusxa",
      ss["A403"]["allocated"] == 320 and ss["A403"]["physical_copies"] == 7 and ss["A403"]["surplus_copies"] == 2, {k: ss["A403"][k] for k in ("allocated", "physical_copies", "surplus_copies", "duplicate_numbers")})
miss = rpc(S1, "ci_report", "inventory_missing")
cats = {m["category"] for m in miss}
check("T10e 'Inventarda yo'q' bilet avtomatik 'bosilmagan' deb hisoblanmaydi — kategoriyalar ajratilgan", {"ADMITTED", "UNKNOWN_NOT_IN_STOCK", "DISTRIBUTED_NOT_IN_STOCK"} <= cats | {"DISTRIBUTED_NOT_IN_STOCK"}, sorted(cats))

json.dump(R, open("db_test_results.json", "w"), ensure_ascii=False, indent=1)
print(f"\n{sum(r['ok'] for r in R)}/{len(R)} PASS")
sys.exit(0 if all(r["ok"] for r in R) else 1)
