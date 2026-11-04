#!/usr/bin/env python3
"""DUSEL GAL — to'liq 8-up bosma (320 × 450 mm, 1000 ta, 0001–1000) va 4 xonali master/QR QA."""
import csv, io, json, os, re, subprocess, sys, zipfile
import numpy as np
import pymupdf as fitz
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol

MM = 72 / 25.4
OUT, CFGP = sys.argv[1], sys.argv[2]
CFG = json.load(open(CFGP)); ROOT = os.path.dirname(os.path.abspath(CFGP))
PDF = os.path.join(OUT, "DUSEL_GAL_1000_8UP_320x450_FINAL.pdf")
TEST = os.path.join(ROOT, "out_test8", "DUSEL_GAL_TEST_8UP_320x450.pdf")
URL = "https://dusel.pages.dev/gal?code="
EXP = [f"{i:04d}" for i in range(1, 1001)]
R = []
def check(n, ok, d=""):
    R.append(dict(name=n, ok=bool(ok), detail=str(d)[:300])); print(("PASS " if ok else "FAIL ") + n + (f" — {d}" if d != "" else ""), flush=True)
def zd(im): return [z.data.decode() for z in decode(im, symbols=[ZBarSymbol.QRCODE])]

# ---- master
rows = list(csv.DictReader(open(os.path.join(OUT, "DUSEL_GAL_MASTER.csv"), encoding="utf-8-sig")))
check("Master: 1000 ta, 0001–1000, 4 xonali, takrorsiz, tushib qolgan yo'q", [r["VOUCHER_NUMBER"] for r in rows] == EXP)
check("Master: QR_URL = https://dusel.pages.dev/gal?code=<4 xonali>; STATUS=NOT_ISSUED; ISM/SANA bo'sh",
      all(r["QR_URL"] == URL + r["VOUCHER_NUMBER"] and r["STATUS"] == "NOT_ISSUED" and r["ISSUE_DATE"] == r["RECIPIENT_NAME"] == "" and r["VOUCHER_TYPE"] == "GAL" for r in rows))
check("Master: 6 xonali raqam (000001…) yo'q", not any(re.search(r"code=\d{6}|^\d{6}$", r["QR_URL"] + "|" + r["VOUCHER_NUMBER"]) for r in rows))
import openpyxl
ws = openpyxl.load_workbook(os.path.join(OUT, "DUSEL_GAL_MASTER.xlsx")).active
xr = list(ws.iter_rows(values_only=True))[1:]
check("Master XLSX = CSV, raqam matn formatida (0001)", [(r[1], r[2]) for r in xr] == [(r["VOUCHER_NUMBER"], r["QR_URL"]) for r in rows] and all(isinstance(r[1], str) for r in xr))
# ---- QR arxivi
qd = os.path.join(OUT, "qr_gal")
bad = [c for c in EXP if zd(Image.open(os.path.join(qd, "PNG", f"GAL_{c}.png")).convert("L")) != [URL + c]]
check("QR PNG: 1000/1000 dekod, payload aynan /gal?code=<raqam>", not bad, bad[:5] or "1000/1000")
import cairosvg
bad = [c for c in EXP[::25] + [EXP[-1]] if zd(Image.open(io.BytesIO(cairosvg.svg2png(url=os.path.join(qd, "SVG", f"GAL_{c}.svg"), output_width=500, background_color="white"))).convert("L")) != [URL + c]]
check("QR SVG: namuna (41 ta) dekod to'g'ri", not bad, bad)
z = zipfile.ZipFile(os.path.join(OUT, "DUSEL_GAL_QR_1000.zip")); nm = z.namelist()
check("DUSEL_GAL_QR_1000.zip: GAL_0001…GAL_1000 (1000 SVG + 1000 PNG) + master CSV, butun",
      sorted(x for x in nm if x.startswith("PNG/")) == [f"PNG/GAL_{c}.png" for c in EXP] and sum(x.endswith(".svg") for x in nm) == 1000 and z.testzip() is None)
# ---- bosma PDF
doc = fitz.open(PDF); lay = json.load(open(PDF.replace(".pdf", "_layout.json")))
check("Bosma: 125 varaq, har biri aynan 320 × 450 mm", len(doc) == 125 and all(abs(p.rect.width / MM - 320) < .01 and abs(p.rect.height / MM - 450) < .01 for p in doc))
check("Bosma: jami 1000 vaucher, har varaqda 8 ta", len(lay) == 1000 and all(sum(1 for x in lay if x["sheet"] == s) == 8 for s in range(1, 126)))
check("Bosma: har vaucher aynan 156.04 × 66.29 mm", all(abs((x["trim"][3] - x["trim"][1]) / MM - 156.04) < .01 and abs((x["trim"][2] - x["trim"][0]) / MM - 66.29) < .01 for x in lay))
bad = []
for s in range(1, 126):
    L = sorted([x for x in lay if x["sheet"] == s], key=lambda x: (round(x["trim"][1]), x["trim"][0]))
    if [x["number"] for x in L] != EXP[(s - 1) * 8:s * 8]: bad.append(s)
