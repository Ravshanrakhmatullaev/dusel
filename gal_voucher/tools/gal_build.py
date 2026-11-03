#!/usr/bin/env python3
"""
DUSEL — GAL "ISHONCHLI HAMKORLAR AKSIYASI" vaucherlari (000001–001000): master va QR.

QR URL (alohida yo'l, biletlar va kuponlardan mustaqil):
    https://dusel.pages.dev/gal?code=000001 … 001000
Boshqa tizimlar (o'zgarmaydi):
    bilet   https://dusel.pages.dev/?code=00001 … 11222
    kupon   https://dusel.pages.dev/coupon?type=gold|silver&code=0001 …

QR: standart QR Model 2, versiya 4 (33×33 modul), xato tuzatish Q (~25%), byte rejimi,
4 modul oq "quiet zone", logotip yo'q. Barcha 1000 URL bir xil uzunlikda — hammasi bir xil versiya.

Ishlatish:
    python gal_build.py --out out --step master|qr|all
"""
import argparse, csv, os, zipfile
import segno
from PIL import Image

BASE = "https://dusel.pages.dev/gal?code={c}"
COUNT = 1000
TYPE = "GAL"
QR_VERSION, QR_ERROR, QR_BORDER = 4, "q", 4
QR_SVG_MM = 22.0            # SVG fizik o'lchami (quiet zone bilan); bosmada masshtablash mumkin, min. 18 mm tavsiya
PNG_SCALE = 30              # 41 modul × 30 = 1230 px  (22 mm @ 1420 dpi; 600 dpi da 52 mm gacha)
COLUMNS = ["VOUCHER_TYPE", "VOUCHER_NUMBER", "QR_URL", "STATUS", "ISSUE_DATE", "RECIPIENT_NAME"]


def number(i):
    return f"{i:06d}"


def url(code):
    assert len(code) == 6 and code.isdigit() and 1 <= int(code) <= COUNT, code
    return BASE.format(c=code)


def rows():
    return [dict(VOUCHER_TYPE=TYPE, VOUCHER_NUMBER=number(i), QR_URL=url(number(i)),
                 STATUS="NOT_ISSUED", ISSUE_DATE="", RECIPIENT_NAME="") for i in range(1, COUNT + 1)]


def qr_matrix(u):
    q = segno.make(u, version=QR_VERSION, error=QR_ERROR, mode="byte", boost_error=False, micro=False)
    return [list(r) for r in q.matrix_iter(scale=1, border=QR_BORDER)]


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


def svg(m):
    n = len(m)
    path = "".join(f"M{x} {y}h{l}v1h-{l}z" for (x, y, l) in runs(m))
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="{QR_SVG_MM}mm" '
            f'height="{QR_SVG_MM}mm" viewBox="0 0 {n} {n}" shape-rendering="crispEdges"><rect width="{n}" height="{n}" '
            f'fill="#FFFFFF"/><path fill="#000000" d="{path}"/></svg>\n')


def master(out, data):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    with open(os.path.join(out, "DUSEL_GAL_MASTER.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(data)
    wb = Workbook()
    ws = wb.active
    ws.title = "GAL"
    ws.append(COLUMNS)
    for r in data:
        ws.append([r[c] if r[c] != "" else None for c in COLUMNS])
    for col in "BEF":
        for c in ws[col]:
            c.number_format = "@"
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="B0101C")
        c.alignment = Alignment(horizontal="center")
    for col, wdt in zip("ABCDEF", (14, 17, 46, 13, 13, 30)):
        ws.column_dimensions[col].width = wdt
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:F{len(data) + 1}"
    wb.save(os.path.join(out, "DUSEL_GAL_MASTER.xlsx"))


def qr_files(out, data):
    d = os.path.join(out, "qr_gal")
    os.makedirs(os.path.join(d, "SVG"), exist_ok=True)
    os.makedirs(os.path.join(d, "PNG"), exist_ok=True)
    for r in data:
        m = qr_matrix(r["QR_URL"])
        name = f"GAL_{r['VOUCHER_NUMBER']}"
        with open(os.path.join(d, "SVG", name + ".svg"), "w") as f:
            f.write(svg(m))
        n = len(m)
        img = Image.new("1", (n, n), 1)
        px = img.load()
        for y, row in enumerate(m):
            for x, v in enumerate(row):
                if v:
                    px[x, y] = 0
        img.resize((n * PNG_SCALE, n * PNG_SCALE), Image.NEAREST).save(os.path.join(d, "PNG", name + ".png"), dpi=(600, 600), optimize=True)
    with zipfile.ZipFile(os.path.join(out, "DUSEL_GAL_QR_1000.zip"), "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for r in data:
            name = f"GAL_{r['VOUCHER_NUMBER']}"
            z.write(os.path.join(d, "SVG", name + ".svg"), f"SVG/{name}.svg")
            z.write(os.path.join(d, "PNG", name + ".png"), f"PNG/{name}.png")
        z.write(os.path.join(out, "DUSEL_GAL_MASTER.csv"), "DUSEL_GAL_MASTER.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out"))
    ap.add_argument("--step", default="all", choices=["all", "master", "qr"])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    data = rows()
    if a.step in ("all", "master", "qr"):
        master(a.out, data)
    if a.step in ("all", "qr"):
        qr_files(a.out, data)
    print("OK", len(data))


if __name__ == "__main__":
    main()
