#!/usr/bin/env python3
"""
DUSEL_MASTER_11222.csv -> sayt ma'lumoti (data/seats/s0..s11.json + manifest.json).
Sayt joyni hisoblamaydi: faqat shu fayllarni o'qiydi. Bosma ham aynan shu CSV dan (impose_prod.py).

holat: "ok" = ASSIGNED, "review" = REVIEW_REQUIRED (qiymat ko'rsatiladi + neytral izoh).
Ishlatish: python sync_site.py master/DUSEL_MASTER_11222.csv /path/to/dusel
"""
import csv, hashlib, json, os, re, sys
from datetime import datetime, timezone

master, site = sys.argv[1], sys.argv[2]
sha = hashlib.sha256(open(master, "rb").read()).hexdigest()
rows = list(csv.DictReader(open(master, encoding="utf-8-sig")))
N = len(rows)
assert [r["TICKET_NUMBER"] for r in rows] == [str(i).zfill(5) for i in range(1, N + 1)]
H = {"ASSIGNED": "ok", "REVIEW_REQUIRED": "review"}
for r in rows:
    assert re.fullmatch(r"[A-D]\d{3}", r["SECTOR"]) and r["ROW"].isdigit() and r["SEAT"].isdigit() and r["STATUS"] in H, r
d = os.path.join(site, "data", "seats")
os.makedirs(d, exist_ok=True)
gen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
shards = (N + 999) // 1000
for k in range(shards):
    part = {r["TICKET_NUMBER"]: [r["SECTOR"], r["ROW"], r["SEAT"], H[r["STATUS"]]] for r in rows[k * 1000:(k + 1) * 1000]}
    with open(os.path.join(d, f"s{k}.json"), "w", encoding="utf-8") as f:
        json.dump({"v": 2, "source": os.path.basename(master), "source_sha256": sha, "generated": gen,
                   "fields": ["sektor", "qator", "joy", "holat"], "tickets": part}, f, ensure_ascii=False, separators=(",", ":"))
# eski ortiqcha bo'laklarni olib tashlash
for fn in os.listdir(d):
    m = re.fullmatch(r"s(\d+)\.json", fn)
    if m and int(m.group(1)) >= shards:
        os.remove(os.path.join(d, fn))
with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump({"v": 2, "source": os.path.basename(master), "source_sha256": sha, "generated": gen, "tickets": N,
               "shards": shards, "status_counts": {k: sum(r["STATUS"] == k for r in rows) for k in H}}, f, ensure_ascii=False, indent=1)
print(f"OK {N} bilet, {shards} bo'lak, master sha256 {sha[:12]}…")
