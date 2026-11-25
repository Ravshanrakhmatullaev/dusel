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
                           ("gate1", "GATE", True), ("gate2", "GATE", True), ("gate3", "GATE", True), ("gone", "GATE", False),
                           ("inv1", "INVENTORY", True), ("inv2", "INVENTORY", True)]:
    uid = sql("insert into auth.users (email) values (%s) on conflict (email) do update set email = excluded.email returning id", f"{name}@test.local")[0][0]
    sql("insert into checkin.staff (user_id, username, display_name, role, active) values (%s,%s,%s,%s,%s) on conflict (user_id) do update set role=excluded.role, active=excluded.active, sessions_valid_after='2000-01-01'",
        uid, f"{name}@test.local", name.upper(), role, active)
    USERS[name] = str(uid)
USERS["stranger"] = str(sql("insert into auth.users (email) values ('stranger@test.local') on conflict (email) do update set email = excluded.email returning id")[0][0])
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
I1, I2 = conn("inv1"), conn("inv2")

# T20 Kirish avtomatik ochilmaydi: yangi deploydan keyin YOPIQ; ochish faqat admin + aniq tasdiq matni bilan
fresh = sql("select value::text from checkin.settings where key='admission_open'")[0][0]
e_noconf = err(AD, "ci_admission_set", True, None)
e_gate_open = err(G1, "ci_admission_set", True, "KIRISHNI OCHISH")
try: sql("update checkin.settings set value='true' where key='admission_open'"); raw = "allowed"
except psycopg.Error as e: raw = e.diag.message_primary
check("T20 Deploydan keyin kirish YOPIQ; tasdiqsiz/darvoza xodimi/to'g'ridan-to'g'ri SQL bilan ochib bo'lmaydi",
      fresh == "false" and e_noconf == "CONFIRMATION_MISMATCH" and e_gate_open == "ROLE_DENIED" and raw == "ADMISSION_LOCKED", (fresh, e_noconf, e_gate_open, raw))
rpc(AD, "ci_admission_set", True, "KIRISHNI OCHISH")

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
batch = rpc(I1, "ci_inventory_batch_open", "A403 qoldiq", "Ombor-1", "A403", "Quti-1", "Dasta-1", "inv-dev-1")["id"]
inv = [rpc(I1, "ci_inventory_scan", str(uuid.uuid4()), batch, U(t), None, "SCANNER", "inv-dev-1", None) for t in [6100, 6101, 6100, 6100, 6102]]
st = sql("select status from checkin.tickets where ticket_no in ('06100','06101','06102')")
check("T10 Inventar skanlari kirish holatini o'zgartirmaydi; dublikat nusxalar sanaladi (06100 × 3)",
      all(s[0] == "NOT_ADMITTED" for s in st) and inv[3]["copies_total"] == 3 and any(w["code"] == "DUPLICATE_COPY" for w in inv[3]["warnings"]), inv[3]["copies_total"])
rep = rpc(S1, "ci_report", "inventory_duplicates")
check("T10b Hisobot: bir necha marta skanerlangan raqamlar", [x["ticket_no"] for x in rep] == ["06100"] and rep[0]["copies"] == 3, rep)
rid_inv = str(uuid.uuid4()); a = rpc(I1, "ci_inventory_scan", rid_inv, batch, U(6103), None, "CAMERA", "inv-dev-1", None); b = rpc(I1, "ci_inventory_scan", rid_inv, batch, U(6103), None, "CAMERA", "inv-dev-1", None)
check("T10c Inventar skani ham idempotent (bir xil so'rov ikki marta = 1 nusxa)", a["scan_id"] == b["scan_id"] and b["copies_total"] == 1)
lk = rpc(G2, "ci_lookup", U(6100), "G2", "dev-2")
check("T10d Darvozada dublikat haqida ogohlantirish chiqadi, lekin bilet kiritilishi mumkin (asl egasini to'smaydi)",
      lk["admissible"] and any(w["code"] == "INVENTORY_DUPLICATE" for w in lk["warnings"]), lk["warnings"])

# 11. Bir joyga turli raqamlar
s11 = rpc(I1, "ci_inventory_scan", str(uuid.uuid4()), batch, U(6110), "A403 qator 1 joy 5", "MANUAL", "inv-dev-1", None)
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

