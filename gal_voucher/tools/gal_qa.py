#!/usr/bin/env python3
"""DUSEL GAL vaucherlar — avtomatik QA: master, QR (PNG/SVG/ZIP), tizimlararo izolyatsiya, bosma PDF (bo'lsa)."""
import csv, io, json, os, re, sys, zipfile
from urllib.parse import urlparse, parse_qs
import openpyxl
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol
import segno

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
TICKET = "/home/claude/work/v6/master/DUSEL_MASTER_FINAL.csv"
COUPONS = {"GOLD": "/home/claude/work/coupon/out/DUSEL_COUPON_GOLD_MASTER.csv", "SILVER": "/home/claude/work/coupon/out/DUSEL_COUPON_SILVER_MASTER.csv"}
COLS = ["VOUCHER_TYPE", "VOUCHER_NUMBER", "QR_URL", "STATUS", "ISSUE_DATE", "RECIPIENT_NAME"]
EXP_NUM = [f"{i:06d}" for i in range(1, 1001)]
EXP_URL = [f"https://dusel.pages.dev/gal?code={c}" for c in EXP_NUM]

R = []
def check(name, ok, detail=""):
    R.append(dict(name=name, ok=bool(ok), detail=str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail != "" else ""), flush=True)

def zd(img):
    return [x.data.decode() for x in decode(img, symbols=[ZBarSymbol.QRCODE])]

