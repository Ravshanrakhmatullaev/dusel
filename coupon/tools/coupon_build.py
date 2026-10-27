#!/usr/bin/env python3
"""
DUSEL — GOLD (0001–2000) va SILVER (0001–4000) kuponlari: master, QR, bosma PDF.

Kupon URL (biletlardan alohida yo'l):  https://dusel.pages.dev/coupon?type=gold&code=0001
Bilet URL (o'zgarmaydi):               https://dusel.pages.dev/?code=00001

Dizayn: dizaynerning kupon_silver_va_gold.pdf fayli (1-sahifa SILVER, 2-sahifa GOLD; 450x320 mm, 6 ta 200x100 mm kupon)
o'zgarishsiz ishlatiladi. Qo'shiladi: QR (oq qutida), raqam (QR ostidagi "№:" qatorida va stubdagi "Kupon №:" yonida),
tashqi kesish belgilari. To'liq listlar — dizaynerning listi aynan; oxirgi list — faqat raqamli kuponlar.

Ishlatish:
  python coupon_build.py --pdf kupon.pdf --out out [--proof-only]
"""
import argparse, csv, hashlib, json, os, sys, zipfile
import pymupdf as fitz
import segno
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MM = 72 / 25.4
BASE = "https://dusel.pages.dev/coupon?type={t}&code={c}"
TYPES = {"GOLD": dict(count=2000, page=1, slug="gold"), "SILVER": dict(count=4000, page=0, slug="silver")}
SLOTS = [(25 + c * 200, 10 + r * 100) for r in range(3) for c in range(2)]   # mm, chap-yuqori
CW, CH = 200, 100
K, REG = (0, 0, 0, 1), (1, 1, 1, 1)
QR_MM = 17.0
FONT = os.path.join(HERE, "fonts", "Montserrat_700Bold.ttf")


def url(t, c):
    return BASE.format(t=TYPES[t]["slug"], c=c)


def qr_matrix(u):
    q = segno.make(u, version=4, error="m", mode="byte", boost_error=False, micro=False)
    return [list(r) for r in q.matrix_iter(scale=1, border=4)]


def runs(m):
    out = []
    for y, row in enumerate(m):
        x = 0
        while x < len(row):
            if row[x]:
                s = x
                while x < len(row) and row[x]:
                    x += 1
                out.append((s, y, x - s))
            else:
                x += 1
    return out


def slot_geometry(page):
    """Har bir slot uchun dizayndagi haqiqiy QR qutisi, '№:' va 'Kupon №:' yorliqlari (vektorlardan)."""
    dr = page.get_drawings()
    geo = []
    for (sx, sy) in SLOTS:
        o = fitz.Point(sx * MM, sy * MM)
        def find(pred):
            c = [g for g in dr if pred(g["rect"], g)]
            assert len(c) >= 1, (sx, sy)
            return c[0]["rect"]
        qbox = find(lambda r, g: "s" in g["type"] and abs(r.width - 17.19 * MM) < 0.3 * MM and abs(r.height - 17.16 * MM) < 0.3 * MM
                    and abs(r.x0 - (o.x + 56.73 * MM)) < 1.5 * MM and abs(r.y0 - (o.y + 4.70 * MM)) < 1.5 * MM)
        strip = find(lambda r, g: "s" in g["type"] and abs(r.x0 - qbox.x0) < 0.5 and abs(r.y1 - (qbox.y1 + 3.0 * MM)) < 0.6 * MM
                     and r.y0 > qbox.y0 + 10 * MM)
        nlab = find(lambda r, g: g["type"] == "f" and strip.contains(r) and len(g["items"]) == 46)
        klab = find(lambda r, g: g["type"] == "f" and len(g["items"]) == 122 and abs(r.x0 - (o.x + 5.13 * MM)) < 1.0 * MM
                    and o.y + 30 * MM < r.y0 < o.y + 40 * MM)
        geo.append(dict(origin=o, qbox=qbox, strip=strip, nlab=nlab, klab=klab))
    return geo


def k_baseline(page, klab):
    """'Kupon №:' yorlig'idagi 'K' harfining pastki cheti = tayanch chiziq (rasterdan)."""
    import numpy as np
    clip = fitz.Rect(klab.x0 - 0.2, klab.y0 - 1, klab.x0 + 1.7 * MM, klab.y1 + 1)
    pix = page.get_pixmap(dpi=2400, clip=clip, colorspace=fitz.csGRAY)
    A = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    ys = np.where((A < 100).any(1))[0]
    return clip.y0 + (ys.max() + 1) / (2400 / 72)