check("Bosma: tartib — har varaqda 1-qator n+1…n+4, 2-qator n+5…n+8; 0001–1000 ketma-ket, takrorsiz", not bad and sorted(x["number"] for x in lay) == EXP, bad[:5])
ref = [x["trim"] for x in lay if x["sheet"] == 1]
check("Bosma: barcha varaqlarda joylashuv bir xil (tasdiqlangan test varag'idagidek)", all(sorted(x["trim"] for x in lay if x["sheet"] == s) == sorted(ref) for s in range(1, 126)))
badn, badq = [], []
for p in range(125):
    pg = doc[p]; words = pg.get_text("words")
    for x in [x for x in lay if x["sheet"] == p + 1]:
        t = fitz.Rect(x["trim"])
        w = [w[4] for w in words if t.contains(fitz.Rect(w[:4])) and re.fullmatch(r"\d{4,6}", w[4])]
        if w != [x["number"]]: badn.append((x["number"], w))
        pix = pg.get_pixmap(clip=fitz.Rect(x["qr"]) + (-3, -3, 3, 3), dpi=300, colorspace=fitz.csGRAY)
        if zd(Image.frombytes("L", (pix.width, pix.height), pix.samples)) != [URL + x["number"]]: badq.append(x["number"])
check("Bosma: har vaucherda bitta bosilgan raqam \"Nº 0001\"…\"Nº 1000\", o'z joyida", not badn, badn[:3])
check("Bosma: 1000/1000 QR PDF'dan 300 dpi'da dekod qilindi — har biri o'z vaucher raqamiga mos", not badq, badq[:5] or "1000/1000")
P = fitz.Rect(0, 0, 320 * MM, 450 * MM)
ov = []
for s in range(1, 126):
    L = [x for x in lay if x["sheet"] == s]
    for i in range(8):
        for j in range(i + 1, 8):
            J = fitz.Rect(L[i]["bleed"]) & fitz.Rect(L[j]["bleed"])
            if not J.is_empty and J.width > .01 and J.height > .01: ov.append((L[i]["number"], L[j]["number"]))
check("Bosma: hech biri kesilmaydi/ustma-ust tushmaydi, hammasi varaq ichida; QR va raqam trimdan ≥3 mm ichkarida",
      not ov and all(P.contains(fitz.Rect(x["bleed"])) for x in lay)
      and all((fitz.Rect(x["trim"]) + (3 * MM, 3 * MM, -3 * MM, -3 * MM)).contains(fitz.Rect(x[k])) for x in lay for k in ("qr", "num")), ov[:3])
badm = []
for p in range(125):
    pg = doc[p]
    n = sum(1 for d in pg.get_drawings() if d["type"] == "s" and abs((d.get("width") or 0) - .25) < 1e-3 for it in d["items"] if it[0] == "l")
    if n != 24: badm.append((p + 1, n))
check("Bosma: har varaqda 24 ta kesish belgisi (8 vertikal + 4 gorizontal kesish × 2), 0.25 pt Registration", not badm, badm[:3])
# tasdiqlangan test varag'i bilan solishtirish (1-varaq, texnik qatordan tashqari)
a = fitz.open(TEST)[0]; b = doc[0]
pa, pb = a.get_pixmap(dpi=100), b.get_pixmap(dpi=100)
D = np.abs(np.frombuffer(pa.samples, np.uint8).astype(int) - np.frombuffer(pb.samples, np.uint8).astype(int)).reshape(pa.h, pa.w, -1).max(axis=2)
D[:, :int(15 * 100 / 25.4)] = 0       # chap hoshiyadagi texnik qator ("TEST"/"PRINT", varaq raqami)
check("1-varaq tasdiqlangan test varag'i bilan piksel bo'yicha bir xil (texnik qatordan tashqari)", (D > 40).sum() == 0, f"farqli piksellar {(D > 40).sum()}")
fonts = {f[3] for p in doc for f in p.get_fonts(full=True)}
check("Shrift embed (subset), OutputIntent ISO Coated v2, dizayn rasmi bitta obyekt (CMYK)",
      all("+" in f for f in fonts) and doc.xref_get_key(doc.pdf_catalog(), "OutputIntents")[0] == "array"
      and len({i[0] for p in doc for i in p.get_images(full=True)}) == 1, fonts)
json.dump(R, open(os.path.join(OUT, "gal_8up_qa.json"), "w"), ensure_ascii=False, indent=1)
print(f"\n{sum(r['ok'] for r in R)}/{len(R)} PASS")
