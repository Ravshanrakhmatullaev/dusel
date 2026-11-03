#!/usr/bin/env python3
"""
DUSEL GAL — vaucherlarni 450×320 mm bosma varaqqa joylash (impozitsiya).

QR va raqamlar o'zgarmaydi: master CSV (000001–001000) va QR URL'lari gal_build.py dagidek o'qiladi.

Kirish:
  * asl dizayn (Vaucher(1).png) — config["artwork"]
  * config (gal_layout.json): vaucher o'lchami (mm), namuna raqam/QR ni yopish to'rtburchaklari (piksel),
    QR joyi va raqam joyi (asl rasm pikselida), varaq/oraliq/bleed parametrlari.

Chiqish:
  * DUSEL_GAL_1000_PRINT_450x320.pdf  — 1000 ta vaucher ketma-ket
  * DUSEL_GAL_6UP_TEST.pdf            — birinchi varaq (000001–000006 yoki N-up)
  * *_layout.json                     — har vaucherning varaqdagi aniq joyi (QA uchun)

Rang: rasm sRGB → ISO Coated v2 (ECI) [FOGRA39], Relative Colorimetric + BPC; QR va raqam vektor, QR = K100,
kesish belgilari = Registration. OutputIntent: ISO Coated v2 (ECI). PDF/X deb da'vo qilinmaydi.

Ishlatish:
  python gal_impose.py --config gal_layout.json --options      # varaqqa sig'ish variantlari jadvali
  python gal_impose.py --config gal_layout.json --step proof|print|all
"""
import argparse, csv, io, json, math, os, sys
import pymupdf as fitz
import segno
from PIL import Image, ImageCms

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MM = 72 / 25.4
K100, REG, WHITE = (0, 0, 0, 1), (1, 1, 1, 1), (0, 0, 0, 0)
ICC_RGB = os.path.join(HERE, "icc", "sRGB_from_source.icc")
ICC_CMYK = os.path.join(HERE, "icc", "ISOcoated_v2_eci_from_source.icc")
sys.path.insert(0, HERE)
import gal_build  # noqa: E402  — URL va QR parametrlari aynan shu yerdan (qayta yaratilmaydi, bir xil algoritm)


# ---------------------------------------------------------------- joylash variantlari
def layout_options(cfg, aspect):
    SW, SH = cfg["sheet_mm"]
    m, g = cfg["margin_min_mm"], cfg["gap_mm"]
    UW, UH = SW - 2 * m, SH - 2 * m
    res = []
    for rot in (False, True):
        a = (1 / aspect) if rot else aspect           # varaqdagi eni/bo'yi nisbati
        for c in range(1, 9):
            for r in range(1, 9):
                w = min((UW - (c - 1) * g) / c, a * (UH - (r - 1) * g) / r)
                if w <= 0:
                    continue
                h = w / a
                vw, vh = (h, w) if rot else (w, h)     # vaucherning o'z (dizayn) eni/bo'yi
                res.append(dict(cols=c, rows=r, n=c * r, rotated=rot, voucher_w=round(vw, 2), voucher_h=round(vh, 2)))
    best = {}
    for o in res:
        k = (o["n"], o["rotated"])
        if k not in best or o["voucher_w"] > best[k]["voucher_w"]:
            best[k] = o
    return sorted(best.values(), key=lambda o: (-o["n"], -o["voucher_w"]))


def grid(cfg):
    """Tanlangan joylash: har slotning trim to'rtburchagi (mm, varaq chap-yuqori burchagidan)."""
    SW, SH = cfg["sheet_mm"]
    vw, vh = cfg["voucher_mm"]
    L = cfg["layout"]
    c, r, rot, g = L["cols"], L["rows"], L.get("rotated", False), cfg["gap_mm"]
    cw, ch = (vh, vw) if rot else (vw, vh)
    GW, GH = c * cw + (c - 1) * g, r * ch + (r - 1) * g
    x0, y0 = (SW - GW) / 2, (SH - GH) / 2
    assert x0 >= cfg["margin_min_mm"] - 1e-6 and y0 >= cfg["margin_min_mm"] - 1e-6, ("sig'maydi", x0, y0)
    slots = [(x0 + i * (cw + g), y0 + j * (ch + g), cw, ch) for j in range(r) for i in range(c)]
    return slots, (x0, y0, GW, GH), rot


