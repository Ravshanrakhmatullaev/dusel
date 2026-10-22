#!/usr/bin/env python3
"""
DUSEL — ishlab chiqarish 6-up imposition (DUSEL_MASTER_11222.csv -> FRONT/BACK CMYK PDF).

* Artwork: src_cmyk.pdf (asl Bilet_final.pdf, faqat texnik kontur bo'yalmaydi + ICC orqali CMYK). Masshtab 1:1.
* O'zgaruvchan: QR (vektor), raqam, SEKTOR/QATOR/JOY — faqat 100% K.
* Varaq 450x320 mm, 2x3, oraliqsiz, markazda; tashqi kesish belgilari (Registration); texnik yozuv yo'q.
* Orqa tomon: varaq CHAPDAN-O'NGGA (vertikal o'q atrofida) aylantiriladi -> old (ustun c, qator r) orqasi = (1-c, r).

Ishlatish:
  python impose_prod.py --master DUSEL_MASTER_11222.csv --art src_cmyk.pdf --icc ISO.icc --front F.pdf --back B.pdf --all
  python impose_prod.py ... --sheets 1 --combined PROOF.pdf          (old+orqa bitta faylda)
  python impose_prod.py ... --sheets 1 --combined DUPLEX.pdf --duplex-marks   (faqat test: hoshiyada pozitsiya raqamlari)
"""
import argparse, csv, hashlib, json, os, sys
import pymupdf as fitz

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import impose_v2 as IV  # geometriya konstantalari va QR

MM = 72 / 25.4
K, REG = (0, 0, 0, 1), (1, 1, 1, 1)