def master(out):
    files = {}
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    for t, cfg in TYPES.items():
        rows = [dict(TYPE=t, COUPON_NUMBER=str(i).zfill(4), QR_URL=url(t, str(i).zfill(4))) for i in range(1, cfg["count"] + 1)]
        p = os.path.join(out, f"DUSEL_COUPON_{t}_MASTER.csv")
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["TYPE", "COUPON_NUMBER", "QR_URL"])
            w.writeheader()
            w.writerows(rows)
        wb = Workbook()
        ws = wb.active
        ws.title = t
        ws.append(["TYPE", "COUPON_NUMBER", "QR_URL"])
        for r in rows:
            ws.append([r["TYPE"], r["COUPON_NUMBER"], r["QR_URL"]])
        for c in ws["B"]:
            c.number_format = "@"
        fill = PatternFill("solid", fgColor="C9A227" if t == "GOLD" else "8A9099")
        for c in ws[1]:
            c.font, c.fill, c.alignment = Font(bold=True, color="FFFFFF"), fill, Alignment(horizontal="center")
        ws.column_dimensions["A"].width, ws.column_dimensions["B"].width, ws.column_dimensions["C"].width = 10, 16, 58
        ws.freeze_panes = "A2"
        wb.save(os.path.join(out, f"DUSEL_COUPON_{t}_MASTER.xlsx"))
        files[t] = rows
    return files


def qr_files(out, data):
    for t, rows in data.items():
        d = os.path.join(out, f"qr_{t.lower()}")
        os.makedirs(os.path.join(d, "SVG"), exist_ok=True)
        os.makedirs(os.path.join(d, "PNG"), exist_ok=True)
        for r in rows:
            m = qr_matrix(r["QR_URL"])
            n = len(m)
            path = "".join(f"M{x} {y}h{l}v1h-{l}z" for (x, y, l) in runs(m))
            name = f"{t}_{r['COUPON_NUMBER']}"
            with open(os.path.join(d, "SVG", name + ".svg"), "w") as f:
                f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="{QR_MM}mm" '
                        f'height="{QR_MM}mm" viewBox="0 0 {n} {n}" shape-rendering="crispEdges"><rect width="{n}" height="{n}" '
                        f'fill="#FFFFFF"/><path fill="#000000" d="{path}"/></svg>\n')
            img = Image.new("1", (n, n), 1)
            px = img.load()
            for y, row in enumerate(m):
                for x, v in enumerate(row):
                    if v:
                        px[x, y] = 0
            img.resize((n * 24, n * 24), Image.NEAREST).save(os.path.join(d, "PNG", name + ".png"), dpi=(300, 300), optimize=True)
        zp = os.path.join(out, f"DUSEL_COUPON_{t}_QR.zip")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for r in rows:
                name = f"{t}_{r['COUPON_NUMBER']}"
                z.write(os.path.join(d, "SVG", name + ".svg"), f"SVG/{name}.svg")
                z.write(os.path.join(d, "PNG", name + ".png"), f"PNG/{name}.png")
            z.write(os.path.join(out, f"DUSEL_COUPON_{t}_MASTER.csv"), f"DUSEL_COUPON_{t}_MASTER.csv")