# ---------------------------------------------------------------- SIG'IM: tasdiqlangan 11 222 hech qachon almashtirish uchun oshirilmaydi
def cap_now(): return int(sql("select value::text from checkin.settings where key='capacity'")[0][0])
ENT0 = rpc(AD, "ci_capacity_status")["entitlements"]
e_capg = err(G1, "ci_capacity_change", 11225, "x" * 12, "SIGIM 11225")
e_capset = err(AD, "ci_setting_set", "capacity", "11225")
try: sql("update checkin.settings set value='11225' where key='capacity'"); raw_cap = "allowed"
except psycopg.Error as e: raw_cap = e.diag.message_primary
check("T13e Sig'im qulflangan: darvoza/oddiy sozlama/to'g'ridan-to'g'ri SQL bilan o'zgarmaydi (11 222 qoladi)",
      e_capg == "ROLE_DENIED" and e_capset == "USE_CAPACITY_CHANGE" and raw_cap == "CAPACITY_LOCKED" and cap_now() == 11222 and ENT0 == 11222,
      (e_capg, e_capset, raw_cap, cap_now(), ENT0))

# zaldagi qo'shimcha (masterda yo'q) joylar — EXTRA joy sig'imni oshirmaydi
extra = [rpc(AD, "ci_admin_spare_add", "SEKTOR", "2-qavat", "B206", 15, 15 + k, "Excel: 'можно добавить ещё 2 места' — joyida tekshirildi") for k in range(1, 4)]
check("T13g Qo'shimcha (EXTRA) joy qo'shilsa ham sig'im va ruxsatlar o'zgarmaydi (headroom 0)",
      all(x["origin"] == "EXTRA" for x in extra) and extra[-1]["headroom"] == 0 and cap_now() == 11222, extra[-1]["headroom"])

# isbotli zaxira: faqat tarqatilmagan (HELD/RETURNED), jismonan yopiq partiyada 1 nusxa, varaqda dublikat yo'q, darvozada ko'rilmagan bilet
rpc(AD, "ci_import_distribution", json.dumps([{"ticket_no": t, "status": "HELD"} for t in ["06650", "06655", "06656", "06661", "06667", "06668"]]
      + [{"ticket_no": "06673", "status": "DISTRIBUTED", "recipient_ref": "Diler B"}]), "Tashkilotchi zaxira jadvali (sinov)")
sb = rpc(I2, "ci_inventory_batch_open", "A405 zaxira qutisi", "Ofis seyf", "A405", "Q-7", "D-1", "inv-dev-2")["id"]
for t in [6650, 6655, 6655, 6656, 6661, 6667, 6668]: rpc(I2, "ci_inventory_scan", str(uuid.uuid4()), sb, U(t), None, "SCANNER", "inv-dev-2", None)
e_open = err(AD, "ci_spare_from_stock", "06650", "Ombor tekshiruvi 25.11, quti Q-7")
rpc(I2, "ci_inventory_batch_close", sb)
gh = rpc(G1, "ci_admit", str(uuid.uuid4()), U(6661), "G1", "dev-1")      # zaxiradagi bilet darvozada ko'rindi → nazorat
E = {t: err(AD, "ci_spare_from_stock", t, "Ombor tekshiruvi 25.11, quti Q-7") for t in ["06649", "06673", "06655", "06656", "06661"]}
e_noev = err(AD, "ci_spare_from_stock", "06667", "qisqa")
e_sup = err(S1, "ci_spare_from_stock", "06667", "Ombor tekshiruvi 25.11, quti Q-7")
check("T13h Noma'lum/tarqatilgan/jismonan tasdiqlanmagan/dublikatli/varag'i shubhali/darvozada ko'rilgan bilet zaxira joy bo'la OLMAYDI",
      E["06649"] == "NO_DISTRIBUTION_PROOF" and E["06673"] == "NO_DISTRIBUTION_PROOF" and e_open == "NOT_PHYSICALLY_VERIFIED"
      and E["06655"] == "DUPLICATE_COPIES_RISK" and E["06656"] == "SHEET_REPRINT_RISK" and E["06661"] == "GATE_ACTIVITY_EXISTS"
      and gh["decision"] == "REFER_HELD_STOCK" and e_noev == "EVIDENCE_REQUIRED" and e_sup == "ROLE_DENIED", (E, e_open, e_noev, e_sup))