def parse_sheets(s, total):
    out = []
    for part in s.split(","):
        a, _, b = part.partition("-")
        out += range(int(a), int(b or a) + 1)
    return [x for x in out if 1 <= x <= total]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", required=True)
    ap.add_argument("--art", required=True)
    ap.add_argument("--icc", required=True)
    ap.add_argument("--front")
    ap.add_argument("--back")
    ap.add_argument("--combined")
    ap.add_argument("--sheets", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--duplex-marks", action="store_true")
    ap.add_argument("--font", default=os.path.join(HERE, "fonts", "Montserrat_700Bold.ttf"))
    a = ap.parse_args()

    msha = hashlib.sha256(open(a.master, "rb").read()).hexdigest()
    rows = list(csv.DictReader(open(a.master, encoding="utf-8-sig")))
    total_sheets = -(-len(rows) // 6)
    if a.all:
        sheets = list(range(1, total_sheets + 1))
    elif a.sheets:
        sheets = parse_sheets(a.sheets, total_sheets)
    else:
        sys.exit("--all yoki --sheets kerak")

    src = fitz.open(a.art)
    SW, SH = 450 * MM, 320 * MM
    tw, th = IV.FRONT.width, IV.FRONT.height
    ox, oy = (SW - 2 * tw) / 2, (SH - 3 * th) / 2
    slots = [(ox + c * tw, oy + r * th) for r in range(3) for c in range(2)]
    font_buf = open(a.font, "rb").read()
    F = fitz.Font(fontbuffer=font_buf)
    qsize = IV.QR_MM * MM
    grid = (ox, oy, 2 * tw, 3 * th)

    def text_center(page, cx, baseline, txt, size, maxw):
        s = size
        while F.text_length(txt, fontsize=s) > maxw and s > 5:
            s -= 0.25
        w = F.text_length(txt, fontsize=s)
        page.insert_text((cx - w / 2, baseline), txt, fontname="MB", fontsize=s, color=K)
        return s

    def crop_marks(page):
        L, O = 5 * MM, 2 * MM
        xs = [ox, ox + tw, ox + 2 * tw]
        ys = [oy + r * th for r in range(4)]
        sh = page.new_shape()
        for x in xs:
            sh.draw_line((x, oy - O - L), (x, oy - O))
            sh.draw_line((x, oy + 3 * th + O), (x, oy + 3 * th + O + L))
        for y in ys:
            sh.draw_line((ox - O - L, y), (ox - O, y))
            sh.draw_line((ox + 2 * tw + O, y), (ox + 2 * tw + O + L, y))
        sh.finish(color=REG, width=0.25, closePath=False)
        sh.commit()

    def front_page(doc, sheet_no):
        chunk = rows[(sheet_no - 1) * 6: sheet_no * 6]
        page = doc.new_page(width=SW, height=SH)
        page.insert_font(fontname="MB", fontbuffer=font_buf)
        for i, r in enumerate(chunk):
            x, y = slots[i]
            page.show_pdf_page(fitz.Rect(x, y, x + tw, y + th), src, 0, clip=IV.FRONT)
            dx, dy = x - IV.FRONT.x0, y - IV.FRONT.y0
            code = r["TICKET_NUMBER"]
            assert r["QR_URL"] == IV.BASE_URL + code
            n, runs = IV.qr_runs(r["QR_URL"])
            m = qsize / n
            qx = IV.QR_BOX.x0 + (IV.QR_BOX.width - qsize) / 2 + dx
            qy = IV.QR_BOX.y0 + (IV.QR_BOX.height - qsize) / 2 + dy
            sh = page.new_shape()
            for (rx, ry, rl) in runs:
                sh.draw_rect(fitz.Rect(qx + rx * m, qy + ry * m, qx + (rx + rl) * m, qy + (ry + 1) * m))
            sh.finish(fill=K, color=None, width=0)
            sh.commit()
            inner_top, inner_bot = IV.NUM_AREA.y0 + IV.STROKE / 2, IV.NUM_AREA.y1 - IV.STROKE / 2
            cx = (IV.NUM_AREA.x0 + 1.2 + IV.NUM_AREA.x1 - IV.STROKE / 2 - 1.2) / 2
            text_center(page, cx + dx, (inner_top + inner_bot) / 2 + 0.35 * IV.NUM_PT + dy, code, IV.NUM_PT, IV.NUM_AREA.width - 4)
            cols = [(IV.SEAT_BOX.x0, IV.SEAT_DIVIDERS[0]), IV.SEAT_DIVIDERS, (IV.SEAT_DIVIDERS[1], IV.SEAT_BOX.x1)]
            sb = (IV.SEAT_LABEL_BASELINE + IV.SEAT_BOX.y1) / 2 + 0.35 * IV.SEAT_PT
            for (c0, c1), lc, v in zip(cols, IV.SEAT_LABEL_CENTERS, (r["SECTOR"], r["ROW"], r["SEAT"])):
                text_center(page, lc + dx, sb + dy, v, IV.SEAT_PT, min(lc - c0, c1 - lc) * 2 - 6)
        crop_marks(page)
        page.set_trimbox(page.rect)
        if a.duplex_marks:
            for i in range(len(chunk)):
                x, y = slots[i]
                col = i % 2
                lx = x - 14 * MM if col == 0 else x + tw + 6 * MM
                page.insert_text((lx, y + th / 2), f"{i + 1}", fontname="MB", fontsize=22, color=K)
            page.insert_text((ox, 6 * MM), "OLD TOMON — YUQORI CHETI", fontname="MB", fontsize=9, color=K)
        return len(chunk)

    def back_page(doc, used):
        page = doc.new_page(width=SW, height=SH)
        page.insert_font(fontname="MB", fontbuffer=font_buf)
        for i in range(used):
            x, y = slots[i]
            mx = SW - x - tw  # chapdan-o'ngga aylantirish: ustun ko'zguda, qator o'zgarmaydi
            page.show_pdf_page(fitz.Rect(mx, y, mx + tw, y + th), src, 0, clip=IV.BACK)
            if a.duplex_marks:
                col = 1 - (i % 2)
                lx = mx - 14 * MM if col == 0 else mx + tw + 6 * MM
                page.insert_text((lx, y + th / 2), f"{i + 1}", fontname="MB", fontsize=22, color=K)
        if a.duplex_marks:
            page.insert_text((SW - ox - 60 * MM, 6 * MM), "ORQA TOMON — YUQORI CHETI", fontname="MB", fontsize=9, color=K)
        crop_marks(page)
        page.set_trimbox(page.rect)

    def finish(doc, path, title):
        doc.subset_fonts()
        tmp = path + ".tmp.pdf"
        doc.save(tmp, garbage=3, deflate=True)
        doc.close()
        import pikepdf
        with pikepdf.open(tmp) as pdf:
            icc = pdf.make_stream(open(a.icc, "rb").read())
            icc.N = 4
            icc.Alternate = pikepdf.Name.DeviceCMYK
            pdf.Root.OutputIntents = pikepdf.Array([pikepdf.Dictionary(
                Type=pikepdf.Name.OutputIntent, S=pikepdf.Name.GTS_PDFX, OutputConditionIdentifier="FOGRA39",
                RegistryName="http://www.color.org", OutputCondition="Offset, coated paper (ISO 12647-2:2004)",
                Info="ISO Coated v2 (ECI)", DestOutputProfile=icc)])
            pdf.docinfo["/Title"] = title
            pdf.docinfo["/Subject"] = f"DUSEL Yulduzli Kecha; master sha256 {msha}"
            pdf.save(path)
        os.remove(tmp)
        print("OK", path)

    if a.combined:
        doc = fitz.open()
        for s in sheets:
            used = front_page(doc, s)
            back_page(doc, used)
        finish(doc, a.combined, "DUSEL — proof (old + orqa)")
    if a.front:
        doc = fitz.open()
        used_list = []
        for s in sheets:
            used_list.append(front_page(doc, s))
        finish(doc, a.front, "DUSEL — OLD tomon (FRONT)")
        json.dump(dict(master_sha256=msha, sheets=sheets[0:1] + sheets[-1:], total_sheets=len(sheets), used=used_list),
                  open(a.front + ".json", "w"))
    if a.back:
        doc = fitz.open()
        for s in sheets:
            back_page(doc, len(rows[(s - 1) * 6: s * 6]))
        finish(doc, a.back, "DUSEL — ORQA tomon (BACK)")


if __name__ == "__main__":
    main()
