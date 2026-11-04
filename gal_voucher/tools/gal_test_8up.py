#!/usr/bin/env python3
"""
DUSEL GAL — FAQAT 1 ta test varaq: 320 × 450 mm, 8 ta vaucher 156.04 × 66.29 mm, raqamlar 0001–0008.

Joylash: varaq 320 mm eni × 450 mm bo'yi (portret). Vaucherlar 90° burilgan holda 4 ustun × 2 qator
(xuddi 450×320 landshaft varaqdagi 2×4 joylashning o'zi, varaq 90° burilgan). Vaucherlar orasida 4 mm kesish
oralig'i (har vaucherga 2 mm bleed), tashqi hoshiyada kesish belgilari. Dizayn cho'zilmaydi.

Ishlatish: python gal_test_8up.py --config gal_layout.json --out out_test8
"""
import argparse, json, os, sys
import pymupdf as fitz

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gal_build, gal_impose as GI  # noqa: E402

MM = 72 / 25.4
N = 8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    assert cfg["voucher_mm"] == [156.04, 66.29] and cfg["layout"]["cols"] * cfg["layout"]["rows"] == N
    os.makedirs(a.out, exist_ok=True)
    rows = gal_build.rows()[:N]                       # 0001–0008, https://dusel.pages.dev/gal?code=0001 …
    assert [r["VOUCHER_NUMBER"] for r in rows] == [f"{i:04d}" for i in range(1, N + 1)]
    base = GI.prepare_base(cfg, a.out)
    land = os.path.join(a.out, "_landscape_450x320.pdf")
    # Portret varaqda o'qish tartibi chapdan o'ngga, yuqoridan pastga bo'lishi uchun (soat yo'nalishida 90° burilgandan keyin):
    #   1-qator 0001 0002 0003 0004 · 2-qator 0005 0006 0007 0008
    # landshaft slot k (qator r=k//2, ustun c=k%2) -> portret ustun 3-r, qator c -> raqam c*4 + (3-r) + 1
    order = [(k % 2) * 4 + (3 - k // 2) for k in range(N)]
    rows = [rows[i] for i in order]
    GI.impose(cfg, rows, land, base, "TEST")          # 450 × 320 landshaft, 2 ustun × 4 qator
    L = json.load(open(land.replace(".pdf", "_layout.json")))
    src = fitz.open(land)
    W, H = src[0].rect.width, src[0].rect.height      # 450 × 320 mm
    doc = fitz.open()
    pg = doc.new_page(width=H, height=W)              # 320 × 450 mm portret
    pg.show_pdf_page(pg.rect, src, 0, rotate=-90)     # landshaft sahifani soat yo'nalishida 90° burish
    # landshaft nuqtasi (x, y) -> portret: burilish yo'nalishini empirik aniqlaymiz (sinov nuqtasi bilan)
    probe = fitz.open(); pp = probe.new_page(width=W, height=H)
    pp.draw_rect(fitz.Rect(0, 0, 20, 10), color=None, fill=(0, 0, 0));
    t = fitz.open(); tp = t.new_page(width=H, height=W); tp.show_pdf_page(tp.rect, probe, 0, rotate=-90)
    pix = tp.get_pixmap(dpi=36, colorspace=fitz.csGRAY)
    import numpy as np
    A = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    ys, xs = np.where(A < 128)
    top_right = xs.mean() > pix.w / 2 and ys.mean() < pix.h / 2
    top_left = xs.mean() < pix.w / 2 and ys.mean() < pix.h / 2
    bottom_left = xs.mean() < pix.w / 2 and ys.mean() > pix.h / 2
    if top_right:      # (x, y) -> (H - y, x)   — soat yo'nalishida
        f = lambda x, y: (H - y, x)
    elif bottom_left:  # (x, y) -> (y, W - x)   — soat yo'nalishiga teskari
        f = lambda x, y: (y, W - x)
    else:
        raise SystemExit(f"kutilmagan burilish {top_left}")
    def T(r):
        (a1, b1), (a2, b2) = f(r[0], r[1]), f(r[2], r[3])
        return [round(min(a1, a2), 3), round(min(b1, b2), 3), round(max(a1, a2), 3), round(max(b1, b2), 3)]
    lay = [dict(x, trim=T(x["trim"]), bleed=T(x["bleed"]), qr=T(x["qr"]), num=T(x["num"])) for x in L]
    out_pdf = os.path.join(a.out, "DUSEL_GAL_TEST_8UP_320x450.pdf")
    doc.save(out_pdf, garbage=3, deflate=True)
    GI.add_output_intent(out_pdf)
    json.dump(lay, open(out_pdf.replace(".pdf", "_layout.json"), "w"), ensure_ascii=False, indent=1)
    d = fitz.open(out_pdf)
    d[0].get_pixmap(dpi=100).save(os.path.join(a.out, "DUSEL_GAL_TEST_8UP_PREVIEW.png"))
    os.remove(land); os.remove(land.replace(".pdf", "_layout.json"))
    print("OK", out_pdf, d[0].rect.width / MM, d[0].rect.height / MM, "rotation", "CW" if top_right else "CCW")


if __name__ == "__main__":
    main()