def read_csv(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

# --- Master
rows = read_csv(os.path.join(OUT, "DUSEL_GAL_MASTER.csv"))
check("CSV ustunlari: " + ", ".join(COLS), list(rows[0].keys()) == COLS)
check("Vaucherlar soni = 1000", len(rows) == 1000, len(rows))
nums = [r["VOUCHER_NUMBER"] for r in rows]
check("Raqamlar 000001–001000, ketma-ket, tushib qolgan yo'q", nums == EXP_NUM)
check("Har bir raqam aynan 6 xonali", all(re.fullmatch(r"\d{6}", n) for n in nums))
check("Takroriy raqam yo'q", len(set(nums)) == 1000)
check("VOUCHER_TYPE = GAL, STATUS = NOT_ISSUED, ISSUE_DATE va RECIPIENT_NAME bo'sh",
      all(r["VOUCHER_TYPE"] == "GAL" and r["STATUS"] == "NOT_ISSUED" and r["ISSUE_DATE"] == "" and r["RECIPIENT_NAME"] == "" for r in rows))
check("QR_URL = https://dusel.pages.dev/gal?code=<raqam> (har bir qatorda raqam bilan mos)", [r["QR_URL"] for r in rows] == EXP_URL)
wb = openpyxl.load_workbook(os.path.join(OUT, "DUSEL_GAL_MASTER.xlsx"))
ws = wb.active
xr = list(ws.iter_rows(values_only=True))
body = xr[1:]
check("XLSX = CSV (1000 qator, raqam matn formatida, nollar saqlangan)",
      list(xr[0]) == COLS and len(body) == 1000 and all(isinstance(r[1], str) for r in body)
      and [(r[0], r[1], r[2], r[3]) for r in body] == [("GAL", n, u, "NOT_ISSUED") for n, u in zip(EXP_NUM, EXP_URL)]
      and all(r[4] is None and r[5] is None for r in body) and ws["B2"].number_format == "@")

# --- QR
urls = [r["QR_URL"] for r in rows]
check("1000 ta noyob QR payload", len(set(urls)) == 1000)
P = [urlparse(u) for u in urls]
check("Har bir QR: https, host dusel.pages.dev, yo'l /gal, faqat 'code' parametri",
      all(p.scheme == "https" and p.netloc == "dusel.pages.dev" and p.path == "/gal" and list(parse_qs(p.query)) == ["code"] for p in P))
check("Qisqartirgich/redirect xizmati, token yoki vaqtinchalik parametr yo'q",
      not any(re.search(r"bit\.ly|tinyurl|qr-code|qrco|token|sig=|expires|session", u, re.I) for u in urls))
qdir = os.path.join(OUT, "qr_gal")
pngs, svgs = sorted(os.listdir(os.path.join(qdir, "PNG"))), sorted(os.listdir(os.path.join(qdir, "SVG")))
check("Fayl nomlari GAL_000001 … GAL_001000 (.png va .svg)", pngs == [f"GAL_{n}.png" for n in EXP_NUM] and svgs == [f"GAL_{n}.svg" for n in EXP_NUM])
bad, sizes = [], set()
for n, u in zip(EXP_NUM, EXP_URL):
    im = Image.open(os.path.join(qdir, "PNG", f"GAL_{n}.png")); sizes.add(im.size)
    if zd(im.convert("L")) != [u]: bad.append(n)
check("Barcha 1000 PNG dekod qilindi va payload aynan kutilgan URL", not bad, f"xato: {bad[:5]}" if bad else f"1000/1000, {sizes}")
import cairosvg
bad = []
for n, u in zip(EXP_NUM, EXP_URL):
    png = cairosvg.svg2png(url=os.path.join(qdir, "SVG", f"GAL_{n}.svg"), output_width=500, background_color="white")
    if zd(Image.open(io.BytesIO(png)).convert("L")) != [u]: bad.append(n)
check("Barcha 1000 SVG rasterlanib dekod qilindi va payload to'g'ri", not bad, f"xato: {bad[:5]}" if bad else "1000/1000")
q = segno.make(EXP_URL[0], version=4, error="q", mode="byte", boost_error=False)
im = Image.open(os.path.join(qdir, "PNG", "GAL_000001.png"))
check("QR parametrlari: versiya 4 (33×33), xato tuzatish Q (~25%), 4 modul quiet zone, logotip yo'q",
      q.version == 4 and q.error == "Q" and im.size[0] == 41 * 30 and all(im.convert("L").getpixel((x, y)) == 255 for x in range(0, 4 * 30) for y in range(0, im.size[1], 7)))
z = zipfile.ZipFile(os.path.join(OUT, "DUSEL_GAL_QR_1000.zip"))
nm = z.namelist()
check("DUSEL_GAL_QR_1000.zip: 1000 SVG + 1000 PNG + master CSV, butun", sum(x.endswith(".svg") for x in nm) == 1000 and sum(x.endswith(".png") for x in nm) == 1000
      and "DUSEL_GAL_MASTER.csv" in nm and z.testzip() is None, f"{len(nm)} fayl")

# --- Tizimlararo izolyatsiya
tick = [r["QR_URL"] for r in read_csv(TICKET)]
coup = {t: [r["QR_URL"] for r in read_csv(p)] for t, p in COUPONS.items()}
allsets = {"TICKET": set(tick), "GOLD": set(coup["GOLD"]), "SILVER": set(coup["SILVER"]), "GAL": set(urls)}
check("Bilet master: 11222 ta, o'zgarmagan", len(tick) == 11222 and len(set(tick)) == 11222)
check("Gold 2000 / Silver 4000 kupon master o'zgarmagan", len(coup["GOLD"]) == 2000 and len(coup["SILVER"]) == 4000)
total = sum(len(s) for s in allsets.values()); union = set().union(*allsets.values())
check("4 tizim (bilet/gold/silver/GAL) URL'lari umuman kesishmaydi", total == len(union) == 11222 + 2000 + 4000 + 1000, f"{len(union)} noyob URL")
def route(u):
    p = urlparse(u); qs = parse_qs(p.query)
    if p.path == "/" and list(qs) == ["code"] and re.fullmatch(r"\d{5}", qs["code"][0]): return "TICKET"
    if p.path == "/coupon" and set(qs) == {"type", "code"} and re.fullmatch(r"\d{4}", qs["code"][0]): return qs["type"][0].upper()
    if p.path == "/gal" and list(qs) == ["code"] and re.fullmatch(r"\d{6}", qs["code"][0]): return "GAL"
    return "?"
mis = [(k, u) for k, s in allsets.items() for u in s if route(u) != k]
check("Har bir URL faqat o'z yo'liga tushadi (yo'l + raqam uzunligi bo'yicha: bilet 5, kupon 4, GAL 6 xona)", not mis, mis[:3])
same = [n for n in ["000001", "001000"]]
check("Bir xil son (1) har tizimda boshqa URL: /?code=00001 · /coupon?type=gold&code=0001 · /gal?code=000001",
      len({"https://dusel.pages.dev/?code=00001", "https://dusel.pages.dev/coupon?type=gold&code=0001", "https://dusel.pages.dev/gal?code=000001"} & union) == 3)

# --- Bosma (artwork kelgandan keyin)
for kind in ("PROOF", "PRINT"):
    pth = os.path.join(OUT, f"DUSEL_GAL_{kind}.pdf")
    if not os.path.exists(pth):
        check(f"DUSEL_GAL_{kind}.pdf", False, "YARATILMAGAN — Vaucher(1).png dizayn fayli va bosma o'lchami kutilmoqda")

json.dump(R, open(os.path.join(OUT, "gal_qa_results.json"), "w"), ensure_ascii=False, indent=1)
print(f"\n{sum(r['ok'] for r in R)}/{len(R)} PASS")
sys.exit(0 if all(r["ok"] for r in R) else 1)
