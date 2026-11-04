#!/usr/bin/env python3
"""DUSEL GAL — 8-up test varag'i (320 × 450 mm) QA."""
import json, os, re, sys
import numpy as np
import pymupdf as fitz
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol

MM = 72 / 25.4
OUT = sys.argv[1]
CFG = json.load(open(sys.argv[2]))
ROOT = os.path.dirname(os.path.abspath(sys.argv[2]))
PDF = os.path.join(OUT, "DUSEL_GAL_TEST_8UP_320x450.pdf")
R = []
def check(n, ok, d=""):
    R.append(dict(name=n, ok=bool(ok), detail=str(d))); print(("PASS " if ok else "FAIL ") + n + (f" — {d}" if d != "" else ""))

doc = fitz.open(PDF); pg = doc[0]
lay = json.load(open(PDF.replace(".pdf", "_layout.json")))
W, H = pg.rect.width / MM, pg.rect.height / MM
check("Varaq o'lchami aynan 320 × 450 mm (1 sahifa)", len(doc) == 1 and abs(W - 320) < 0.01 and abs(H - 450) < 0.01, f"{W:.3f} × {H:.3f} mm")
sizes = [((x["trim"][2] - x["trim"][0]) / MM, (x["trim"][3] - x["trim"][1]) / MM) for x in lay]
check("Har vaucher aynan 156.04 × 66.29 mm (varaqda 90° burilgan: 66.29 eni × 156.04 bo'yi)",
      all(abs(h - 156.04) < 0.01 and abs(w - 66.29) < 0.01 for w, h in sizes), sorted({(round(w, 3), round(h, 3)) for w, h in sizes}))
check("Varaqda aynan 8 ta vaucher", len(lay) == 8)
order = [x["number"] for x in sorted(lay, key=lambda x: (round(x["trim"][1]), x["trim"][0]))]
check("Raqamlar 0001–0008 (1-qator 0001–0004, 2-qator 0005–0008, chapdan o'ngga)", order == [f"{i:04d}" for i in range(1, 9)], order)
check("Har QR havolasi https://dusel.pages.dev/gal?code=<4 xonali raqam>", all(x["url"] == "https://dusel.pages.dev/gal?code=" + x["number"] for x in lay))
# bosilgan raqam
words = pg.get_text("words")
bad = []
for x in lay:
    t = fitz.Rect(x["trim"])
    w = [w[4] for w in words if t.contains(fitz.Rect(w[:4])) and re.fullmatch(r"\d{4,6}", w[4])]
    n = [w[4] for w in words if t.contains(fitz.Rect(w[:4])) and w[4] == "Nº"]
    if w != [x["number"]] or len(n) != 1: bad.append((x["number"], w))
check("Har vaucherda bitta bosilgan seriya raqami \"Nº 000N\", o'z joyida", not bad, bad)
# QR dekod
bad, qs = [], set()
for x in lay:
    q = fitz.Rect(x["qr"]); qs.add((round(q.width / MM, 2), round(q.height / MM, 2)))
    pix = pg.get_pixmap(clip=q + (-3, -3, 3, 3), dpi=300, colorspace=fitz.csGRAY)
    im = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    got = [z.data.decode() for z in decode(im, symbols=[ZBarSymbol.QRCODE])]
    if got != [x["url"]]: bad.append((x["number"], got))
check("Har QR (8/8) 300 dpi'da dekod qilindi va o'z vaucher raqamiga mos", not bad, bad if bad else f"QR {sorted(qs)} mm")
bad = []
for x in lay:
    pix = pg.get_pixmap(clip=fitz.Rect(x["qr"]) + (-3, -3, 3, 3), dpi=120, colorspace=fitz.csGRAY)
    im = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    if [z.data.decode() for z in decode(im, symbols=[ZBarSymbol.QRCODE])] != [x["url"]]: bad.append(x["number"])
check("Qo'shimcha: QR past ruxsatda ham (120 dpi) o'qiladi", not bad, bad)
# joylashuv
P = fitz.Rect(0, 0, 320 * MM, 450 * MM)
ins = all(P.contains(fitz.Rect(x["bleed"])) for x in lay)
mrg = min(min(x["bleed"][0], x["bleed"][1], P.x1 - x["bleed"][2], P.y1 - x["bleed"][3]) for x in lay) / MM
ov = []
for i in range(8):
    for j in range(i + 1, 8):
        a, b = fitz.Rect(lay[i]["trim"]), fitz.Rect(lay[j]["trim"])
        A, B = fitz.Rect(lay[i]["bleed"]), fitz.Rect(lay[j]["bleed"])
        I, J = a & b, A & B
        if (not I.is_empty and I.width > 0.01 and I.height > 0.01) or (not J.is_empty and J.width > 0.01 and J.height > 0.01): ov.append((lay[i]["number"], lay[j]["number"]))