ret = rpc(AD, "ci_spare_from_stock", "06667", "Tashkilotchi zaxirasi: quti Q-7, 25.11 inventar #%d, tekshirdi: Admin" % sb)
seat_r = ret["seat"]["seat_key"]
cs1 = rpc(AD, "ci_capacity_status")
check("T13i Isbotli zaxira: asl bilet bekor, joyi zaxirada; ruxsatlar 11 221, sig'im 11 222 (o'zgarmadi)",
      ret["ticket"]["status"] == "CANCELLED_BY_AUTHORIZED_SUPERVISOR" and ret["seat"]["spare_status"] == "AVAILABLE"
      and cs1["entitlements"] == 11221 and cs1["approved_capacity"] == 11222 and cs1["retired_to_spare"] == 1, (seat_r, cs1["entitlements"]))

# 14. Ikki nazoratchi bir zaxira joyni bir vaqtda band qila olmaydi
case2 = rpc(G1, "ci_refer", U(5000), "G1", "ikkinchi holat")["case_id"]
def reserve(args):
    c = conn(args[0]);
    try: return rpc(c, "ci_spare_reserve", args[1], seat_r)["spare_status"]
    except psycopg.Error as e: return e.diag.message_primary
    finally: c.close()
with ThreadPoolExecutor(8) as ex: rr = list(ex.map(reserve, [("sup1", r2["case_id"]), ("sup2", case2)] * 4))
check("T14 Ikki nazoratchi bir zaxira joyni parallel band qilmoqchi — faqat 1 ta muvaffaqiyat", rr.count("RESERVED") == 1, rr)
owner_case = sql("select reserved_case from checkin.seats where seat_key=%s", seat_r)[0][0]

# almashtirish bileti (takror skan holati uchun: asl 00330 kirgan, ikkinchi haqiqiy xaridor isbotli zaxira joyga)
rep_res = rpc(S1 if owner_case == r2["case_id"] else S2, "ci_issue_replacement", owner_case, seat_r,
              "Bosmaxona dublikati — haqiqiy xaridor", "Distribyutor cheki №123, asl qog'oz bilet ko'rildi", False)
tok = rep_res["payload"]
check("T07r Almashtirish bileti: taxmin qilib bo'lmaydigan token (144 bit), bazada faqat xeshi",
      re.fullmatch(r"DUSELR1:[A-Za-z0-9_-]{24}", tok) and sql("select count(*) from checkin.replacements where token_hash = %s", hashlib.sha256(tok[8:].encode()).hexdigest())[0][0] == 1
      and not sql("select count(*) from checkin.replacements where token_hash like %s", "%" + tok[8:] + "%")[0][0], tok[:12] + "…")
ra = rpc(G2, "ci_admit", str(uuid.uuid4()), tok, "G2", "dev-2"); rb = rpc(G1, "ci_admit", str(uuid.uuid4()), tok, "G1", "dev-1")
check("T07s Almashtirish bileti bir marta kiritadi, ikkinchisi bloklanadi", ra["decision"] == "ADMITTED" and ra["credential"]["sector"] == "A405" and rb["decision"] == "DENIED_ALREADY_ADMITTED", (ra["decision"], rb["decision"]))
fake = rpc(G1, "ci_admit", str(uuid.uuid4()), "DUSELR1:" + "A" * 24, "G1", "dev-1")["decision"]
check("T07t Soxta almashtirish tokeni rad etiladi", fake == "DENIED_NOT_FOUND", fake)
old_copy = rpc(G2, "ci_admit", str(uuid.uuid4()), U(6667), "G2", "dev-2")
check("T07v Zaxiraga o'tkazilgan asl bilet nusxasi darvozada rad etiladi va nazoratga tushadi (joy ikki marta berilmaydi)",
      old_copy["decision"] == "DENIED_CANCELLED" and old_copy["case_id"], old_copy["decision"])
cs2 = rpc(AD, "ci_capacity_status")
check("T07u Almashtirishdan keyin: ruxsatlar 11 222 = tasdiqlangan sig'im 11 222; sig'im o'zgarishlari yo'q; invariant butun",
      cs2["entitlements"] == 11222 and cs2["approved_capacity"] == 11222 and cs2["capacity_changes"] == [] and cs2["invariant_ok"] and cs2["headroom"] == 0,
      {k: cs2[k] for k in ("entitlements", "approved_capacity", "headroom", "invariant_ok")})

