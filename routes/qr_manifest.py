#!/usr/bin/env python3
"""Har tizim arxividan tasodifiy QR'larni dekod qilib manifest yaratadi va barcha yakuniy URL'larning kesishmasligini tekshiradi."""
import csv, json, random, re, sys
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol
from urllib.parse import urlparse, parse_qs
SYS = {
 "ticket": dict(master="/home/claude/work/v7/master/DUSEL_MASTER_FINAL.csv", col="TICKET_NUMBER", png="/home/claude/work/v7/qr/QR_PNG/{c}.png", path="/ticket", w=5, n=11222),
 "gal":    dict(master="/home/claude/work/gal/out/DUSEL_GAL_MASTER.csv", col="VOUCHER_NUMBER", png="/home/claude/work/gal/out/qr_gal/PNG/GAL_{c}.png", path="/gal", w=6, n=1000),
 "gold":   dict(master="/home/claude/work/coupon2/out/DUSEL_COUPON_GOLD_MASTER.csv", col="COUPON_NUMBER", png="/home/claude/work/coupon2/out/qr_gold/PNG/GOLD_{c}.png", path="/gold", w=4, n=2000),
 "silver": dict(master="/home/claude/work/coupon2/out/DUSEL_COUPON_SILVER_MASTER.csv", col="COUPON_NUMBER", png="/home/claude/work/coupon2/out/qr_silver/PNG/SILVER_{c}.png", path="/silver", w=4, n=4000),
}
R, man, allurls = [], {}, {}
def check(n, ok, d=""):
    R.append(dict(name=n, ok=bool(ok), detail=str(d))); print(("PASS " if ok else "FAIL ") + n + (f" — {d}" if d != "" else ""))
for k, s in SYS.items():
    rows = list(csv.DictReader(open(s["master"], encoding="utf-8-sig")))
    codes = [r[s["col"]] for r in rows]; urls = [r["QR_URL"] for r in rows]
    exp = [str(i).zfill(s["w"]) for i in range(1, s["n"] + 1)]
    check(f"{k.upper()}: {s['n']} ta, {exp[0]}–{exp[-1]}, takrorsiz, {s['w']} xonali", codes == exp and len(set(urls)) == s["n"])
    ok = all(urlparse(u).scheme == "https" and urlparse(u).netloc == "dusel.pages.dev" and urlparse(u).path == s["path"]
             and list(parse_qs(urlparse(u).query)) == ["code"] and parse_qs(urlparse(u).query)["code"][0] == c for u, c in zip(urls, codes))
    check(f"{k.upper()}: har URL = https://dusel.pages.dev{s['path']}?code=<raqam>", ok)
    allurls[k] = set(urls)
    pick = sorted(set([exp[0], exp[-1]] + random.Random(7).sample(exp, 40)))
    dec = []
    for c in pick:
        z = decode(Image.open(s["png"].format(c=c)).convert("L"), symbols=[ZBarSymbol.QRCODE])
        dec.append(z[0].data.decode() if len(z) == 1 else "")
    bad = [c for c, u in zip(pick, dec) if u != f"https://dusel.pages.dev{s['path']}?code={c}"]
    check(f"{k.upper()}: {len(pick)} ta tasodifiy QR rasm dekod qilindi — payload aynan yakuniy URL", not bad, bad[:3])
    man[k] = dec
tot = sum(len(v) for v in allurls.values()); uni = set().union(*allurls.values())
check("4 tizim yakuniy URL'lari kesishmaydi (bilet 11222 + GAL 1000 + GOLD 2000 + SILVER 4000)", tot == len(uni) == 18222, f"{len(uni)} noyob")
paths = {k: {urlparse(u).path for u in v} for k, v in allurls.items()}
check("Har tizim faqat bitta, boshqalardan farqli yo'lda: " + ", ".join(f"{k}={sorted(p)[0]}" for k, p in paths.items()),
      all(len(p) == 1 for p in paths.values()) and len({next(iter(p)) for p in paths.values()}) == 4)
json.dump(man, open("qr_manifest.json", "w"), indent=0)
json.dump(R, open("qr_manifest_results.json", "w"), ensure_ascii=False, indent=1)
print(f"{sum(r['ok'] for r in R)}/{len(R)} PASS")