gaps = sorted({round((b["trim"][0] - a["trim"][2]) / MM, 2) for a in lay for b in lay if abs(a["trim"][1] - b["trim"][1]) < 1 and b["trim"][0] > a["trim"][2]} )
check("Hammasi varaq ichida, ustma-ust tushmaydi; vaucherlar orasida 4 mm kesish oralig'i (2 + 2 mm bleed)", ins and not ov and mrg > 7 and 4.0 in gaps, f"eng kichik chet {mrg:.1f} mm, oraliqlar {gaps[:2]} mm, ustma-ust {ov}")
safe = all((fitz.Rect(x["trim"]) + (3 * MM, 3 * MM, -3 * MM, -3 * MM)).contains(fitz.Rect(x[k])) for x in lay for k in ("qr", "num"))
check("QR va raqam kesish chizig'idan ≥3 mm ichkarida (kesilmaydi)", safe)
# kesish belgilari
xs = sorted({round(v, 2) for x in lay for v in (x["trim"][0], x["trim"][2])})
ys = sorted({round(v, 2) for x in lay for v in (x["trim"][1], x["trim"][3])})
lines = [(it[1], it[2]) for d in pg.get_drawings() if d["type"] == "s" and abs((d.get("width") or 0) - 0.25) < 1e-3 for it in d["items"] if it[0] == "l"]
grid = fitz.Rect(min(x["bleed"][0] for x in lay), min(x["bleed"][1] for x in lay), max(x["bleed"][2] for x in lay), max(x["bleed"][3] for x in lay))
ok_marks, bad_m = 0, []
for a, b in lines:
    if abs(a.x - b.x) < 0.01:      # vertikal belgi -> vertikal kesish chizig'i x
        good = any(abs(a.x - x) < 0.05 for x in xs) and (max(a.y, b.y) <= grid.y0 + 0.01 or min(a.y, b.y) >= grid.y1 - 0.01)
    else:
        good = any(abs(a.y - y) < 0.05 for y in ys) and (max(a.x, b.x) <= grid.x0 + 0.01 or min(a.x, b.x) >= grid.x1 - 0.01)
    ok_marks += good
    if not good: bad_m.append((a, b))
lens = sorted({round(abs((b - a).x + (b - a).y) / MM, 2) for a, b in lines})
check("Kesish belgilari: har bir kesish chizig'iga 2 ta (tashqi hoshiyada), Registration, 0.25 pt, 5 mm; vaucher ustiga tushmaydi",
      len(lines) == 2 * (len(xs) + len(ys)) and ok_marks == len(lines) and any(b"1 1 1 1 K" in (doc.xref_stream(i) or b"") for i in range(1, doc.xref_length()) if doc.xref_is_stream(i)) and lens == [5.0],
      f"{len(lines)} belgi = 2 × ({len(xs)} vertikal + {len(ys)} gorizontal kesish), uzunlik {lens} mm")
# cho'zilmagan / dizayn
art = Image.open(os.path.join(ROOT, CFG["artwork"])).convert("RGB")
AW, AH = art.size
x = [x for x in lay if x["number"] == "0001"][0]
t = fitz.Rect(x["trim"])
pix = pg.get_pixmap(clip=t, dpi=200)
ren = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).transpose(Image.ROTATE_90)   # soat yo'nalishida burilganni qaytarish
ratio = ren.width / ren.height
check("Dizayn cho'zilmagan: vaucher nisbati asl rasm bilan bir xil", abs(ratio - AW / AH) / (AW / AH) < 0.005 and abs((t.height / t.width) - AW / AH) / (AW / AH) < 0.0005,
      f"vaucher {t.height / t.width:.4f}, asl {AW / AH:.4f}")
ren = ren.resize((AW // 4, AH // 4), Image.LANCZOS); ref = art.resize((AW // 4, AH // 4), Image.LANCZOS)
A, B = np.asarray(ref, np.int16), np.asarray(ren, np.int16)
mask = np.ones(A.shape[:2], bool)
for e in CFG["erase"] + [CFG["qr_box"] + [None]]:
    x0, y0, x1, y1 = [int(v / 4) for v in e[:4]]; mask[max(0, y0 - 3):y1 + 3, max(0, x0 - 3):x1 + 3] = False
dd = np.abs(A - B).mean(axis=2)[mask]
check("Dizayn asl rasm bilan mos (o'zgaruvchi zonalardan tashqari; farq faqat RGB→CMYK)", dd.mean() < 12, f"o'rtacha farq {dd.mean():.1f}/255")
fonts = {f[3] for f in pg.get_fonts(full=True)}
imgs = pg.get_images(full=True)
check("Shrift embed (subset), rasm CMYK ISO Coated v2, OutputIntent bor",
      all("+" in f for f in fonts) and doc.xref_get_key(doc.pdf_catalog(), "OutputIntents")[0] == "array" and all(i[5] in ("ICCBased",) for i in imgs), fonts)
json.dump(R, open(os.path.join(OUT, "test8_qa.json"), "w"), ensure_ascii=False, indent=1)
print(f"\n{sum(r['ok'] for r in R)}/{len(R)} PASS")