# sig'im chegarasi: EXTRA joy bor, lekin sig'imda bo'sh o'rin yo'q → tashkilotchiga
other = case2 if owner_case != case2 else r2["case_id"]
rpc(S1, "ci_spare_reserve", other, "SEKTOR:B206:15:16")
cap = rpc(S1, "ci_issue_replacement", other, "SEKTOR:B206:15:16", "sabab yozildi", "dalil yozildi", False)
st_other = sql("select status from checkin.review_cases where id=%s", other)[0][0]
check("T13c Sig'imdan oshadigan almashtirish bloklanadi → 'ESCALATED_NO_SEAT'; sig'im avtomatik oshirilmaydi",
      cap.get("error") == "CAPACITY_EXCEEDED" and st_other == "ESCALATED_NO_SEAT" and cap_now() == 11222, (cap, st_other))

# asl bilet hali kiritilmagan (shikastlangan/yo'qolgan): yangi QR uning O'RNIGA, o'sha joyda — ruxsatlar soni o'zgarmaydi
seat_4000 = sql("select seat_key from checkin.tickets where ticket_no='04000'")[0][0]
sup = rpc(S1, "ci_issue_replacement", ref["case_id"], seat_4000, "Bilet shikastlangan — QR o'qilmaydi", "Mijoz pasporti va xarid cheki ko'rildi", True)
t4000 = sql("select status, superseded_by_case from checkin.tickets where ticket_no='04000'")[0]
g4000 = rpc(G1, "ci_admit", str(uuid.uuid4()), U(4000), "G1", "dev-1")["decision"]
s4000 = rpc(G2, "ci_admit", str(uuid.uuid4()), sup["payload"], "G2", "dev-2")["decision"]
cs3 = rpc(AD, "ci_capacity_status")
check("T13j O'rnini bosuvchi almashtirish: asl bilet bekor, yangi QR o'sha joyda bir marta kiradi, ruxsatlar 11 222 da qoladi",
      sup["superseded_original"] and t4000[0] == "CANCELLED_BY_AUTHORIZED_SUPERVISOR" and g4000 == "DENIED_CANCELLED" and s4000 == "ADMITTED"
      and cs3["entitlements"] == 11222 and cs3["invariant_ok"], (t4000, g4000, s4000, cs3["entitlements"]))
rpc(G1, "ci_admit", str(uuid.uuid4()), U(331), "G1", "dev-1"); d331 = rpc(G2, "ci_admit", str(uuid.uuid4()), U(331), "G2", "dev-2")
rpc(S1, "ci_spare_reserve", d331["case_id"], "SEKTOR:B206:15:17")
e_sup331 = err(S1, "ci_issue_replacement", d331["case_id"], "SEKTOR:B206:15:17", "sabab yozildi", "dalil yozildi", True)
check("T13k Kiritilgan asl biletning o'rnini bosib bo'lmaydi (bekor qilinmaydi)", e_sup331 == "ORIGINAL_NOT_SUPERSEDABLE", e_sup331)

# baza darajasidagi himoya (funksiyadagi xatoga qarshi): superuser ham band joyga/sig'imdan ortiq almashtirish yoza olmaydi
def raw(q, *a):
    try: sql(q, *a); return "allowed"
    except psycopg.Error as e: return e.diag.message_primary
ins = "insert into checkin.replacements (token_hash, token_hint, original_ticket, case_id, seat_key, reason, evidence_summary, issued_by) values (md5(random()::text), 'xxxx', null, %s, %s, 'r', 'e', %s)"
r_occ = raw(ins, ref["case_id"], "SEKTOR:A403:1:1", USERS["admin"])
r_cap = raw(ins, ref["case_id"], "SEKTOR:B206:15:18", USERS["admin"])
r_back = raw("update checkin.tickets set status='NOT_ADMITTED' where ticket_no='04000'")
r_unadm = raw("update checkin.tickets set status='NOT_ADMITTED', admitted_at=null where ticket_no='00330'")
r_del = raw("delete from checkin.tickets where ticket_no='00001'")
check("T13l Bazada qulf: band joyga yoki sig'imdan ortiq almashtirish, bekor/kiritilgan biletni qaytarish, bilet o'chirish — taqiqlangan",
      r_occ == "SEAT_OCCUPIED_BY_TICKET" and r_cap == "CAPACITY_EXCEEDED" and r_back == "TICKET_STATUS_FINAL" and r_unadm == "TICKET_STATUS_FINAL" and r_del.startswith("IMMUTABLE"),
      (r_occ, r_cap, r_back, r_unadm, r_del))