# ---------------------------------------------------------------- asl dizaynni tayyorlash
def prepare_base(cfg, out_dir):
    """Namuna raqam/QR yopiladi, chetlariga sintetik bleed qo'shiladi, sRGB → ISO Coated v2 CMYK."""
    im = Image.open(os.path.join(ROOT, cfg["artwork"]))
    icc = im.info.get("icc_profile")
    im = im.convert("RGB")
    W, H = im.size
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    for e in cfg.get("erase", []):
        x0, y0, x1, y1, col = e
        d.rectangle([x0, y0, x1, y1], fill=col)
    ppm = W / cfg["voucher_mm"][0]
    b = int(round(cfg["bleed_mm"] * ppm))
    if b:
        big = Image.new("RGB", (W + 2 * b, H + 2 * b))
        big.paste(im, (b, b))
        # chekka piksellarni cho'zish (dizaynda bleed yo'q — hisobotda qayd etiladi)
        big.paste(im.crop((0, 0, W, 1)).resize((W, b)), (b, 0))
        big.paste(im.crop((0, H - 1, W, H)).resize((W, b)), (b, H + b))
        big.paste(big.crop((b, 0, b + 1, H + 2 * b)).resize((b, H + 2 * b)), (0, 0))
        big.paste(big.crop((W + b - 1, 0, W + b, H + 2 * b)).resize((b, H + 2 * b)), (W + b, 0))
        im = big
    src = ImageCms.ImageCmsProfile(io.BytesIO(icc)) if icc else ImageCms.ImageCmsProfile(ICC_RGB)
    dst = ImageCms.ImageCmsProfile(ICC_CMYK)
    xf = ImageCms.buildTransform(src, dst, "RGB", "CMYK", renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
                                 flags=ImageCms.Flags.BLACKPOINTCOMPENSATION)
    cm = ImageCms.applyTransform(im, xf)
    p = os.path.join(out_dir, "gal_base_cmyk.tif")
    cm.save(p, compression="tiff_lzw", dpi=(ppm * 25.4, ppm * 25.4))
    eff_dpi = ppm * 25.4
    return p, cm.size, b, ppm, eff_dpi, ("embedded" if icc else "sRGB (taxmin)")


# ---------------------------------------------------------------- chizish
def qr_paths(page, url, rect):
    m = gal_build.qr_matrix(url)          # 4 modul quiet zone bilan
    n = len(m)
    s = rect.width / n
    sh = page.new_shape()
    sh.draw_rect(rect)
    sh.finish(fill=WHITE, color=None, width=0)   # oq fon + quiet zone (CMYK 0)
    for (x, y, l) in gal_build.runs(m):
        sh.draw_rect(fitz.Rect(rect.x0 + x * s, rect.y0 + y * s, rect.x0 + (x + l) * s, rect.y0 + (y + 1) * s))
    sh.finish(fill=K100, color=None, width=0, closePath=True)
    sh.commit()
    return n


def crop_marks(page, xs, ys, area, cfg):
    """Tashqi hoshiyada har bir kesish chizig'i uchun belgilar (Registration, 0.25 pt)."""
    off, ln = cfg["mark_offset_mm"] * MM, cfg["mark_len_mm"] * MM
    x0, y0, x1, y1 = area
    sh = page.new_shape()
    for x in xs:
        sh.draw_line((x, y0 - off), (x, y0 - off - ln)); sh.draw_line((x, y1 + off), (x, y1 + off + ln))
    for y in ys:
        sh.draw_line((x0 - off, y), (x0 - off - ln, y)); sh.draw_line((x1 + off, y), (x1 + off + ln, y))
    sh.finish(color=REG, width=0.25, fill=None, closePath=False)
    sh.commit()


