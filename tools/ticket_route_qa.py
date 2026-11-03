#!/usr/bin/env python3
"""Bilet (11 222) — /ticket yo'liga o'tkazilgandan keyingi QA: master, QR arxivi, bosma PDF (har bir QR dekod)."""
import csv, json, os, re, sys, zipfile
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pymupdf as fitz
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V6 = "/home/claude/work/v6"
BASE = "https://dusel.pages.dev/ticket?code="
N = 11222
CODES = [f"{i:05d}" for i in range(1, N + 1)]
R = []
def check(n, ok, d=""):
    R.append(dict(name=n, ok=bool(ok), detail=str(d)[:300])); print(("PASS " if ok else "FAIL ") + n + (f" — {d}" if d != "" else ""), flush=True)

def dec_png(code):
    im = Image.open(os.path.join(ROOT, "qr", "QR_PNG", code + ".png")).convert("L")
    im = im.resize((im.width // 4, im.height // 4))
    return code, [z.data.decode() for z in decode(im, symbols=[ZBarSymbol.QRCODE])]

def dec_page(pno):
    d = fitz.open(os.path.join(ROOT, "out", "DUSEL_FRONT_FINAL_CMYK.pdf"))
    pix = d[pno].get_pixmap(dpi=200, colorspace=fitz.csGRAY)
    im = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    res = decode(im, symbols=[ZBarSymbol.QRCODE])
    words = [w[4] for w in d[pno].get_text("words") if re.fullmatch(r"\d{5}", w[4])]
    return pno, sorted(z.data.decode() for z in res), words

if __name__ == "__main__":
    M = list(csv.DictReader(open(os.path.join(ROOT, "master", "DUSEL_MASTER_FINAL.csv"), encoding="utf-8-sig")))
    check("Master: 11 222 bilet, 00001–11222, takrorsiz", [r["TICKET_NUMBER"] for r in M] == CODES)
    check("Master: har QR_URL = https://dusel.pages.dev/ticket?code=<raqam>", all(r["QR_URL"] == BASE + r["TICKET_NUMBER"] for r in M))
    v6 = list(csv.DictReader(open(os.path.join(V6, "master", "DUSEL_MASTER_FINAL.csv"), encoding="utf-8-sig")))
    check("Master: joy ma'lumotlari (BLITCHER/SEKTOR/QATOR/JOY) V6 bilan aynan bir xil — faqat QR_URL o'zgargan",
          all({k: v for k, v in a.items() if k != "QR_URL"} == {k: v for k, v in b.items() if k != "QR_URL"} for a, b in zip(v6, M)) and len(v6) == len(M))
    import openpyxl
    ws = openpyxl.load_workbook(os.path.join(ROOT, "master", "DUSEL_MASTER_FINAL.xlsx"), read_only=True)["MASTER"]
    rows = list(ws.iter_rows(values_only=True)); h = list(rows[0]); qi, ti = h.index("QR_URL"), h.index("TICKET_NUMBER")
    check("Master XLSX: 11 222 qator, QR_URL /ticket, raqam matn", sum(1 for r in rows[1:] if r[ti]) == N and all(r[qi] == BASE + r[ti] for r in rows[1:] if r[ti]))
    z = zipfile.ZipFile(os.path.join(ROOT, "qr", "DUSEL_TICKET_QR_11222.zip"))
    nm = z.namelist()
    check("QR arxivi: 11 222 SVG + 11 222 PNG, butun", sum(x.endswith(".svg") for x in nm) == N and sum(x.endswith(".png") for x in nm) == N and z.testzip() is None, len(nm))
    with ProcessPoolExecutor() as ex:
        res = dict(ex.map(dec_png, CODES, chunksize=200))
    bad = [c for c in CODES if res[c] != [BASE + c]]
    check("QR PNG: barcha 11 222 dekod qilindi, payload = /ticket?code=<raqam>", not bad, f"xato {bad[:5]}" if bad else "11222/11222")
    doc = fitz.open(os.path.join(ROOT, "out", "DUSEL_FRONT_FINAL_CMYK.pdf"))
    check("Bosma FRONT: 1 871 varaq, 450×320 mm", len(doc) == 1871 and all(abs(p.rect.width / 72 * 25.4 - 450) < .05 and abs(p.rect.height / 72 * 25.4 - 320) < .05 for p in doc))
    with ProcessPoolExecutor() as ex:
        pages = list(ex.map(dec_page, range(len(doc)), chunksize=20))
    badq, badw = [], []
    for pno, urls, words in pages:
        exp = CODES[pno * 6:(pno + 1) * 6]
        if urls != sorted(BASE + c for c in exp): badq.append((pno + 1, len(urls)))
        if words != exp: badw.append((pno + 1, words[:3]))
    check("Bosma FRONT: har varaqdagi barcha QR (11 222 ta) 200 dpi'da dekod qilindi va shu varaqdagi raqamlarga aynan mos", not badq, f"xato {badq[:5]}" if badq else "11222/11222")
    check("Bosma FRONT: bosilgan raqamlar tartibi 00001–11222", not badw, badw[:3])
    check("Bosma FRONT: oxirgi varaqda 2 bilet (11221, 11222)", pages[-1][2] == ["11221", "11222"])
    json.dump(R, open(os.path.join(ROOT, "out", "ticket_route_qa.json"), "w"), ensure_ascii=False, indent=1)
    print(f"\n{sum(r['ok'] for r in R)}/{len(R)} PASS")