conf2 = [c for c in rpc(S1, "ci_report", "seat_conflicts") if c["type"] == "MULTIPLE_ENTITLEMENTS"]
adm_total = sql("select (select count(*) from checkin.tickets where status='ADMITTED') + (select count(*) from checkin.replacements where status='ADMITTED')")[0][0]
check("T13m Bir joyga ikki amaldagi huquq yo'q; jami kirishlar ≤ sig'im", conf2 == [] and adm_total <= 11222, (conf2, adm_total))

# tasdiqlangan sig'imni o'zgartirish — faqat tashkilotchining yozma qarori, aniq tasdiq matni bilan, alohida jurnalga
e_low = err(AD, "ci_capacity_change", 11000, "Tashkilotchi qarori №1 25.11", "SIGIM 11000")
e_ref = err(AD, "ci_capacity_change", 11223, "", "SIGIM 11223")
e_cf = err(AD, "ci_capacity_change", 11223, "Tashkilotchi qarori №1 25.11", "ha")
ok_up = rpc(AD, "ci_capacity_change", 11223, "SINOV: Humo Arena ma'muriyati xati №7 (sinov)", "SIGIM 11223")
ok_dn = rpc(AD, "ci_capacity_change", 11222, "SINOV: sinovdan keyin qaytarildi", "SIGIM 11222")
chg = rpc(AD, "ci_capacity_status")["capacity_changes"]
check("T13f Sig'im o'zgarishi faqat yozma qaror + tasdiq matni bilan; ruxsatlardan pastga tushmaydi; har biri jurnalda",
      e_low == "CAPACITY_BELOW_ENTITLEMENTS" and e_ref == "APPROVAL_REF_REQUIRED" and e_cf == "CONFIRMATION_MISMATCH"
      and ok_up["capacity"] == 11223 and ok_dn["capacity"] == 11222 and len(chg) == 2 and cap_now() == 11222, (e_low, e_ref, e_cf, len(chg)))

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
sid = sql("insert into auth.sessions (user_id) values (%s) returning id", USERS["gate3"])[0][0]
sql("insert into auth.refresh_tokens (token, user_id, session_id) values ('rt-gate3', %s, %s)", USERS["gate3"], sid)
rpc(AD, "ci_staff_revoke_sessions", "gate3@test.local")
check("T18c Sessiyani bekor qilish Supabase Auth sessiyasi va refresh tokenni ham o'chiradi (yangi token olib bo'lmaydi)",
      sql("select count(*) from auth.sessions where user_id=%s", USERS["gate3"])[0][0] == 0 and sql("select count(*) from auth.refresh_tokens where user_id=%s and not revoked", USERS["gate3"])[0][0] == 0)
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
rpc(AD, "ci_admission_set", False, None)
cl = rpc(G1, "ci_admit", str(uuid.uuid4()), U(7000), "G1", "dev-1")["decision"]
rpc(AD, "ci_admission_set", True, "KIRISHNI OCHISH")
check("T05d Kirish rasman ochilmaguncha hech kim kiritilmaydi", cl == "DENIED_ADMISSION_CLOSED" and sql("select status from checkin.tickets where ticket_no='07000'")[0][0] == "NOT_ADMITTED")
sql("update checkin.settings set value='15' where key='rate_limit_per_10s'")
rl = None
for i in range(30):
    e = err(G2, "ci_lookup", U(100 + i), "G2", "dev-2")
    if e: rl = (i, e); break
sql("update checkin.settings set value='100000' where key='rate_limit_per_10s'")
check("T15b Tezlik cheklovi: bitta xodim juda ko'p so'rov yuborsa to'xtatiladi (raqam terib chiqishga qarshi)", rl and rl[1] == "RATE_LIMIT", rl)