def impose(src_path, t, rows, out_path, sheets=None):
    src = fitz.open(src_path)
    pno = TYPES[t]["page"]
    sp = src[pno]
    geo = slot_geometry(sp)
    kbase = [k_baseline(sp, g["klab"]) for g in geo]
    font_buf = open(FONT, "rb").read()
    F = fitz.Font(fontbuffer=font_buf)
    W, H = sp.rect.width, sp.rect.height
    total = -(-len(rows) // 6)
    sheets = sheets or list(range(1, total + 1))
    doc = fitz.open()
    layout = []

    def text_center(page, cx, base, s, size):
        w = F.text_length(s, fontsize=size)
        page.insert_text((cx - w / 2, base), s, fontname="MB", fontsize=size, color=K)

    for sh in sheets:
        chunk = rows[(sh - 1) * 6: sh * 6]
        page = doc.new_page(width=W, height=H)
        page.insert_font(fontname="MB", fontbuffer=font_buf)
        if len(chunk) == 6:
            page.show_pdf_page(page.rect, src, pno)                       # dizaynerning listi aynan
        else:
            for i in range(len(chunk)):                                   # oxirgi list: faqat raqamli kuponlar
                sx, sy = SLOTS[i]
                r = fitz.Rect(sx * MM, sy * MM, (sx + CW) * MM, (sy + CH) * MM)
                page.show_pdf_page(r, src, pno, clip=r)
        for i, row in enumerate(chunk):
            g = geo[i]
            m = qr_matrix(row["QR_URL"])
            n = len(m)
            qs = QR_MM * MM
            mod = qs / n
            qx = g["qbox"].x0 + (g["qbox"].width - qs) / 2
            qy = g["qbox"].y0 + (g["qbox"].height - qs) / 2
            shp = page.new_shape()
            for (x, y, l) in runs(m):
                shp.draw_rect(fitz.Rect(qx + x * mod, qy + y * mod, qx + (x + l) * mod, qy + (y + 1) * mod))
            shp.finish(fill=K, color=None, width=0)
            shp.commit()
            # QR ostidagi "№:" qatori — ko'rinadigan oraliq markazida, "№:" bilan bir tayanch chiziqda
            st = 0.2835
            top, bot = g["qbox"].y1 + st / 2, g["strip"].y1 - st / 2
            base = (top + bot) / 2 + 0.35 * 6.5
            cx = (g["nlab"].x1 + 1.2 + g["strip"].x1 - st / 2 - 1.2) / 2
            text_center(page, cx, base, row["COUPON_NUMBER"], 6.5)
            # stub: "Kupon №:" dan keyin, bir tayanch chiziqda
            kx = g["klab"].x1 + 1.5 * MM
            page.insert_text((kx, kbase[i]), row["COUPON_NUMBER"], fontname="MB", fontsize=14, color=K)
            layout.append(dict(sheet=sh, slot=i + 1, number=row["COUPON_NUMBER"],
                               qr=[round(v, 3) for v in (qx, qy, qx + qs, qy + qs)],
                               strip_num=[round(v, 3) for v in (cx - F.text_length(row["COUPON_NUMBER"], fontsize=6.5) / 2, base - 0.712 * 6.5,
                                                                cx + F.text_length(row["COUPON_NUMBER"], fontsize=6.5) / 2, base + 0.012 * 6.5)],
                               stub_num=[round(v, 3) for v in (kx, kbase[i] - 0.712 * 14, kx + F.text_length(row["COUPON_NUMBER"], fontsize=14), kbase[i] + 0.012 * 14)],
                               qbox=[round(v, 3) for v in g["qbox"]], strip=[round(v, 3) for v in g["strip"]], klab=[round(v, 3) for v in g["klab"]]))
        # tashqi kesish belgilari (Registration), to'rdan 2 mm tashqarida
        L, O = 5 * MM, 2 * MM
        gx0, gy0, gx1, gy1 = 25 * MM, 10 * MM, 425 * MM, 310 * MM
        shp = page.new_shape()
        for x in (25, 225, 425):
            shp.draw_line((x * MM, gy0 - O - L), (x * MM, gy0 - O))
            shp.draw_line((x * MM, gy1 + O), (x * MM, gy1 + O + L))
        for y in (10, 110, 210, 310):
            shp.draw_line((gx0 - O - L, y * MM), (gx0 - O, y * MM))
            shp.draw_line((gx1 + O, y * MM), (gx1 + O + L, y * MM))
        shp.finish(color=REG, width=0.25, closePath=False)
        shp.commit()
        page.set_trimbox(page.rect)
    doc.subset_fonts()
    tmp = out_path + ".tmp.pdf"
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    import pikepdf
    icc_ref = int(src.xref_object(17).split("/ICCBased")[1].split()[0])
    with pikepdf.open(tmp) as pdf:
        icc = pdf.make_stream(src.xref_stream(icc_ref))
        icc.N = 4
        icc.Alternate = pikepdf.Name.DeviceCMYK
        pdf.Root.OutputIntents = pikepdf.Array([pikepdf.Dictionary(
            Type=pikepdf.Name.OutputIntent, S=pikepdf.Name.GTS_PDFX, OutputConditionIdentifier="FOGRA39",
            RegistryName="http://www.color.org", Info="ISO Coated v2 (ECI)", DestOutputProfile=icc)])
        pdf.docinfo["/Title"] = f"DUSEL {t} kupon — 6-up"
        pdf.save(out_path)
    os.remove(tmp)
    json.dump(layout, open(out_path.replace(".pdf", "_layout.json"), "w"), indent=0)
    print("OK", out_path, len(sheets), "list")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--step", default="all", choices=["all", "master", "qr", "proof", "print"])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    data = master(a.out)
    if a.step in ("all", "qr"):
        qr_files(a.out, data)
    if a.step in ("all", "proof"):
        for t in TYPES:
            impose(a.pdf, t, data[t], os.path.join(a.out, f"DUSEL_COUPON_{t}_PROOF.pdf"), sheets=[1])
    if a.step in ("all", "print"):
        for t in TYPES:
            impose(a.pdf, t, data[t], os.path.join(a.out, f"DUSEL_COUPON_{t}_PRINT.pdf"))


if __name__ == "__main__":
    main()
