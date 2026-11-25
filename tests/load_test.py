#!/usr/bin/env python3
"""
Yuklama testi (lokal Postgres 16): konsert oqimini taqlid qiladi.
- 16 darvoza qurilmasi parallel; har biri: ko'rish (lookup) + kiritish (admit), barcha 11 222 bilet
- 10% takroriy skan, 2% kupon/yaroqsiz QR, 1% tarmoq qayta yuborishi (bir xil request_id)
Natija: o'tkazuvchanlik, kechikish (p50/p95/p99), yaxlitlik (har bilet aynan 1 marta).
"""
import json, random, statistics, sys, time, uuid, threading
from concurrent.futures import ThreadPoolExecutor
import psycopg

DSN = sys.argv[1] if len(sys.argv) > 1 else "host=/tmp port=5433 dbname=ci_load user=postgres"
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 16
admin = psycopg.connect(DSN, autocommit=True)
uids = []
for i in range(WORKERS):
    uid = admin.execute("insert into auth.users (email) values (%s) on conflict (email) do update set email=excluded.email returning id", (f"load{i}@t",)).fetchone()[0]
    admin.execute("insert into checkin.staff (user_id, username, display_name, role) values (%s,%s,%s,'GATE') on conflict do nothing", (uid, f"load{i}@t", f"L{i}"))
    uids.append(str(uid))
for gi in range(1, 17):
    admin.execute("insert into checkin.gates values (%s, %s, true) on conflict do nothing", (f"L{gi}", f"Load {gi}"))
admin.execute("update checkin.settings set value='true' where key='admission_open'")
admin.execute("update checkin.settings set value='100000' where key='rate_limit_per_10s'")

tickets = [f"{i:05d}" for i in range(1, 11223)]
random.seed(42); random.shuffle(tickets)
plan = []
for t in tickets:
    plan.append(("admit", f"https://dusel.pages.dev/?code={t}", None))
    r = random.random()
    if r < 0.10: plan.append(("dup", f"https://dusel.pages.dev/ticket?code={t}", None))
    elif r < 0.12: plan.append(("foreign", "https://dusel.pages.dev/gold?code=0001", None))
    elif r < 0.13: plan.append(("retry", f"https://dusel.pages.dev/?code={t}", "same"))
chunks = [plan[i::WORKERS] for i in range(WORKERS)]
lat = {"lookup": [], "admit": []}; lock = threading.Lock(); errors = []

def worker(i):
    c = psycopg.connect(DSN, autocommit=True)
    c.execute("set role authenticated")
    c.execute("select set_config('request.jwt.claims', %s, false)", (json.dumps({"sub": uids[i], "iat": int(time.time())}),))
    gate = f"L{1 + i % 16}"; last_rid = None; L = {"lookup": [], "admit": []}
    for kind, payload, extra in chunks[i]:
        try:
            t0 = time.perf_counter(); c.execute("select public.ci_lookup(%s,%s,%s)", (payload, gate, f"d{i}")).fetchone(); L["lookup"].append(time.perf_counter() - t0)
            rid = last_rid if extra == "same" and last_rid else str(uuid.uuid4())
            t0 = time.perf_counter(); c.execute("select public.ci_admit(%s,%s,%s,%s)", (rid, payload, gate, f"d{i}")).fetchone(); L["admit"].append(time.perf_counter() - t0)
            last_rid = rid
        except Exception as e:
            errors.append(str(e)[:100])
    with lock:
        lat["lookup"] += L["lookup"]; lat["admit"] += L["admit"]
    c.close()

t0 = time.time()
with ThreadPoolExecutor(WORKERS) as ex: list(ex.map(worker, range(WORKERS)))
dur = time.time() - t0
q = lambda a, p: sorted(a)[int(len(a) * p) - 1] * 1000
adm = admin.execute("select count(*) from checkin.tickets where status='ADMITTED'").fetchone()[0]
ev = dict(admin.execute("select decision, count(*) from checkin.admission_events group by 1").fetchall())
per_ticket = admin.execute("select max(n) from (select ticket_no, count(*) n from checkin.admission_events where decision='ADMITTED' and credential_type='TICKET' group by 1) x").fetchone()[0]
audit = admin.execute("select public.ci_audit_verify()") if False else None
res = dict(workers=WORKERS, operations=len(lat["lookup"]) + len(lat["admit"]), seconds=round(dur, 1),
           ops_per_sec=round((len(lat["lookup"]) + len(lat["admit"])) / dur, 1), admits_per_sec=round(adm / dur, 1),
           lookup_ms=dict(p50=round(q(lat["lookup"], .5), 1), p95=round(q(lat["lookup"], .95), 1), p99=round(q(lat["lookup"], .99), 1)),
           admit_ms=dict(p50=round(q(lat["admit"], .5), 1), p95=round(q(lat["admit"], .95), 1), p99=round(q(lat["admit"], .99), 1)),
           admitted_tickets=adm, events=ev, max_admitted_events_per_ticket=per_ticket, errors=len(errors), error_samples=errors[:3])
print(json.dumps(res, ensure_ascii=False, indent=1))
json.dump(res, open("load_results.json", "w"), ensure_ascii=False, indent=1)
ok = adm == 11222 and per_ticket == 1 and not errors
print("LOAD", "PASS" if ok else "FAIL")
