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
    ap.add_argument("--back-single", help="BITTA sahifa: 6 ta bir xil orqa (har list uchun takrorlanadi)")
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
    elif a.back_single:
        sheets = []
    else:
        sys.exit("--all, --sheets yoki --back-single kerak")

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

    # ---- V5: o'zgaruvchan ma'lumot maydoni (asl oq quti) 4 ustunga qayta chiziladi: ZONA / QAVAT | SEKTOR | QATOR | JOY
    # Asl quti yo'li (PDF koord.) aynan takrorlanadi va asl rang bilan bo'yaladi; asl 3 yorliq va 2 chiziq shu quti ostida qoladi.
    BOX_PDF = [("m", (37.4769, 389.8069)), ("l", (189.2361, 389.8069)),
               ("c", (190.3470, 389.8069), (191.2555, 388.8984), (191.2555, 387.7875)), ("l", (191.2555, 369.3915)),
               ("c", (191.2555, 368.2806), (190.3470, 367.3721), (189.2361, 367.3721)), ("l", (37.4769, 367.3721)),
               ("c", (36.3660, 367.3721), (35.4574, 368.2806), (35.4574, 369.3915)), ("l", (35.4574, 387.7875)),
               ("c", (35.4574, 388.8984), (36.3660, 389.8069), (37.4769, 389.8069))]
    BOX_FILL = (0.0078, 0.0039, 0.0157, 0.0)        # asl quti rangi (CS17, ISO Coated v2)
    PAGE_H = 615.8698                                # asl sahifa: fitz_y = 615.8698 - pdf_y, fitz_x = pdf_x + 1
    LAB = ("ZONA / QAVAT", "SEKTOR №", "QATOR №", "JOY №")
    LAB_PT, VAL_PT = 6.0, 9.0
    COLW = (52.5, 39.7, 37.0, 26.6)                  # jami 155.8 pt = asl quti eni
    X0 = IV.SEAT_BOX.x0
    edges = [X0]
    for w_ in COLW:
        edges.append(edges[-1] + w_)
    LAB_BASE = IV.SEAT_LABEL_BASELINE                # asl yorliqlar tayanch chizig'i
    VAL_BASE = (IV.SEAT_LABEL_BASELINE + IV.SEAT_BOX.y1) / 2 + 0.35 * VAL_PT
    DIV_Y = (228.57, 245.99)                         # asl ajratuvchi chiziqlar balandligi
    globals()["V5_INFO"] = dict(edges=edges, lab=LAB, lab_pt=LAB_PT, val_pt=VAL_PT, lab_base=LAB_BASE, val_base=VAL_BASE)

    def P(pt, dx, dy):
        return fitz.Point(pt[0] + 1 + dx, PAGE_H - pt[1] + dy)

    def info_box(page, dx, dy, vals):
        sh = page.new_shape()
        cur = None
        for seg in BOX_PDF:
            if seg[0] == "m":
                cur = P(seg[1], dx, dy)
            elif seg[0] == "l":
                nxt = P(seg[1], dx, dy)
                sh.draw_line(cur, nxt)
                cur = nxt
            else:
                c1, c2, nxt = P(seg[1], dx, dy), P(seg[2], dx, dy), P(seg[3], dx, dy)
                sh.draw_bezier(cur, c1, c2, nxt)
                cur = nxt
        sh.finish(fill=BOX_FILL, color=None, width=0, even_odd=True, closePath=True)
        for x in edges[1:-1]:
            sh.draw_line((x + dx, DIV_Y[0] + dy), (x + dx, DIV_Y[1] + dy))
        sh.finish(color=K, width=0.5669, closePath=False)
        sh.commit()
        for i_, (lab, v) in enumerate(zip(LAB, vals)):
            cx = (edges[i_] + edges[i_ + 1]) / 2 + dx
            mw = COLW[i_] - 4
            text_center(page, cx, LAB_BASE + dy, lab, LAB_PT, mw)
            text_center(page, cx, VAL_BASE + dy, v, VAL_PT, mw)

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
            info_box(page, dx, dy, (r["ZONA_QAVAT"], r["SECTOR"], r["ROW"], r["SEAT"]))
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

    if a.back_single:
        doc = fitz.open()
        back_page(doc, 6)
        finish(doc, a.back_single, "DUSEL — ORQA tomon, 6-up, bitta sahifa")
        sheets = sheets or [1]
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