def voucher_doc(cfg, rows, base):
    """Har bir vaucher alohida sahifa (bleed bilan): asl dizayn + QR (vektor, K100) + seriya raqami (vektor matn)."""
    base_path, (bw, bh), bpx, ppm, dpi, _ = base
    vw, vh = cfg["voucher_mm"]
    bl = cfg["bleed_mm"]
    S = cfg["serial"]
    font = os.path.join(HERE, S["font"])
    fnt = fitz.Font(fontfile=font)
    size = S["size_px"] / ppm * MM
    doc = fitz.open()
    xref = 0
    meta = []
    for r in rows:
        pg = doc.new_page(width=(vw + 2 * bl) * MM, height=(vh + 2 * bl) * MM)
        xref = pg.insert_image(pg.rect, filename=None if xref else base_path, xref=xref, keep_proportion=False)
        T = lambda px, py: fitz.Point((bl + px / ppm) * MM, (bl + py / ppm) * MM)   # dizayn pikseli -> sahifa
        qx0, qy0, qx1, qy1 = cfg["qr_box"]
        side = min(qx1 - qx0, qy1 - qy0)
        cx, cy = (qx0 + qx1) / 2, (qy0 + qy1) / 2
        qrect = fitz.Rect(T(cx - side / 2, cy - side / 2), T(cx + side / 2, cy + side / 2))
        qr_paths(pg, r["QR_URL"], qrect)
        pg.insert_font(fontname="SER", fontfile=font)
        tw = fnt.text_length(r["VOUCHER_NUMBER"], fontsize=size)
        fx0, _, fx1, _ = S["box"]
        bx = (fx0 + fx1) / 2 if S.get("align") == "center" else fx0
        p0 = T(bx, S["baseline"])
        if S.get("align") == "center":
            p0.x -= tw / 2
        pg.insert_text(p0, r["VOUCHER_NUMBER"], fontname="SER", fontsize=size, color=tuple(S["color_cmyk"]))
        meta.append(dict(qr=qrect, num=fitz.Rect(p0.x, p0.y - size * 0.72, p0.x + tw, p0.y)))
    return doc, meta


