#!/usr/bin/env python3
"""
DUSEL GAL — to'liq bosma: 1000 ta vaucher (0001–1000), tasdiqlangan test varag'i bilan aynan bir xil joylash.

Varaq 320 × 450 mm (portret), har varaqda 8 ta vaucher 156.04 × 66.29 mm (90° burilgan, 4 ustun × 2 qator),
4 mm kesish oralig'i, tashqi kesish belgilari. 125 varaq.
Har varaqda: 1-qator n+1 … n+4, 2-qator n+5 … n+8 (chapdan o'ngga).

Ishlatish: python gal_8up_320x450.py --config gal_layout.json --master out4/DUSEL_GAL_MASTER.csv --out out4
"""
import argparse, csv, json, math, os, sys
import pymupdf as fitz

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gal_impose as GI  # noqa: E402

MM = 72 / 25.4
PER = 8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--master", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="DUSEL_GAL_1000_8UP_320x450_FINAL.pdf")
    ap.add_argument("--count", type=int, default=1000)
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    assert cfg["voucher_mm"] == [156.04, 66.29] and cfg["layout"] == {"cols": 2, "rows": 4, "rotated": False}
    rows = list(csv.DictReader(open(a.master, encoding="utf-8-sig")))[:a.count]
    assert [r["VOUCHER_NUMBER"] for r in rows] == [f"{i:04d}" for i in range(1, a.count + 1)]
    assert all(r["QR_URL"] == "https://dusel.pages.dev/gal?code=" + r["VOUCHER_NUMBER"] for r in rows)
    sheets = math.ceil(len(rows) / PER)
    # landshaft slot k (qator r=k//2, ustun c=k%2) soat yo'nalishida 90° burilgach portretda ustun 3-r, qator c bo'ladi
    order = [(k % 2) * 4 + (3 - k // 2) for k in range(PER)]
    ordered = []
    for s in range(sheets):
        chunk = rows[s * PER:(s + 1) * PER]
        assert len(chunk) == PER, "oxirgi varaq to'liq bo'lishi kerak (1000 = 125 × 8)"
        ordered += [chunk[i] for i in order]
    base = GI.prepare_base(cfg, a.out)
    land = os.path.join(a.out, "_landscape.pdf")
    GI.impose(cfg, ordered, land, base, "PRINT")
    L = json.load(open(land.replace(".pdf", "_layout.json")))
    src = fitz.open(land)
    W, H = src[0].rect.width, src[0].rect.height
    f = lambda x, y: (H - y, x)            # soat yo'nalishida 90° (test varag'ida empirik tasdiqlangan)
    def T(r):
        (x1, y1), (x2, y2) = f(r[0], r[1]), f(r[2], r[3])
        return [round(min(x1, x2), 3), round(min(y1, y2), 3), round(max(x1, x2), 3), round(max(y1, y2), 3)]
    doc = fitz.open()
    for p in range(len(src)):
        pg = doc.new_page(width=H, height=W)
        pg.show_pdf_page(pg.rect, src, p, rotate=-90)
    lay = [dict(x, trim=T(x["trim"]), bleed=T(x["bleed"]), qr=T(x["qr"]), num=T(x["num"])) for x in L]
    out_pdf = os.path.join(a.out, a.name)
    doc.save(out_pdf, garbage=3, deflate=True)
    GI.add_output_intent(out_pdf)
    json.dump(lay, open(out_pdf.replace(".pdf", "_layout.json"), "w"), ensure_ascii=False)
    os.remove(land); os.remove(land.replace(".pdf", "_layout.json"))
    print("OK", out_pdf, len(doc), "varaq")


if __name__ == "__main__":
    main()
