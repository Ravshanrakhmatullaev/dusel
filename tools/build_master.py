#!/usr/bin/env python3
"""
DUSEL_MASTER_11222 — yagona bilet/joy bazasi (bosma va sayt uchun bitta manba).

Qoidalar (mijoz tasdiqlagan):
  * Faqat Блитчеры, 2-этаж, 4-этаж. "балкон 3-vip" (VIP/lojalar) to'liq chiqarib tashlanadi.
  * Tartib: SEKTOR (raqami bo'yicha 201→216, 401→416) → QATOR (o'sish) → JOY (o'sish).
  * Har bir qatorda joy raqami 1 dan boshlanadi, soni Excel'dagi "Кол-во мест" ga teng. Ortiqcha joy qo'shilmaydi.
  * Bilet raqamlari 00001 dan ketma-ket.
  * STATUS: ASSIGNED — kamchiliksiz qatorlar; REVIEW_REQUIRED — Excel izohi raqamlashni noaniq qiladigan joylar.
    Ikkalasi ham ketma-ket raqamlash (fizik tekshirilmagan).

Ishlatish: python build_master.py места.xlsx out/
"""
import csv, hashlib, json, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seatlib

BASE_URL = "https://ravshanrakhmatullaev.github.io/dusel/?code="
ZONE = {"блитчеры": "Блитчеры", "2-этаж": "2-этаж", "4-этаж": "4-этаж"}
EXPECTED = {"блитчеры": 1896, "2-этаж": 3519, "4-этаж": 5807}
TOTAL = 11222