def impose(cfg, rows, out_pdf, base, label):
    slots, (gx, gy, GW, GH), rot = grid(cfg)
    SW, SH = cfg["sheet_mm"]
    vw, vh = cfg["voucher_mm"]
    bl = cfg["bleed_mm"]
    vdoc, meta = voucher_doc(cfg, rows, base)
    doc = fitz.open()
    lay = []
    per = len(slots)
    sheets = math.ceil(len(rows) / per)
    font = os.path.join(HERE, cfg["serial"]["font"])
    for si in range(sheets):
        page = doc.new_page(width=SW * MM, height=SH * MM)
        chunk = list(range(si * per, min(len(rows), (si + 1) * per)))
        for k, i in enumerate(chunk):
            sx, sy, cw, ch = slots[k]
            trim = fitz.Rect(sx * MM, sy * MM, (sx + cw) * MM, (sy + ch) * MM)
            bleed = trim + (-bl * MM, -bl * MM, bl * MM, bl * MM)
            page.show_pdf_page(bleed, vdoc, i, rotate=90 if rot else 0, keep_proportion=False)
            # vaucher ichidagi to'rtburchakni varaqqa o'tkazish (QA uchun)
            def M(R):
                if not rot:
                    return R + (bleed.x0, bleed.y0, bleed.x0, bleed.y0)
                vh_pt = (vh + 2 * bl) * MM
                return fitz.Rect(bleed.x0 + R.y0, bleed.y0 + (bleed.height - R.x1), bleed.x0 + R.y1, bleed.y0 + (bleed.height - R.x0))
            lay.append(dict(sheet=si + 1, slot=k + 1, number=rows[i]["VOUCHER_NUMBER"], url=rows[i]["QR_URL"],
                            trim=[round(v, 3) for v in trim], bleed=[round(v, 3) for v in bleed],
                            qr=[round(v, 3) for v in M(meta[i]["qr"])], num=[round(v, 3) for v in M(meta[i]["num"])]))
        xs = sorted({round(s[0] * MM, 3) for s in slots} | {round((s[0] + s[2]) * MM, 3) for s in slots})
        ys = sorted({round(s[1] * MM, 3) for s in slots} | {round((s[1] + s[3]) * MM, 3) for s in slots})
        area = ((gx - bl) * MM, (gy - bl) * MM, (gx + GW + bl) * MM, (gy + GH + bl) * MM)
        crop_marks(page, xs, ys, area, cfg)
        page.insert_font(fontname="INF", fontfile=font)
        a_, b_ = rows[chunk[0]]["VOUCHER_NUMBER"], rows[chunk[-1]]["VOUCHER_NUMBER"]
        info = f"DUSEL GAL · {label} · varaq {si + 1}/{sheets} · {a_}–{b_} · {len(chunk)} dona · vaucher {vw:g}×{vh:g} mm · ISO Coated v2 (ECI)"
        page.insert_text(fitz.Point((gx - bl) * MM, SH * MM - 3 * MM), info, fontname="INF", fontsize=5.5, color=K100)
    doc.subset_fonts()
    doc.save(out_pdf, garbage=3, deflate=True)
    add_output_intent(out_pdf)
    with open(out_pdf.replace(".pdf", "_layout.json"), "w") as f:
        json.dump(lay, f, ensure_ascii=False)
    return sheets, lay


def add_output_intent(path):
    import pikepdf
    pdf = pikepdf.open(path, allow_overwriting_input=True)
    icc = pdf.make_stream(open(ICC_CMYK, "rb").read())
    icc.N = 4
    pdf.Root.OutputIntents = pikepdf.Array([pikepdf.Dictionary(Type=pikepdf.Name.OutputIntent, S=pikepdf.Name.GTS_PDFX,
        OutputConditionIdentifier="FOGRA39", RegistryName="http://www.color.org", Info="ISO Coated v2 (ECI)", DestOutputProfile=icc)])
    pdf.docinfo["/Title"] = "DUSEL GAL vaucherlar — bosma"
    pdf.docinfo["/Creator"] = "gal_impose.py"
    pdf.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "gal_layout.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out"))
    ap.add_argument("--step", default="all", choices=["proof", "print", "all"])
    ap.add_argument("--options", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    if a.options:
        W, H = Image.open(os.path.join(ROOT, cfg["artwork"])).size
        print(f"artwork {W}×{H} px, nisbat {W / H:.4f}")
        for o in layout_options(cfg, W / H)[:14]:
            print(o)
        return
    with open(os.path.join(a.out, "DUSEL_GAL_MASTER.csv"), encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1000 and rows[0]["VOUCHER_NUMBER"] == "000001" and rows[-1]["VOUCHER_NUMBER"] == "001000"
    base = prepare_base(cfg, a.out)
    print("base", base[1], "bleed px", base[2], f"~{base[4]:.0f} dpi", base[5])
    per = cfg["layout"]["cols"] * cfg["layout"]["rows"]
    if a.step in ("proof", "all"):
        n, _ = impose(cfg, rows[:per], os.path.join(a.out, f"DUSEL_GAL_{per}UP_TEST.pdf"), base, "PROOF")
        print("proof", n)
    if a.step in ("print", "all"):
        n, _ = impose(cfg, rows, os.path.join(a.out, "DUSEL_GAL_1000_PRINT_450x320.pdf"), base, "PRINT")
        print("print", n)


if __name__ == "__main__":
    main()