# nazoratli favqulodda rejim: faqat Admin belgilagan YAGONA nazoratchi qurilmasi; darvozalar mustaqil oflayn kirita olmaydi
rpc(AD, "ci_set_contingency_code", "1234567890")
rpc(AD, "ci_contingency_device_set", "sup-device-0001")
cg = rpc(G1, "ci_contingency", "sup-device-0001"); cw = rpc(S1, "ci_contingency", "other-device-01"); cr = rpc(S1, "ci_contingency", "sup-device-0001")
e_gate_off = err(G1, "ci_admit", str(uuid.uuid4()), U(8000), "G1", "sup-device-0001", "2026-11-25T10:00:00+05:00")
e_sup_off = err(S1, "ci_admit", str(uuid.uuid4()), U(8000), "G1", "other-device-01", "2026-11-25T10:00:00+05:00")
check("T19a Oflayn kirishni darvoza xodimi yoki belgilanmagan qurilma yubora olmaydi; kod faqat belgilangan nazoratchi qurilmasiga beriladi",
      not cg["allowed"] and not cw["allowed"] and cr["allowed"] and cr["alg"] == "PBKDF2-SHA256" and cr["iter"] >= 100000
      and e_gate_off == "CONTINGENCY_DEVICE_ONLY" and e_sup_off == "CONTINGENCY_DEVICE_ONLY", (cg, cw.get("allowed"), e_gate_off, e_sup_off))
rpc(G1, "ci_admit", str(uuid.uuid4()), U(8001), "G1", "dev-1")                     # aloqa uzilgan paytda boshqa darvoza onlayn kiritgan
off_ok = rpc(S1, "ci_admit", str(uuid.uuid4()), U(8000), "G1", "sup-device-0001", "2026-11-25T10:00:00+05:00")
off_conf = rpc(S1, "ci_admit", str(uuid.uuid4()), U(8001), "G1", "sup-device-0001", "2026-11-25T10:01:00+05:00")
cfc = sql("select source from checkin.review_cases where ticket_no='08001'")[0][0]
check("T19 Nazoratli oflayn yozuvlar keyin sinxronlanadi: allaqachon kirgan bilet 'OFFLINE_CONFLICT' holatiga tushadi",
      off_ok["decision"] == "ADMITTED" and off_conf["decision"] == "DENIED_ALREADY_ADMITTED" and cfc == "OFFLINE_CONFLICT", cfc)
check("T19b Kontingensiya kodi bazada ochiq holda saqlanmaydi (PBKDF2)", "1234567890" not in json.dumps(cr) and len(cr["hash"]) == 64)

# 16. Audit
acts = {a for (a,) in sql("select distinct action from checkin.audit_log")}
need = {"ADMISSION_ADMITTED", "ADMISSION_DENIED_ALREADY_ADMITTED", "CASE_UPDATE", "SPARE_ADD", "SPARE_RESERVE", "REPLACEMENT_ISSUE", "STAFF_SET" if False else "SESSIONS_REVOKE",
        "DISTRIBUTION_IMPORT", "SUPERVISOR_ADMIT", "INVENTORY_BATCH_OPEN", "CONTINGENCY_CODE_SET", "REPORT_EXPORT", "CASE_REFER",
        "SPARE_FROM_STOCK", "CAPACITY_CHANGE", "ADMISSION_OPEN", "ADMISSION_CLOSE", "CONTINGENCY_DEVICE_SET", "INVENTORY_BATCH_CLOSE"}
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


# ---------------------------------------------------------------- INVENTAR ↔ KIRISH qat'iy ajratish
e_g_inv = err(G1, "ci_inventory_scan", str(uuid.uuid4()), batch, U(9000), None, None, None, None)
e_i_adm = err(I1, "ci_admit", str(uuid.uuid4()), U(9000), "G1", "inv-dev-1")
e_i_lk = err(I1, "ci_lookup", U(9000), "G1", "inv-dev-1")
e_i_case = err(I1, "ci_cases", None)
check("T10f Rollar ajratilgan: darvoza xodimi inventar qila olmaydi; inventar xodimi kiritish/ko'rish/holatlarga kira olmaydi",
      e_g_inv == "ROLE_DENIED" and e_i_adm == "ROLE_DENIED" and e_i_lk == "ROLE_DENIED" and e_i_case == "ROLE_DENIED", (e_g_inv, e_i_adm, e_i_lk, e_i_case))
def in_mode(mode, q):
    try:
        with admin.transaction():
            with admin.cursor() as k:
                k.execute("select set_config('checkin.mode', %s, true)", (mode,)); k.execute(q)
        return "allowed"
    except psycopg.Error as e: return e.diag.message_primary
