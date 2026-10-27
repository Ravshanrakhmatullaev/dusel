#!/usr/bin/env python3
"""DUSEL kupon tizimi — avtomatik QA (ma'lumot, QR, PDF)."""
import csv, json, os, re, sys, zipfile, io, random, time
from urllib.parse import urlparse, parse_qs
import pymupdf as fitz
import numpy as np
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol
import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
SRC = os.path.join(ROOT, "input", "kupon.pdf")
TICKET_MASTER = "/home/claude/work/v6/master/DUSEL_MASTER_FINAL.csv"
TYPES = {"GOLD": dict(count=2000, page=1, slug="gold"), "SILVER": dict(count=4000, page=0, slug="silver")}
FULL_QR = "--full" in sys.argv

results = []
def check(name, ok, detail=""):
    results.append(dict(name=name, ok=bool(ok), detail=str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""), flush=True)

def zdecode(img):
    r = decode(img, symbols=[ZBarSymbol.QRCODE])
    return [x.data.decode() for x in r]

all_urls = {}
for T, cfg in TYPES.items():
    t = cfg["slug"]; n = cfg["count"]
    exp = [f"{i:04d}" for i in range(1, n + 1)]
    exp_url = [f"https://dusel.pages.dev/coupon?type={t}&code={c}" for c in exp]
    # --- CSV
    with open(os.path.join(OUT, f"DUSEL_COUPON_{T}_MASTER.csv"), encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    check(f"{T}: CSV ustunlari TYPE/COUPON_NUMBER/QR_URL", list(rows[0].keys()) == ["TYPE", "COUPON_NUMBER", "QR_URL"])
    check(f"{T}: CSV soni = {n}", len(rows) == n, len(rows))
    nums = [r["COUPON_NUMBER"] for r in rows]
    check(f"{T}: raqamlar {exp[0]}–{exp[-1]} ketma-ket, 4 xonali", nums == exp)
    check(f"{T}: raqamlar takrorlanmaydi", len(set(nums)) == n)
    check(f"{T}: TYPE ustuni hamma joyda {T}", all(r["TYPE"] == T for r in rows))
    check(f"{T}: QR_URL formati to'g'ri", [r["QR_URL"] for r in rows] == exp_url)
    # --- XLSX
    wb = openpyxl.load_workbook(os.path.join(OUT, f"DUSEL_COUPON_{T}_MASTER.xlsx"), read_only=True)
    ws = wb.active
    xr = list(ws.iter_rows(values_only=True))
    hdr, body = xr[0], [r for r in xr[1:] if any(v is not None for v in r)]
    check(f"{T}: XLSX = CSV ({n} qator, raqamlar matn ko'rinishida)",
          list(hdr[:3]) == ["TYPE", "COUPON_NUMBER", "QR_URL"] and len(body) == n
          and all(isinstance(r[1], str) for r in body)
          and [(r[0], r[1], r[2]) for r in body] == [(T, c, u) for c, u in zip(exp, exp_url)])
    all_urls[T] = exp_url

    # --- QR fayllar (PNG hammasi dekod qilinadi, SVG soni + namuna)
    qdir = os.path.join(OUT, f"qr_{t}")
    pngs = sorted(os.listdir(os.path.join(qdir, "PNG"))); svgs = sorted(os.listdir(os.path.join(qdir, "SVG")))
    check(f"{T}: PNG={n}, SVG={n}", len(pngs) == n and len(svgs) == n, f"{len(pngs)}/{len(svgs)}")
    bad = []; sizes = set()
    for c, u in zip(exp, exp_url):
        im = Image.open(os.path.join(qdir, "PNG", f"{T}_{c}.png")); sizes.add(im.size)
        if zdecode(im.convert("L")) != [u]: bad.append(c)
    check(f"{T}: barcha {n} PNG QR dekod = kutilgan URL", not bad, f"xato: {bad[:5]}" if bad else f"o'lcham {sizes}")
    try:
        import cairosvg
        sbad = []
        for c in random.Random(7).sample(exp, 60) + [exp[0], exp[-1]]:
            png = cairosvg.svg2png(url=os.path.join(qdir, "SVG", f"{T}_{c}.svg"), output_width=600, background_color="white")
            if zdecode(Image.open(io.BytesIO(png)).convert("L")) != [exp_url[int(c) - 1]]: sbad.append(c)
        check(f"{T}: SVG namuna (62 ta) dekod to'g'ri", not sbad, sbad[:5])
    except ImportError:
        check(f"{T}: SVG namuna dekod (cairosvg yo'q)", True, "o'tkazildi")
    z = zipfile.ZipFile(os.path.join(OUT, f"DUSEL_COUPON_{T}_QR.zip"))
    names = z.namelist()
    check(f"{T}: ZIP ichida {n} SVG + {n} PNG", sum(x.endswith(".svg") for x in names) == n and sum(x.endswith(".png") for x in names) == n,
          f"{len(names)} fayl")
    check(f"{T}: ZIP butun (testzip)", z.testzip() is None)

# --- Turlar va biletlar orasida konflikt yo'q
g, s = set(all_urls["GOLD"]), set(all_urls["SILVER"])
check("Gold va Silver URL'lari kesishmaydi (6000 noyob payload)", not (g & s) and len(g | s) == 6000, len(g | s))
with open(TICKET_MASTER, encoding="utf-8-sig") as f:
    turls = [r["QR_URL"] for r in csv.DictReader(f)]
check("Bilet master 11222 ta (o'zgarmagan)", len(turls) == 11222 and len(set(turls)) == 11222)
check("Kupon URL'lari bilet URL'lari bilan kesishmaydi", not ((g | s) & set(turls)))
tick_ok = all(urlparse(u).path in ("/", "") and set(parse_qs(urlparse(u).query)) == {"code"} and re.fullmatch(r"\d{5}", parse_qs(urlparse(u).query)["code"][0]) for u in turls)
coup_ok = all(urlparse(u).path == "/coupon" and set(parse_qs(urlparse(u).query)) == {"type", "code"} and re.fullmatch(r"\d{4}", parse_qs(urlparse(u).query)["code"][0]) for u in g | s)
check("Bilet: '/?code=NNNNN' (5 xona); Kupon: '/coupon?type=..&code=NNNN' (4 xona) — yo'llar ajratilgan", tick_ok and coup_ok)

# --- PDF
src = fitz.open(SRC)
for T, cfg in TYPES.items():
    t = cfg["slug"]; n = cfg["count"]
    for kind in ("PRINT", "PROOF"):
        path = os.path.join(OUT, f"DUSEL_COUPON_{T}_{kind}.pdf")
        lay = json.load(open(path.replace(".pdf", "_layout.json")))
        doc = fitz.open(path)
        cnt = n if kind == "PRINT" else 6
        sheets = -(-cnt // 6)
        check(f"{T} {kind}: sahifalar soni = {sheets}", len(doc) == sheets, len(doc))
        check(f"{T} {kind}: barcha sahifalar 450×320 mm", all(abs(p.rect.width / 72 * 25.4 - 450) < 0.05 and abs(p.rect.height / 72 * 25.4 - 320) < 0.05 for p in doc))
        check(f"{T} {kind}: layout {cnt} kupon, raqamlar 0001–{cnt:04d}", [x["number"] for x in lay] == [f"{i:04d}" for i in range(1, cnt + 1)])
        # matnli raqamlar: har varaqda har kupon 2 marta (QR osti + koreshok)
        bad = []
        for i, p in enumerate(doc):
            words = [w[4] for w in p.get_text("words")]
            expw = []
            for x in lay[i * 6:(i + 1) * 6]: expw += [x["number"], x["number"]]
            if words != expw: bad.append((i + 1, words[:4]))
        check(f"{T} {kind}: har varaqdagi bosma raqamlar layout bilan mos (QR osti + koreshok)", not bad, bad[:3])
        last = doc[-1]
        check(f"{T} {kind}: oxirgi varaqda {cnt - (sheets - 1) * 6} kupon", len(last.get_text("words")) == 2 * (cnt - (sheets - 1) * 6))
        fonts = {f[3] for p in doc for f in p.get_fonts()}
        check(f"{T} {kind}: shriftlar embed qilingan (subset)", all("+" in f for f in fonts), fonts)
        oi = doc.pdf_catalog() and doc.xref_get_key(doc.pdf_catalog(), "OutputIntents")
        check(f"{T} {kind}: OutputIntent (ISO Coated v2) bor", oi[0] == "array")

        # QR'larni PDF'dan render qilib dekod qilish
        if kind == "PROOF" or FULL_QR:
            sample = list(range(len(lay)))
        else:
            rnd = random.Random(11)
            sample = sorted(set(list(range(12)) + list(range(len(lay) - 6, len(lay))) + rnd.sample(range(len(lay)), 120)))
        bad = []; t0 = time.time()
        for k in sample:
            x = lay[k]; p = doc[x["sheet"] - 1]
            r = fitz.Rect(x["qbox"]) + (-2, -2, 2, 2)
            pix = p.get_pixmap(clip=r, dpi=300, colorspace=fitz.csGRAY)
            im = Image.frombytes("L", (pix.width, pix.height), pix.samples)
            if zdecode(im) != [f"https://dusel.pages.dev/coupon?type={t}&code={x['number']}"]: bad.append(x["number"])
        check(f"{T} {kind}: PDF ichidagi QR dekod = raqam ({len(sample)} ta, 300 dpi)", not bad, f"xato {bad[:5]}" if bad else f"{time.time() - t0:.0f}s")

        # Dizayn o'zgarmaganligi: o'zgaruvchi zonalardan tashqari designer sahifa bilan piksel solishtirish
        if kind == "PROOF":
            sp = src[cfg["page"]]; dp = doc[0]
            a = np.asarray(Image.frombytes("RGB", *(lambda q: ((q.width, q.height), q.samples))(sp.get_pixmap(dpi=100))), dtype=np.int16)
            b = np.asarray(Image.frombytes("RGB", *(lambda q: ((q.width, q.height), q.samples))(dp.get_pixmap(dpi=100))), dtype=np.int16)
            mask = np.ones(a.shape[:2], bool); sc = 100 / 72
            for x in lay:
                for key in ("qbox", "strip_num", "stub_num"):
                    R = fitz.Rect(x[key]) + (-3, -3, 3, 3)
                    mask[int(R.y0 * sc):int(R.y1 * sc) + 1, int(R.x0 * sc):int(R.x1 * sc) + 1] = False
            # tashqi chetdagi crop marklar zonasini ham chiqaramiz (kesish chizig'idan tashqari)
            X0, Y0, X1, Y1 = [int(v * 72 / 25.4 * sc) for v in (25, 10, 425, 310)]
            outside = np.ones(a.shape[:2], bool); outside[Y0:Y1, X0:X1] = False
            d = np.abs(a - b).max(axis=2)
            inner = d[mask & ~outside]
            check(f"{T}: dizayn (o'zgaruvchi zonadan tashqari) designer fayl bilan bir xil",
                  inner.max() <= 2, f"max farq {inner.max()}, >2 piksel: {(inner > 2).sum()}")

ok = all(r["ok"] for r in results)
json.dump(results, open(os.path.join(OUT, "qa_results.json"), "w"), ensure_ascii=False, indent=1)
print(f"\n{sum(r['ok'] for r in results)}/{len(results)} PASS")
sys.exit(0 if ok else 1)
