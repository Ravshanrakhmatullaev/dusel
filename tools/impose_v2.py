#!/usr/bin/env python3
"""
DUSEL — 6-up bosma (2-revizya).

* Asl artwork o'zgarishsiz joylanadi (Form XObject, masshtab 1:1, faqat kesish chizig'i bo'yicha clip).
* O'zgaruvchan ma'lumot (QR, raqam, SEKTOR/QATOR/JOY) faqat 100% K (DeviceCMYK 0/0/0/1), vektor.
* Varaq 450x320 mm, 2x3, oraliqsiz, markazda; faqat tashqi kesish belgilari (Registration), texnik yozuvsiz.
* 1-sahifa: old tomon; 2-sahifa (ixtiyoriy): orqa tomon, chapdan-o'ngga aylantirish (work-and-turn).

Ishlatish (namuna):
  python impose_v2.py --art artwork/src_cmyk.pdf --map sample/sample_6.csv --out DUSEL_TEST_6UP_CMYK.pdf --with-back
To'liq ishlab chiqarish faqat --approved bayrog'i bilan (namuna tasdiqlangandan keyin).
"""
import argparse, csv, io, os, sys
import pymupdf as fitz
import segno

HERE = os.path.dirname(os.path.abspath(__file__))
MM = 72 / 25.4
BASE_URL = "https://dusel.pages.dev/?code="
QR_VERSION = 3

# --- asl sahifa koordinatalari (PyMuPDF, chap-yuqori; asl PDF MediaBox [-1 -1 ...] hisobga olingan)
FRONT = fitz.Rect(15.1732, 17.6947, 582.1024, 301.1592)   # 566.9292 x 283.4645 pt = 200.000 x 100.000 mm
BACK = fitz.Rect(15.1732, 315.7106, 582.1024, 599.1752)
QR_BOX = fitz.Rect(425.24, 231.74, 473.96, 280.45)          # oq QR qutisi (konturi 0.2835 pt)
NUM_AREA = fitz.Rect(435.62, 280.45, 473.96, 288.98)        # "№:" dan o'ngdagi maydon, QR qutisi chizig'i ostida
NUM_LABEL_BASELINE = 287.02                                  # asl "№:" yozuvi tayanch chizig'i
STROKE = 0.2835
SEAT_BOX = fitz.Rect(36.46, 226.06, 192.26, 248.5)
SEAT_DIVIDERS = (91.14, 145.39)                              # 0.5669 pt
SEAT_LABEL_BASELINE = 234.19
SEAT_LABEL_CENTERS = (62.91, 118.27, 168.02)                 # "SEKTOR №", "QATOR №", "JOY №" markazlari

QR_MM = 17.0
NUM_PT = 6.5
SEAT_PT = 9.0
K = (0, 0, 0, 1)
REG = (1, 1, 1, 1)