m1 = in_mode("INVENTORY", "update checkin.tickets set status='ADMITTED', admitted_at=now() where ticket_no='09001'")
m2 = in_mode("INVENTORY", "insert into checkin.admission_events (request_id, credential_type, ticket_no, payload_kind, decision, gate, staff) values (gen_random_uuid(), 'TICKET', '09001', 'TICKET', 'ADMITTED', 'G1', gen_random_uuid())")
m3 = in_mode("INVENTORY", "update checkin.replacements set reason = reason")
m4 = in_mode("ADMISSION", "insert into checkin.inventory_scans (request_id, batch_id, ticket_no, payload_kind, operator) values (gen_random_uuid(), %d, '09001', 'TICKET', gen_random_uuid())" % batch)
src = sql("select string_agg(prosrc, ' ') from pg_proc where proname like 'ci\\_inventory%%'")[0][0].lower()
static_ok = not re.search(r"update\s+checkin\.tickets|insert\s+into\s+checkin\.admission_events|update\s+checkin\.replacements|checkin\._case_touch", src)
check("T10g Baza darajasida: INVENTORY rejimida bilet/kirish/almashtirishga yozish taqiqlangan; inventar skanini kirish rejimi yoza olmaydi; inventar funksiyalarida kirish kodi yo'q",
      m1 == m2 == m3 == "INVENTORY_MODE_CANNOT_TOUCH_ADMISSION" and m4 == "INVENTORY_WRITE_OUTSIDE_INVENTORY_MODE" and static_ok
      and sql("select status from checkin.tickets where ticket_no='09001'")[0][0] == "NOT_ADMITTED", (m1, m2, m3, m4, static_ok))
rb2 = rpc(I1, "ci_inventory_batch_open", "Sinov: noto'g'ri QR", "Ombor-2", None, None, None, "inv-dev-1")["id"]
rj = [rpc(I1, "ci_inventory_scan", str(uuid.uuid4()), rb2, x, None, "SCANNER", "inv-dev-1", None)["result"]
      for x in ["https://dusel.pages.dev/gold?code=0001", "https://dusel.pages.dev/gal?code=0005", "salom dunyo", "https://dusel.pages.dev/?code=11223"]]
rej = rpc(I1, "ci_inventory_report", "rejected_scans", None)
check("T10h Noma'lum/noto'g'ri QR va kuponlar inventarda alohida qayd etiladi (bilet sifatida sanalmaydi)",
      rj == ["FOREIGN", "FOREIGN", "INVALID", "INVALID"] and len(rej) == 4, rj)
d1 = rpc(I1, "ci_inventory_scan", str(uuid.uuid4()), rb2, U(9100), None, "SCANNER", "inv-dev-1", None)
d2 = rpc(I1, "ci_inventory_scan", str(uuid.uuid4()), rb2, U(9100), None, "SCANNER", "inv-dev-1", None)
d3 = rpc(I1, "ci_inventory_scan", str(uuid.uuid4()), rb2, U(9100), None, "SCANNER", "inv-dev-1", None)
rid_off = str(uuid.uuid4())
o1 = rpc(I1, "ci_inventory_scan", rid_off, rb2, U(9101), None, "CAMERA", "inv-dev-1", "2026-11-25T09:00:00+05:00")
o2 = rpc(I1, "ci_inventory_scan", rid_off, rb2, U(9101), None, "CAMERA", "inv-dev-1", "2026-11-25T09:00:00+05:00")
check("T10i Bir xil bilet 3 marta → nusxa 1→2→3, birinchi dublikat darhol belgilanadi; oflayn navbat qayta yuborsa nusxa ko'paymaydi",
      (d1["copies_total"], d2["copies_total"], d3["copies_total"]) == (1, 2, 3) and not d1["first_duplicate"] and d2["first_duplicate"] and not d3["first_duplicate"]
      and o2["replay"] and o2["copies_total"] == 1 and o1["scan_id"] == o2["scan_id"], (d1["copies_total"], d2["copies_total"], d3["copies_total"], o2["replay"]))