def seat_rules(r, all_rows):
    """-> (list of (seat, status), qoida izohi yoki '')"""
    n = r["count"]
    note = r["note"]
    seats = list(range(1, n + 1))
    if n == 0:
        return [], ""
    if r["special"]:
        return [(s, "REVIEW_REQUIRED") for s in seats], (
            f"Maxsus yozuv '{r['special']}': {n} joy, o'rindiqlarda raqam yo'q ({note or 'izohsiz'}). "
            f"Qator belgisi Excel'dagi 'Ряд' ustunidan ({r['row']}). Joylar 1–{n} ketma-ket (mijoz tasdiqlagan qoida).")
    if "последние 4 места без цифр" in note.lower():
        return [(s, "ASSIGNED" if s <= n - 4 else "REVIEW_REQUIRED") for s in seats], (
            f"Izoh: '{note}'. 1–{n - 4} joylar raqamli (ASSIGNED); oxirgi 4 joy ({n - 3}–{n}) raqamsiz — REVIEW_REQUIRED.")
    if note:
        extra = ""
        if "можно добавить" in note.lower():
            extra = " Izohdagi qo'shimcha joylar Excel sonida yo'q — QO'SHILMADI."
        if r["note_range"]:
            extra += f" Izoh birlashtirilgan katakda ({r['note_range']}) — shu oraliqdagi barcha qatorlarga tegishli deb olindi."
        return [(s, "REVIEW_REQUIRED") for s in seats], f"Izoh: '{note}'. Joylar 1–{n} ketma-ket, fizik raqamlash tekshirilishi kerak.{extra}"
    # "с 16го нет номеров" (2-этаж A202, 16-qator) — "16-dan boshlab" talqini: 17–18 qatorlar ham tekshiruvga
    if r["sheet"] == "2-этаж" and r["sector"] == "A202" and r["row"] in (17, 18):
        return [(s, "REVIEW_REQUIRED") for s in seats], (
            "16-qatordagi izoh 'с 16го нет номеров' ('16-dan boshlab raqam yo'q') ehtiyotkorlik uchun 17–18 qatorlarga ham "
            f"tatbiq etildi. Joylar 1–{n} ketma-ket.")
    return [(s, "ASSIGNED") for s in seats], ""


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    wb_sha = hashlib.sha256(open(src, "rb").read()).hexdigest()
    P = seatlib.parse(src)
    rows = [r for r in P["rows"] if r["sheet"] in ZONE]
    # tekshiruv: sektor+qator noyob
    rk = Counter((r["sector"], r["row"]) for r in rows)
    dup_rows = [k for k, v in rk.items() if v > 1]
    assert not dup_rows, dup_rows
    rows.sort(key=lambda r: (r["sector_num"], r["row"]))
    master, exceptions = [], []
    t = 0
    for r in rows:
        seats, rule = seat_rules(r, rows)
        if rule or r["count"] == 0 and (r["count_raw"] not in (None,)):
            pass
        if rule:
            exceptions.append(dict(ZONE=ZONE[r["sheet"]], SECTOR=r["sector"], SECTOR_ORIGINAL=r["sector_original"],
                                   ROW=r["row"], SEATS=r["count"], EXCEL_VALUE=str(r["count_raw"]), EXCEL_NOTE=r["note"],
                                   REVIEW_SEATS=sum(1 for _, st in seats if st == "REVIEW_REQUIRED"),
                                   ASSUMPTION=rule, SOURCE=r["cell"]))
        for s, st in seats:
            t += 1
            code = str(t).zfill(5)
            master.append(dict(TICKET_NUMBER=code, SECTOR=r["sector"], ROW=str(r["row"]), SEAT=str(s),
                               ZONE=ZONE[r["sheet"]], STATUS=st, QR_URL=BASE_URL + code,
                               SECTOR_ORIGINAL=r["sector_original"], SOURCE_CELL=r["cell"],
                               EXCEL_NOTE=r["note"] if st == "REVIEW_REQUIRED" else ""))
    zero_rows = [dict(ZONE=ZONE[r["sheet"]], SECTOR=r["sector"], ROW=r["row"], EXCEL_VALUE=str(r["count_raw"]), SOURCE=r["cell"])
                 for r in rows if r["count"] == 0]
    # yarashtirish
    per_zone = Counter(m["ZONE"] for m in master)
    recon = {ZONE[k]: dict(excel_floor_total=P["floor_stated"].get(k), expected=v, master=per_zone[ZONE[k]],
                           ok=P["floor_stated"].get(k) == v == per_zone[ZONE[k]]) for k, v in EXPECTED.items()}
    sec_bad = [s for s in P["sectors"] if s["sheet"] in ZONE and s["stated"] is not None and s["stated"] != s["computed"]]
    assert len(master) == TOTAL, len(master)
    assert all(v["ok"] for v in recon.values()), recon
    assert not sec_bad, sec_bad
    assert len({(m["SECTOR"], m["ROW"], m["SEAT"]) for m in master}) == TOTAL

    F = ["TICKET_NUMBER", "SECTOR", "ROW", "SEAT", "ZONE", "STATUS", "QR_URL", "SECTOR_ORIGINAL", "SOURCE_CELL", "EXCEL_NOTE"]
    with open(os.path.join(out, "DUSEL_MASTER_11222.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=F)
        w.writeheader()
        w.writerows(master)
    master_sha = hashlib.sha256(open(os.path.join(out, "DUSEL_MASTER_11222.csv"), "rb").read()).hexdigest()

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook()
    hf, hfill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="C8000E")
    rv_fill = PatternFill("solid", fgColor="FFF2CC")

    def sheet(title, data, fields, widths, first=False, text_cols=()):
        ws = wb.active if first else wb.create_sheet(title)
        ws.title = title
        ws.append(fields)
        for d in data:
            ws.append([d.get(k) for k in fields])
        for c in ws[1]:
            c.font, c.fill, c.alignment = hf, hfill, Alignment(horizontal="center")
        for col in text_cols:
            for c in ws[col][1:]:
                c.number_format = "@"
        for i, wd in enumerate(widths):
            ws.column_dimensions[chr(65 + i)].width = wd
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        return ws

    ws = sheet("MASTER", master, F, [14, 9, 6, 6, 11, 18, 56, 14, 26, 40], first=True, text_cols=("A", "B", "C", "D"))
    for row in ws.iter_rows(min_row=2):
        if row[5].value == "REVIEW_REQUIRED":
            row[5].fill = rv_fill
    sheet("ISTISNOLAR", exceptions, ["ZONE", "SECTOR", "SECTOR_ORIGINAL", "ROW", "SEATS", "EXCEL_VALUE", "EXCEL_NOTE",
                                     "REVIEW_SEATS", "ASSUMPTION", "SOURCE"], [11, 9, 12, 6, 7, 14, 40, 9, 90, 26])
    sheet("BO'SH QATORLAR", zero_rows, ["ZONE", "SECTOR", "ROW", "EXCEL_VALUE", "SOURCE"], [11, 9, 6, 22, 26])
    secsum = []
    for s in sorted({(m["SECTOR"]) for m in master}, key=lambda x: int(x[1:])):
        ms = [m for m in master if m["SECTOR"] == s]
        secsum.append(dict(SECTOR=s, ZONES=", ".join(sorted({m["ZONE"] for m in ms})), FIRST=ms[0]["TICKET_NUMBER"],
                           LAST=ms[-1]["TICKET_NUMBER"], SEATS=len(ms), ROWS=len({m["ROW"] for m in ms}),
                           REVIEW=sum(1 for m in ms if m["STATUS"] == "REVIEW_REQUIRED")))
    sheet("SEKTORLAR", secsum, ["SECTOR", "ZONES", "FIRST", "LAST", "SEATS", "ROWS", "REVIEW"], [9, 22, 9, 9, 8, 7, 9])
    summ = [dict(K="Manba workbook SHA-256", V=wb_sha), dict(K="Master CSV SHA-256", V=master_sha),
            dict(K="Jami bilet", V=len(master)), dict(K="ASSIGNED", V=sum(m["STATUS"] == "ASSIGNED" for m in master)),
            dict(K="REVIEW_REQUIRED", V=sum(m["STATUS"] == "REVIEW_REQUIRED" for m in master)),
            dict(K="VIP/loja (chiqarib tashlandi)", V=P["vip_seats"])] + \
           [dict(K=f"{z}: Excel / master", V=f"{v['excel_floor_total']} / {v['master']}") for z, v in recon.items()]
    sheet("XULOSA", summ, ["K", "V"], [34, 70])
    wb.save(os.path.join(out, "DUSEL_MASTER_11222.xlsx"))

    with open(os.path.join(out, "seating_exceptions.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(exceptions[0].keys()))
        w.writeheader()
        w.writerows(exceptions)
    json.dump(dict(workbook_sha256=wb_sha, master_sha256=master_sha, total=len(master),
                   assigned=sum(m["STATUS"] == "ASSIGNED" for m in master),
                   review=sum(m["STATUS"] == "REVIEW_REQUIRED" for m in master), vip_excluded=P["vip_seats"],
                   reconciliation=recon, exception_rows=len(exceptions), zero_rows=len(zero_rows),
                   sector_sections=sum(1 for s in P["sectors"] if s["sheet"] in ZONE),
                   row_records=len(rows), sheets=P["sheets"]),
              open(os.path.join(out, "master_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(json.load(open(os.path.join(out, "master_summary.json"))), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