def qr_runs(url):
    qr = segno.make(url, version=QR_VERSION, error="m", mode="byte", boost_error=False, micro=False)
    m = [list(r) for r in qr.matrix_iter(scale=1, border=4)]
    runs = []
    for y, row in enumerate(m):
        x = 0
        while x < len(row):
            if row[x]:
                s = x
                while x < len(row) and row[x]:
                    x += 1
                runs.append((s, y, x - s))
            else:
                x += 1
    return len(m), runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--art", required=True)
    ap.add_argument("--map", required=True, help="CSV: NUMBER,SECTOR,ROW,SEAT (tartib bo'yicha)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sheet-w", type=float, default=450)
    ap.add_argument("--sheet-h", type=float, default=320)
    ap.add_argument("--with-back", action="store_true")
    ap.add_argument("--approved", action="store_true", help="6 tadan ko'p bilet uchun majburiy")
    ap.add_argument("--icc", default=None, help="OutputIntent uchun CMYK ICC")
    ap.add_argument("--font", default=os.path.join(HERE, "fonts", "Montserrat_700Bold.ttf"))
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.map, encoding="utf-8-sig")))
    if len(rows) > 6 and not a.approved:
        sys.exit("TO'XTATILDI: to'liq ishlab chiqarish namuna tasdiqlanmaguncha bajarilmaydi (--approved).")

    src = fitz.open(a.art)
    SW, SH = a.sheet_w * MM, a.sheet_h * MM
    tw, th = FRONT.width, FRONT.height
    cols, nrows = 2, 3
    gw, gh = cols * tw, nrows * th
    assert gw <= SW and gh <= SH
    ox, oy = (SW - gw) / 2, (SH - gh) / 2
    slots = [(ox + c * tw, oy + r * th) for r in range(nrows) for c in range(cols)]

    font_buf = open(a.font, "rb").read()
    F = fitz.Font(fontbuffer=font_buf)
    qsize = QR_MM * MM

    def text_center(page, cx, baseline, txt, size, maxw):
        s = size
        while F.text_length(txt, fontsize=s) > maxw and s > 5:
            s -= 0.25
        w = F.text_length(txt, fontsize=s)
        page.insert_text((cx - w / 2, baseline), txt, fontname="MB", fontsize=s, color=K)
        return fitz.Rect(cx - w / 2, baseline - 0.712 * s, cx + w / 2, baseline + 0.012 * s), s

    def crop_marks(page):
        L, O = 5 * MM, 2 * MM
        xs = sorted({round(x, 4) for x, _ in slots} | {round(x + tw, 4) for x, _ in slots})
        ys = sorted({round(y, 4) for _, y in slots} | {round(y + th, 4) for _, y in slots})
        sh = page.new_shape()
        for x in xs:
            sh.draw_line((x, oy - O - L), (x, oy - O))
            sh.draw_line((x, oy + gh + O), (x, oy + gh + O + L))
        for y in ys:
            sh.draw_line((ox - O - L, y), (ox - O, y))
            sh.draw_line((ox + gw + O, y), (ox + gw + O + L, y))
        sh.finish(color=REG, width=0.25, closePath=False)
        sh.commit()
        return xs, ys

    out = fitz.open()
    report = []
    for sheet_i in range(0, len(rows), 6):
        chunk = rows[sheet_i:sheet_i + 6]
        page = out.new_page(width=SW, height=SH)
        page.insert_font(fontname="MB", fontbuffer=font_buf)
        for i, r in enumerate(chunk):
            x, y = slots[i]
            tgt = fitz.Rect(x, y, x + tw, y + th)
            page.show_pdf_page(tgt, src, 0, clip=FRONT)
            dx, dy = x - FRONT.x0, y - FRONT.y0                # asl koordinata -> varaq
            code = r["NUMBER"]
            # QR — oq qutining markazida, 4 modul oq himoya maydoni QR ichida
            n, runs = qr_runs(BASE_URL + code)
            m = qsize / n
            qx = QR_BOX.x0 + (QR_BOX.width - qsize) / 2 + dx
            qy = QR_BOX.y0 + (QR_BOX.height - qsize) / 2 + dy
            sh = page.new_shape()
            for (rx, ry, rl) in runs:
                sh.draw_rect(fitz.Rect(qx + rx * m, qy + ry * m, qx + (rx + rl) * m, qy + (ry + 1) * m))
            sh.finish(fill=K, color=None, width=0)
            sh.commit()
            # raqam — "№:" bilan bir tayanch chiziqda, QR qutisi chizig'i va pastki chegara orasida markazda
            inner_top = NUM_AREA.y0 + STROKE / 2
            inner_bot = NUM_AREA.y1 - STROKE / 2
            baseline = (inner_top + inner_bot) / 2 + 0.35 * NUM_PT
            cx = (NUM_AREA.x0 + 1.2 + NUM_AREA.x1 - STROKE / 2 - 1.2) / 2
            nr, _ = text_center(page, cx + dx, baseline + dy, code, NUM_PT, NUM_AREA.width - 4)
            # SEKTOR / QATOR / JOY
            col_bounds = [(SEAT_BOX.x0, SEAT_DIVIDERS[0]), (SEAT_DIVIDERS[0], SEAT_DIVIDERS[1]), (SEAT_DIVIDERS[1], SEAT_BOX.x1)]
            sb = (SEAT_LABEL_BASELINE + SEAT_BOX.y1) / 2 + 0.35 * SEAT_PT
            vals = [r["SECTOR"], str(r["ROW"]), str(r["SEAT"])]
            seat_rects = []
            for (c0, c1), lc, v in zip(col_bounds, SEAT_LABEL_CENTERS, vals):
                maxw = min(lc - c0, c1 - lc) * 2 - 6
                rr, s = text_center(page, lc + dx, sb + dy, v, SEAT_PT, maxw)
                seat_rects.append((v, [round(t - d, 3) for t, d in zip(rr, (dx, dy, dx, dy))], s))
            report.append(dict(sheet=sheet_i // 6 + 1, slot=i + 1, number=code, sector=vals[0], row=vals[1], seat=vals[2],
                               ticket_rect_mm=[round(v / MM, 3) for v in tgt],
                               qr_rect_local=[round(qx - dx, 3), round(qy - dy, 3), round(qx - dx + qsize, 3), round(qy - dy + qsize, 3)],
                               num_rect_local=[round(t - d, 3) for t, d in zip(nr, (dx, dy, dx, dy))],
                               seat_text=seat_rects))
        xs, ys = crop_marks(page)
        page.set_trimbox(page.rect)
        if a.with_back:
            bp = out.new_page(width=SW, height=SH)
            for i in range(len(chunk)):
                x, y = slots[i]
                mx = SW - x - tw                                 # work-and-turn: ustunlar ko'zguda
                bp.show_pdf_page(fitz.Rect(mx, y, mx + tw, y + th), src, 0, clip=BACK)
            crop_marks(bp)
            bp.set_trimbox(bp.rect)

    out.subset_fonts()
    tmp = a.out + ".tmp.pdf"
    out.save(tmp, garbage=3, deflate=True)
    out.close()
    # OutputIntent (rang sharoiti) — PDF/X muvofiqligini da'vo qilmaydi, faqat chop sharoitini bildiradi
    import pikepdf
    with pikepdf.open(tmp) as pdf:
        if a.icc:
            icc = pdf.make_stream(open(a.icc, "rb").read())
            icc.N = 4
            icc.Alternate = pikepdf.Name.DeviceCMYK
            pdf.Root.OutputIntents = pikepdf.Array([pikepdf.Dictionary(
                Type=pikepdf.Name.OutputIntent, S=pikepdf.Name.GTS_PDFX,
                OutputConditionIdentifier="FOGRA39", RegistryName="http://www.color.org",
                OutputCondition="Offset, coated paper (ISO 12647-2:2004)",
                Info="ISO Coated v2 (ECI)", DestOutputProfile=icc)])
        pdf.docinfo["/Title"] = "DUSEL Yulduzli Kecha — 6-up"
        pdf.save(a.out)
    os.remove(tmp)
    import json
    json.dump(dict(sheet_mm=[a.sheet_w, a.sheet_h], grid_origin_mm=[round(ox / MM, 3), round(oy / MM, 3)],
                   ticket_mm=[round(tw / MM, 4), round(th / MM, 4)], cut_x_mm=[round(v / MM, 3) for v in xs],
                   cut_y_mm=[round(v / MM, 3) for v in ys], tickets=report),
              open(a.out.replace(".pdf", "_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OK", a.out, len(rows), "bilet")


if __name__ == "__main__":
    main()