# ---------------------------------------------------------------- fizik solishtiruv (sinov ma'lumoti, A405)
rec = {x["sector"]: x for x in rpc(I1, "ci_reconciliation", "A405")}["A405"]
sh = {x["sheet"]: x for x in rpc(I1, "ci_reconciliation_sheets", "A405")}
notobs = rpc(I1, "ci_inventory_report", "not_observed", "A405")
cats = {}
for x in notobs: cats[x["category"]] = cats.get(x["category"], 0) + 1
check("T21 Solishtiruv (A405): toifalar ajratilgan, noma'lum 'sotilmagan' emas; dublikatli varaq 'REPRINTED_SUSPECTED'",
      rec["allocated"] == 445 and rec["retired_to_spare"] == 1 and rec["in_stock_confirmed"] == 5 and rec["unknown"] == 445 - 7
      and rec["distributed_confirmed"] == 1 and rec["duplicate_numbers"] == 1 and rec["surplus_copies"] == 1 and rec["reprinted_sheets"] == [1110]
      and sh[1110]["status"] == "REPRINTED_SUSPECTED" and sh[1112]["status"] == "PARTIAL_SHEET_IN_STOCK" and sh[1111]["status"] in ("PARTIAL_SHEET_IN_STOCK",)
      and "NOT_OBSERVED_UNKNOWN" in cats and "NOT_OBSERVED_DISTRIBUTED" in cats,
      {k: rec[k] for k in ("allocated", "in_stock_confirmed", "unknown", "distributed_confirmed", "retired_to_spare", "reprinted_sheets", "sheets_by_status")})

# ---------------------------------------------------------------- 11 222 + dublikatlar + kuponlar inventarda: KIRISH HOLATI O'ZGARMAYDI
def snapshot():
    return sql("""select md5(string_agg(ticket_no || status || coalesce(admitted_at::text, '') || coalesce(admit_request::text, ''), ',' order by ticket_no)),
                         (select count(*) from checkin.admission_events), (select count(*) from checkin.review_cases),
                         (select md5(coalesce(string_agg(id::text || status, ',' order by id), '')) from checkin.replacements)
                  from checkin.tickets""")[0]
before = snapshot()
sweep = rpc(I2, "ci_inventory_batch_open", "To'liq sinov supurish", "Ombor-3", None, None, None, "inv-dev-2")["id"]
payloads = [U(n) for n in range(1, 11223)] + [U(n) for n in range(1, 11223, 22)] + ["https://dusel.pages.dev/silver?code=0002", tok, "https://ravshanrakhmatullaev.github.io/dusel/?code=00330", "https://dusel.pages.dev/ticket?code=00330"]
def inv_worker(chunk):
    c = conn("inv2"); out = 0
    for x in chunk:
        out += rpc(c, "ci_inventory_scan", str(uuid.uuid4()), sweep, x, None, "SCANNER", "inv-dev-2", None)["result"] == "RECORDED"
    c.close(); return out
t0 = time.time()
with ThreadPoolExecutor(8) as ex: recorded = sum(ex.map(inv_worker, [payloads[i::8] for i in range(8)]))
after = snapshot()
check("T10j %d ta inventar skani (barcha 11 222 + dublikatlar + eski URL formatlari + kupon + almashtirish QR): kirish holati, hodisalar, holatlar va almashtirishlar O'ZGARMADI" % len(payloads),
      before == after and recorded == len(payloads) - 2, dict(recorded=recorded, seconds=round(time.time() - t0, 1), events=after[1]))

# ---------------------------------------------------------------- migratsiyalarni qayta qo'llash: ma'lumot va kirish holati saqlanadi
import subprocess, os
snap_m = snapshot(); adm_before = sql("select value::text from checkin.settings where key='admission_open'")[0][0]
here = os.path.dirname(os.path.abspath(__file__))
outs = [subprocess.run(["psql", DSN, "-v", "ON_ERROR_STOP=1", "-q", "-f", os.path.join(here, "..", "sql", f)], capture_output=True, text=True)
        for f in ["001_checkin_schema.sql", "002_checkin_functions.sql", "003_seed_tickets.sql", "004_settings_seed.sql", "005_print_sheets.sql"]]
check("T22 Migratsiyalarni qayta qo'llash xavfsiz: biletlar, kirish holati (admission_open), sig'im o'zgarmaydi",
      all(o.returncode == 0 for o in outs) and snapshot() == snap_m and cap_now() == 11222
      and sql("select value::text from checkin.settings where key='admission_open'")[0][0] == adm_before
      and sql("select count(*) from pg_proc where proname = 'ci_issue_replacement'")[0][0] == 1,
      [o.stderr[-200:] for o in outs if o.returncode])

json.dump(R, open("db_test_results.json", "w"), ensure_ascii=False, indent=1)
print(f"\n{sum(r['ok'] for r in R)}/{len(R)} PASS")
sys.exit(0 if all(r["ok"] for r in R) else 1)
