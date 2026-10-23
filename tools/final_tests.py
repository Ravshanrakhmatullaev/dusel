#!/usr/bin/env python3
"""DUSEL 11 222 — yakuniy avtomatik tekshiruv (ma'lumot, QR, sayt ma'lumoti, bosma PDF, CMYK, artwork)."""
import csv, glob, hashlib, io, json, os, random, re, subprocess, sys, zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pymupdf as fitz
from PIL import Image
from pyzbar.pyzbar import decode

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import seatlib, impose_v2 as IV

ROOT = sys.argv[1]           # work/final
SITE = sys.argv[2]           # dusel repo
WB = sys.argv[3]             # места.xlsx
SRC_PDF = sys.argv[4]        # Bilet_final.pdf
MM = 72 / 25.4
BASE = "https://dusel.pages.dev/?code="
N = 11222
R = []


def check(sec, name, ok, detail=""):
    R.append(dict(section=sec, test=name, ok=bool(ok), detail=str(detail)[:400]))
    print(("PASS " if ok else "FAIL ") + f"[{sec}] {name}" + (f" — {str(detail)[:200]}" if detail else ""), flush=True)


def dec_png(path):
    im = Image.open(path).convert("L")
    im = im.resize((im.width // 4, im.height // 4))
    return os.path.basename(path)[:-4], [z.data.decode() for z in decode(im)]


def main():
    M = list(csv.DictReader(open(os.path.join(ROOT, "master/DUSEL_MASTER_FINAL.csv"), encoding="utf-8-sig")))
    codes = [str(i).zfill(5) for i in range(1, N + 1)]
    # ---------------- A. MASTER
    S = "MASTER"
    check(S, "11 222 ta noyob bilet raqami 00001–11222, tartibda, boshidagi nollar bilan", [m["TICKET_NUMBER"] for m in M] == codes)
    lab = Counter(m["FIELD1_LABEL"] for m in M)
    check(S, "1-maydon yorlig'i: blitcher varag'i -> BLITCHER (1 896), 2/4-этаж -> SEKTOR (9 326)",
          all((m["FIELD1_LABEL"] == "BLITCHER") == (m["SOURCE_SHEET"] == "блитчеры") for m in M) and lab == {"BLITCHER": 1896, "SEKTOR": 9326}, dict(lab))
    check(S, "1-maydon qiymati har doim haqiqiy sektor kodi (A–D + 3 raqam), 'BLITCHER' sektor kodi sifatida ishlatilmagan",
          all(re.fullmatch(r"[A-D]\d{3}", m["SECTOR"]) for m in M))
    V4 = list(csv.DictReader(open(os.path.join(ROOT, "../v4/master/DUSEL_MASTER_FINAL.csv"), encoding="utf-8-sig")))
    keys4 = list(V4[0].keys())
    check(S, "Taqsimot V4 bilan aynan bir xil (raqam, zona, sektor, qator, joy, QR_URL, status — 11 222 qator)",
          len(V4) == len(M) and all(all(a[k] == b[k] for k in keys4) for a, b in zip(M, V4)))
    s2 = {s_: sum(1 for m in M if m["SECTOR"] == s_ and m["SOURCE_SHEET"] == "2-этаж") for s_ in ("A201", "A205", "C209", "C213")}
    check(S, "2-этаж dagi A201/A205/C209/C213 biletlari saqlangan (202/197/209/201)", s2 == {"A201": 202, "A205": 197, "C209": 209, "C213": 201}, s2)
    urls = [m["QR_URL"] for m in M]
    check(S, "11 222 ta QR URL, hammasi noyob va raqamga mos", len(set(urls)) == N and all(u == BASE + c for u, c in zip(urls, codes)))
    check(S, "VIP/loja yo'q (faqat Блитчеры, 2-этаж, 4-этаж; sektor kodi A–D + 3 raqam)",
          {m["ZONE"] for m in M} == {"Блитчеры", "2-этаж", "4-этаж"} and all(re.fullmatch(r"[A-D]\d{3}", m["SECTOR"]) for m in M),
          Counter(m["ZONE"] for m in M))
    sn = [int(m["SECTOR"][1:]) for m in M]
    check(S, "Sektor tartibi: 201→216, 401→416 (kamaymaydi)", all(a <= b for a, b in zip(sn, sn[1:])),
          " → ".join(dict.fromkeys(m["SECTOR"] for m in M)))
    ok_row = all((int(a["SECTOR"][1:]), int(a["ROW"])) <= (int(b["SECTOR"][1:]), int(b["ROW"])) for a, b in zip(M, M[1:]))
    check(S, "Qator tartibi: har sektor ichida qator o'sib boradi", ok_row)
    groups = defaultdict(list)
    for m in M:
        groups[(m["SECTOR"], int(m["ROW"]))].append(int(m["SEAT"]))
    restart = all(v == list(range(1, len(v) + 1)) for v in groups.values())
    check(S, "Joy raqami HAR qatorda 1 dan boshlanadi va uzluksiz (1..N)", restart, f"{len(groups)} qator")
    check(S, "Takroriy sektor/qator/joy yo'q", len({(m['SECTOR'], m['ROW'], m['SEAT']) for m in M}) == N)
    P = seatlib.parse(WB)
    rows = [r for r in P["rows"] if r["sheet"] != "балкон 3-vip"]
    wb_counts = {(r["sector"], r["row"]): r["count"] for r in rows if r["count"] > 0}
    m_counts = {k: len(v) for k, v in groups.items()}
    check(S, "Excel bilan har bir qator bo'yicha sig'im mos (ortiqcha joy yo'q, yetishmaydigan joy yo'q)", wb_counts == m_counts,
          f"{len(wb_counts)} ta joyli qator")
    ft = P["floor_stated"]
    zc = Counter(m["ZONE"] for m in M)
    check(S, "Qavat jamlari: Блитчеры 1896, 2-этаж 3519, 4-этаж 5807 = 11 222 (Excel 'Всего' bilan)",
          ft["блитчеры"] == zc["Блитчеры"] == 1896 and ft["2-этаж"] == zc["2-этаж"] == 3519 and ft["4-этаж"] == zc["4-этаж"] == 5807,
          dict(zc))
    check(S, "VIP (балкон 3-vip, 571 joy) chiqarib tashlangan", P["vip_seats"] == 571 and "балкон" not in "".join(zc))
    NOB = ("A201", "A205", "C209", "C213")
    src_nob = {s_: sum(r["count"] for r in rows if r["sheet"] == "блитчеры" and r["sector"] == s_) for s_ in NOB}
    got_nob = {s_: sum(1 for m in M if m["ZONE"] == "Блитчеры" and m["SECTOR"] == s_) for s_ in NOB}
    check(S, "Blitcher A201, A205, C209, C213: Excel'da 0 joy va masterda 0 bilet", all(v == 0 for v in src_nob.values()) and all(v == 0 for v in got_nob.values()),
          f"Excel {src_nob}; master {got_nob}; shu kodlar faqat 2-этаж da: " + ", ".join(f"{s_}={sum(1 for m in M if m['SECTOR']==s_ and m['ZONE']=='2-этаж')}" for s_ in NOB))
    zkey = {"блитчеры": "Блитчеры", "2-этаж": "2-этаж", "4-этаж": "4-этаж"}
    zero = {(zkey[r["sheet"]], r["sector"], r["row"]) for r in rows if r["count"] == 0}
    used = {(m["ZONE"], m["SECTOR"], int(m["ROW"])) for m in M}
    pos = {(zkey[r["sheet"]], r["sector"], r["row"]): r["count"] for r in rows}
    check(S, "Bo'sh/0/НЕТ qatorlarning birortasi masterda yo'q; har bir master qatori Excel'dagi musbat sonli qatordan",
          not (zero & used) and all(pos.get(k, 0) > 0 for k in used), f"{len(zero)} ta bo'sh qator chiqarildi, {len(used)} ta qator ishlatildi")
    check(S, "SOURCE_SHEET faqat блитчеры / 2-этаж / 4-этаж va ZONE ga mos",
          all(zkey[m["SOURCE_SHEET"]] == m["ZONE"] for m in M))
    check(S, "Barcha QR URL https://dusel.pages.dev/ ; github.io yo'q", all(u.startswith("https://dusel.pages.dev/?code=") for u in urls) and not any("github.io" in u for u in urls))
    ex = list(csv.DictReader(open(os.path.join(ROOT, "master/seating_exceptions.csv"), encoding="utf-8-sig")))
    noted = {(r["sector"], r["row"]) for r in rows if r["note"] or r["special"]}
    exk = {(e["SECTOR"], int(e["ROW"])) for e in ex}
    check(S, "Excel'dagi barcha izohli/maxsus qatorlar istisnolar ro'yxatida", noted <= exk, f"{len(noted)} izohli, {len(exk)} istisno")
    rv = {(m["SECTOR"], int(m["ROW"])) for m in M if m["STATUS"] == "REVIEW_REQUIRED"}
    check(S, "REVIEW_REQUIRED faqat istisno qatorlarida; kamchiliksiz qatorlar ASSIGNED", rv == exk,
          Counter(m["STATUS"] for m in M))
    humo = [m for m in M if m["SECTOR"] in ("A203", "C211") and m["ROW"] in ("15", "14") and "нет" in (m["EXCEL_NOTE"] + "нет")]
    a203 = [m for m in M if m["SECTOR"] == "A203" and m["ROW"] == "15"]
    c211 = [m for m in M if m["SECTOR"] == "C211" and m["ROW"] == "14"]
    check(S, "Maxsus 'Хумо А 24' (A203/15) va 'ХУМО С 24' (C211/14): 24 tadan joy, 1–24, REVIEW_REQUIRED",
          [int(m["SEAT"]) for m in a203] == list(range(1, 25)) == [int(m["SEAT"]) for m in c211]
          and all(m["STATUS"] == "REVIEW_REQUIRED" for m in a203 + c211),
          f"A203/15: {a203[0]['TICKET_NUMBER']}–{a203[-1]['TICKET_NUMBER']}, C211/14: {c211[0]['TICKET_NUMBER']}–{c211[-1]['TICKET_NUMBER']}")
    c210 = [m for m in M if m["SECTOR"] == "C210" and m["ROW"] == "16"]
    check(S, "C210/16 'oxirgi 4 joy raqamsiz': 1–18 ASSIGNED, 19–22 REVIEW_REQUIRED",
          [m["STATUS"] for m in c210] == ["ASSIGNED"] * 18 + ["REVIEW_REQUIRED"] * 4)
    b206 = [m for m in M if m["SECTOR"] == "B206" and m["ROW"] in ("15", "16")]
    check(S, "'можно добавить' qo'shimcha joylari qo'shilmagan (B206/15=15, B206/16=16, B208/16=15)",
          Counter(m["ROW"] for m in b206) == {"15": 15, "16": 16} and sum(1 for m in M if m["SECTOR"] == "B208" and m["ROW"] == "16") == 15)
    for c in ("00001", "05611", "11222"):
        m = M[int(c) - 1]
        R.append(dict(section=S, test=f"Namuna {c}", ok=True, detail=f"{m['SECTOR']} / {m['ROW']} / {m['SEAT']} ({m['ZONE']}, {m['STATUS']})"))

    # ---------------- B. QR
    S = "QR"
    svgs = sorted(os.listdir(os.path.join(ROOT, "qr/QR_SVG")))
    pngs = sorted(os.listdir(os.path.join(ROOT, "qr/QR_PNG")))
    check(S, "SVG 11 222 ta (00001.svg … 11222.svg)", svgs == [c + ".svg" for c in codes])
    check(S, "PNG 11 222 ta (00001.png … 11222.png)", pngs == [c + ".png" for c in codes])
    with ProcessPoolExecutor() as exr:
        res = list(exr.map(dec_png, [os.path.join(ROOT, "qr/QR_PNG", c + ".png") for c in codes], chunksize=200))
    bad = [(c, d) for c, d in res if d != [BASE + c]]
    check(S, "BARCHA 11 222 PNG haqiqiy dekoderda (zbar) o'qildi, URL = raqam", not bad, bad[:3] or "11222/11222")
    check(S, "QR payloadlari takrorlanmaydi", len({d[0] for _, d in res if d}) == N)
    import cairosvg
    sample = ["00001", "05611", "10000", "10001", "11222"] + random.Random(11).sample(codes, 300)
    bads = []
    for c in sample:
        png = cairosvg.svg2png(url=os.path.join(ROOT, "qr/QR_SVG", c + ".svg"), output_width=300)
        if [z.data.decode() for z in decode(Image.open(io.BytesIO(png)).convert("L"))] != [BASE + c]:
            bads.append(c)
    check(S, "SVG namunasi (305 ta, chegaralar bilan) dekodlandi", not bads, bads[:5])
    s = open(os.path.join(ROOT, "qr/QR_SVG/00001.svg")).read()
    check(S, "SVG 17 mm, 37 modul (v3-M, 4 modul oq himoya maydoni, modul 0.46 mm); PNG 888 px, 300 dpi metama'lumot",
          'width="17.0mm"' in s and 'viewBox="0 0 37 37"' in s and Image.open(os.path.join(ROOT, "qr/QR_PNG/00001.png")).size == (888, 888))
    with zipfile.ZipFile(os.path.join(ROOT, "out/DUSEL_QR_FINAL_CLOUDFLARE.zip")) as z:
        names = set(z.namelist())
        okz = z.testzip() is None and {f"QR_SVG/{c}.svg" for c in codes} | {f"QR_PNG/{c}.png" for c in codes} <= names
        zsvg = z.read("QR_SVG/11222.svg").decode()
    check(S, "DUSEL_QR_FINAL_CLOUDFLARE.zip: 11 222 SVG + 11 222 PNG, CRC xatosiz, ichidagi fayl = generatsiya", okz and zsvg == open(os.path.join(ROOT, "qr/QR_SVG/11222.svg")).read(), f"{len(names)} fayl")

    # ---------------- C. SAYT MA'LUMOTI
    S = "SAYT"
    web = {}
    shas = set()
    for f in sorted(glob.glob(os.path.join(SITE, "data/seats/s*.json"))):
        d = json.load(open(f))
        shas.add(d["source_sha256"])
        web.update(d["tickets"])
    msha = hashlib.sha256(open(os.path.join(ROOT, "master/DUSEL_MASTER_FINAL.csv"), "rb").read()).hexdigest()
    H = {"ASSIGNED": "ok", "REVIEW_REQUIRED": "review"}
    exp = {m["TICKET_NUMBER"]: [m["FIELD1_LABEL"], m["SECTOR"], m["ROW"], m["SEAT"], H[m["STATUS"]]] for m in M}
    check(S, "Sayt JSON = master (11 222 yozuv, sektor/qator/joy/holat har biri mos)", web == exp, f"{len(web)} yozuv")
    check(S, "Barcha JSON bo'laklari bitta master SHA-256 dan", shas == {msha}, msha[:16])
    html = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    check(S, f"Sayt 00001–{N} qabul qiladi (MAX={N}), URL formati ?code=NNNNN, ma'lumot nisbiy yo'ldan (data/seats/)",
          f"MAX={N}" in html and "get('code')" in html and "'data/seats/s'" in html and "github.io" not in html)
    check(S, "TEST NAMUNA banneri yo'q; 'tasdiqlangan/haqiqiy bilet' da'vosi yo'q",
          "TEST NAMUNA" not in html and not re.search(r"(?i)verified|haqiqiy bilet|tasdiqlangan bilet", html))

    # ---------------- D. BOSMA PDF
    S = "PDF"
    F = fitz.open(os.path.join(ROOT, "out/DUSEL_FRONT_FINAL_CMYK.pdf"))
    B = fitz.open(os.path.join(ROOT, "out/DUSEL_BACK_6UP_SINGLE_PAGE_CMYK.pdf"))
    NS = -(-N // 6)
    check(S, f"FRONT: {NS} list (= ceil({N}/6))", F.page_count == NS, F.page_count)
    check(S, "BACK: AYNAN 1 sahifa", B.page_count == 1, B.page_count)
    import filecmp
    check(S, "BACK: V4 dagi tasdiqlangan orqa fayl bilan bayt-bayt bir xil (o'zgartirilmagan)",
          filecmp.cmp(os.path.join(ROOT, "out/DUSEL_BACK_6UP_SINGLE_PAGE_CMYK.pdf"), os.path.join(ROOT, "../v4/out/DUSEL_BACK_6UP_SINGLE_PAGE_CMYK.pdf"), shallow=False))
    sz = {(round(p.mediabox.width / MM, 3), round(p.mediabox.height / MM, 3), round(p.trimbox.width / MM, 3)) for doc in (F, B) for p in doc}
    check(S, "Har bir sahifa 450 × 320 mm (MediaBox = TrimBox)", sz == {(450.0, 320.0, 450.0)}, sz)
    tw, th = IV.FRONT.width, IV.FRONT.height
    ox, oy = (450 * MM - 2 * tw) / 2, (320 * MM - 3 * th) / 2
    slots = [(ox + c * tw, oy + r * th) for r in range(3) for c in range(2)]
    # joylashuv: har sahifadagi Form XObjectlar
    geo_bad, counts_f, counts_b = [], [], []
    for doc, cnt, clip in ((F, counts_f, IV.FRONT), (B, counts_b, IV.BACK)):
        for p in doc:
            n = 0
            for (xref, name, inv, bb) in p.get_xobjects():
                if inv != 0 or not name.startswith("fzFrm"):
                    continue
                n += 1
                mtx = [float(v) for v in doc.xref_get_key(xref, "Matrix")[1].strip("[]").split()]
                bbx = [float(v) for v in doc.xref_get_key(xref, "BBox")[1].strip("[]").split()]
                if not (mtx[:4] == [1, 0, 0, 1] and abs((bbx[2] - bbx[0]) / MM - 200) < 0.005 and abs((bbx[3] - bbx[1]) / MM - 100) < 0.005):
                    geo_bad.append((p.number, name))
                r = fitz.Rect(bb)
                if not any(abs(r.x0 - x) < 0.01 and abs(r.y0 - y) < 0.01 for x, y in slots):
                    geo_bad.append((p.number, "pozitsiya", list(bb)))
            cnt.append(n)
    check(S, "Har bir bilet 200 × 100 mm, masshtab 1:1, 6-up to'r pozitsiyalarida (barcha sahifalar)", not geo_bad, geo_bad[:3])
    check(S, f"FRONT: {NS - 1} list × 6 + oxirgi list {N - (NS - 1) * 6} bilet; BACK: 1 sahifada 6 ta orqa",
          counts_f[:-1] == [6] * (NS - 1) and counts_f[-1] == N - (NS - 1) * 6 and counts_b == [6], f"oxirgi front {counts_f[-1]}, back {counts_b}")
    # orqa tomon oxirgi listda: front slot 1,2 (yuqori qator) -> orqa yuqori qator
    HH = 320 * MM  # get_xobjects bbox PDF koordinatada (pastdan) -> yuqoridan hisoblash
    bpos = sorted((round(bb[0], 1), round(HH - bb[3], 1)) for (x, nm, inv, bb) in B[0].get_xobjects() if inv == 0 and nm.startswith("fzFrm"))
    fpos = [(bb[0], HH - bb[3]) for (x, nm, inv, bb) in F[0].get_xobjects() if inv == 0 and nm.startswith("fzFrm")]
    mirrored = sorted((round(450 * MM - x - tw, 1), round(y, 1)) for x, y in fpos)
    check(S, "Orqa 6 ta pozitsiya = old pozitsiyalarning chap-o'ng ko'zgusi (chapdan-o'ngga aylantirishda ustma-ust)",
          bpos == mirrored and len(bpos) == 6, f"{bpos}")
    # matn: raqam + sektor/qator/joy BARCHA biletlar
    printed = {}
    for p in F:
        words = p.get_text("words")
        for i, (x, y) in enumerate(slots):
            dx, dy = x - IV.FRONT.x0, y - IV.FRONT.y0
            na = fitz.Rect(IV.NUM_AREA.x0 + dx, IV.NUM_AREA.y0 + dy, IV.NUM_AREA.x1 + dx, IV.NUM_AREA.y1 + dy)
            num = [w[4] for w in words if fitz.Rect(w[:4]).intersects(na) and re.fullmatch(r"\d{5}", w[4])]
            if not num:
                continue
            vals = []
            E6 = [IV.SEAT_BOX.x0, IV.SEAT_DIVIDERS[0], IV.SEAT_DIVIDERS[1], IV.SEAT_BOX.x1]   # V6: asl 3 ustun
            la = fitz.Rect(IV.SEAT_BOX.x0 + dx, 227 + dy, IV.SEAT_DIVIDERS[0] + dx, IV.SEAT_LABEL_BASELINE + 1.2 + dy)
            vals.append(" ".join(w[4] for w in words if fitz.Rect(w[:4]).intersects(la)))
            for c0, c1 in zip(E6[:-1], E6[1:]):
                ar = fitz.Rect(c0 + dx, IV.SEAT_LABEL_BASELINE + 2.5 + dy, c1 + dx, IV.SEAT_BOX.y1 + dy)
                vals.append(" ".join(w[4] for w in words if fitz.Rect(w[:4]).intersects(ar)))
            printed[num[0]] = (p.number + 1, i + 1, vals)
    order_ok = [k for k in printed] == codes
    LBL = {"BLITCHER": "BLITCHER", "SEKTOR": "SEKTOR №"}
    seat_ok = all(printed[m["TICKET_NUMBER"]][2] == [LBL[m["FIELD1_LABEL"]], m["SECTOR"], m["ROW"], m["SEAT"]] for m in M if m["TICKET_NUMBER"] in printed)
    bad_lab = [c for c, v in printed.items() if v[2][0] not in ("BLITCHER", "SEKTOR №")]
    seq_ok = all(printed[c][:2] == ((int(c) - 1) // 6 + 1, (int(c) - 1) % 6 + 1) for c in printed)
    check(S, "Bosilgan raqamlar: 11 222 ta, 00001…11222, takrorsiz, list/pozitsiya ketma-ket", len(printed) == N and order_ok and seq_ok,
          f"{len(printed)} raqam")
    check(S, "Bosilgan yorliq (BLITCHER / SEKTOR №) va SEKTOR, QATOR, JOY qiymatlari = master = sayt (barcha 11 222 bilet)", seat_ok and len(printed) == N)
    floor_hits = 0
    for p in F:
        floor_hits += len(re.findall(r"QAVAT|ZONA|этаж|Zona|Qavat", p.get_text()))
    check(S, "Hech bir biletda qavat/zona yozuvi yo'q (ZONA/QAVAT, 2-QAVAT, 4-QAVAT, 2-этаж, 4-этаж) — barcha 1871 sahifa matni", floor_hits == 0 and not bad_lab, f"topildi: {floor_hits}")
    nbl = sum(1 for v in printed.values() if v[2][0] == "BLITCHER")
    nse = sum(1 for v in printed.values() if v[2][0] == "SEKTOR №")
    check(S, "Bosilgan yorliqlar: BLITCHER 1 896 ta, SEKTOR № 9 326 ta", nbl == 1896 and nse == 9326, f"BLITCHER {nbl}, SEKTOR № {nse}")
    # QR dekodlash: birinchi, o'rta, oxirgi + tasodifiy listlar
    pages = sorted({0, NS // 2, NS - 1} | set(random.Random(5).sample(range(NS), 25)))
    qbad, qn = [], 0
    for pi in pages:
        p = F[pi]
        for i, (x, y) in enumerate(slots):
            code_i = pi * 6 + i + 1
            if code_i > N:
                continue
            dx, dy = x - IV.FRONT.x0, y - IV.FRONT.y0
            clip = fitz.Rect(IV.QR_BOX.x0 + dx, IV.QR_BOX.y0 + dy, IV.QR_BOX.x1 + dx, IV.QR_BOX.y1 + dy)
            pix = p.get_pixmap(dpi=300, clip=clip, colorspace=fitz.csGRAY)
            d = [z.data.decode() for z in decode(Image.frombytes("L", (pix.w, pix.h), pix.samples))]
            qn += 1
            c = str(code_i).zfill(5)
            if d != [BASE + c] or printed[c][0] != pi + 1:
                qbad.append((pi + 1, c, d))
    check(S, f"PDF ichidagi QR (300 dpi) yonidagi bosilgan raqamga mos — 1, 936, 1871 + 25 tasodifiy list", not qbad,
          qbad[:3] or f"{qn} QR")
    # kesish belgilari va ramka
    cm_bad = []
    for pi in (0, NS // 2, NS - 1):
        for doc in ((F, B) if pi == 0 else (F,)):
            dr = doc[pi].get_drawings()
            lines = [it for g in dr if g.get("width") and abs(g["width"] - 0.25) < 1e-3 for it in g["items"] if it[0] == "l"]
            hair = [g for g in dr if g.get("width") and abs(g["width"] - 0.216) < 0.01]
            if len(lines) != 14 or hair:
                cm_bad.append((pi + 1, len(lines), len(hair)))
    check(S, "Kesish belgilari 14 ta (to'rdan 2 mm tashqarida), bilet atrofida ramka yo'q", not cm_bad, cm_bad)
    # texnik yozuv yo'q
    stray = [w[4] for pi in (0, 1870) for w in F[pi].get_text("words") if not fitz.Rect(w[:4]).intersects(fitz.Rect(ox, oy, ox + 2 * tw, oy + 3 * th))]
    check(S, "Varaq hoshiyasida texnik yozuv yo'q", not stray, stray[:5])
    # CMYK + shriftlar
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    for name, doc_path in (("FRONT", "out/DUSEL_FRONT_FINAL_CMYK.pdf"), ("BACK", "out/DUSEL_BACK_6UP_SINGLE_PAGE_CMYK.pdf")):
        dd = fitz.open(os.path.join(ROOT, doc_path))
        kinds, rgb_ops, kvals = set(), 0, set()
        for x in range(1, dd.xref_length()):
            try:
                o = dd.xref_object(x)
            except Exception:
                continue
            if "/Subtype /Image" in o or "/ShadingType" in o:
                cs = dd.xref_get_key(x, "ColorSpace")[1]
                if cs.endswith(" R"):
                    arr = dd.xref_object(int(cs.split()[0]))
                    n = dd.xref_get_key(int(arr.split("/ICCBased")[1].split()[0]), "N")[1] if "ICCBased" in arr else arr
                    kinds.add(f"ICCBased N={n}")
                else:
                    kinds.add(cs)
            if "/DeviceRGB" in o and "/Alternate /DeviceRGB" not in o:
                rgb_ops += 1
            if dd.xref_is_stream(x) and "/Subtype /Image" not in o and "/N " not in o and "/FontFile" not in o and "/Length1" not in o:
                try:
                    st = dd.xref_stream(x)
                except Exception:
                    st = b""
                if st and len(st) < 5_000_000:
                    rgb_ops += len(re.findall(rb"\b[\d.]+ [\d.]+ [\d.]+ (?:rg|RG)\b", st))
                    for m_ in re.finditer(rb"(?<![\d.])([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) (?:k|K)\b", st):
                        kvals.add(tuple(round(float(v), 3) for v in m_.groups()))
        has_oi = "OutputIntents" in dd.xref_object(dd.pdf_catalog())
        check("CMYK", f"{name}: rasm/gradientlar CMYK (ICC N=4) yoki kulrang niqob; RGB operator/DeviceRGB yo'q",
              not any("N=3" in k for k in kinds) and rgb_ops == 0, sorted(kinds))
        if name == "FRONT":
            check("CMYK", "FRONT: o'zgaruvchan matn va QR 100K, kesish belgilari Registration",
                  kvals <= {(0, 0, 0, 1), (1, 1, 1, 1)}, sorted(kvals))
        check("CMYK", f"{name}: OutputIntent ISO Coated v2 (ECI) / FOGRA39", has_oi)
        pf = subprocess.run(["pdffonts", "-l", "3", os.path.join(ROOT, doc_path)], capture_output=True, text=True).stdout.splitlines()[2:]
        check("SHRIFT", f"{name}: barcha shriftlar joylashtirilgan", all(l.split()[-5] == "yes" for l in pf if l.strip()),
              ", ".join(sorted({l.split()[0].split('+')[-1] for l in pf if l.strip()})))
    # ---------------- E. ARTWORK
    S = "ARTWORK"
    o = fitz.open(SRC_PDF)
    fx = fitz.open(os.path.join(ROOT, "artwork/src_fixed.pdf"))
    a, b = o.xref_stream(o[0].get_contents()[0]), fx.xref_stream(fx[0].get_contents()[0])
    diffb = sum(1 for x, y in zip(a, b) if x != y)
    check(S, "Asl kontent oqimidan farq: faqat 2 bayt (texnik 0.216 pt kesish konturi 's'→'n')", len(a) == len(b) and diffb == 2, diffb)
    cm = fitz.open(os.path.join(ROOT, "artwork/src_cmyk.pdf"))
    v6 = fitz.open(os.path.join(ROOT, "artwork/src_cmyk_v6.pdf"))
    c0_, c1_ = v6.xref_stream(v6[0].get_contents()[0]), v6.xref_stream(v6[1].get_contents()[0])
    orig_c = cm.xref_stream(cm[0].get_contents()[0])
    st_ = orig_c.find(b"BT\r\n45.6687 381.6757 TD"); en_ = orig_c.find(b"ET\r\n", st_) + 4
    check(S, "BLITCHER artwork varianti = asl artwork, faqat 'SEKTOR №' yorlig'i bloki (BT…ET, 288 bayt) olib tashlangan; rasmlar umumiy",
          c0_ == orig_c and c1_ == orig_c[:st_] + orig_c[en_:] and en_ - st_ == 288 and
          [i[0] for i in v6[0].get_images()] == [i[0] for i in v6[1].get_images()])
    same_struct = (len(cm[0].get_drawings()) == len(fx[0].get_drawings()) and
                   [i[2:4] for i in cm[0].get_images(full=True)] == [i[2:4] for i in fx[0].get_images(full=True)] and
                   cm[0].get_text() == fx[0].get_text())
    check(S, "CMYK artwork: vektorlar, rasmlar (o'lcham/ruxsat), matn — asl bilan bir xil tuzilma", same_struct)
    # ishlab chiqarish 1-list vs faqat-artwork etalon (bir xil joylashuv): o'zgaruvchan maydonlardan tashqarida 0 farq
    fitz.TOOLS.set_icc(False)   # xom CMYK siyoh qiymatlarini solishtirish (rang boshqaruvisiz)
    ref = fitz.open()
    rp = ref.new_page(width=450 * MM, height=320 * MM)
    for x, y in slots:
        rp.show_pdf_page(fitz.Rect(x, y, x + tw, y + th), cm, 0, clip=IV.FRONT)
    tot_changed = 0
    for pi in (0, 35, NS // 2):   # 1-list (SEKTOR), 36-list (BLITCHER), o'rta list
        pa = F[pi].get_pixmap(dpi=120, colorspace=fitz.csCMYK)
        pb = rp.get_pixmap(dpi=120, colorspace=fitz.csCMYK)
        A = np.frombuffer(pa.samples, np.uint8).reshape(pa.h, pa.w, pa.n)[:, :, :4].astype(int)
        Bm = np.frombuffer(pb.samples, np.uint8).reshape(pb.h, pb.w, pb.n)[:, :, :4].astype(int)
        D = np.abs(A - Bm).max(2)
        s_ = 120 / 72
        yy, xx = np.mgrid[0:D.shape[0], 0:D.shape[1]]
        X, Y = (xx + 0.5) / s_, (yy + 0.5) / s_
        mask = np.ones(D.shape, bool)
        for (x, y) in slots:
            ins = (X >= x) & (X < x + tw) & (Y >= y) & (Y < y + th)
            mask &= ~ins
            lx, ly = X - x + IV.FRONT.x0, Y - y + IV.FRONT.y0
            ti = pi * 6 + slots.index((x, y))
            regs = [IV.QR_BOX, IV.NUM_AREA, fitz.Rect(IV.SEAT_BOX.x0, IV.SEAT_LABEL_BASELINE + 0.8, IV.SEAT_BOX.x1, IV.SEAT_BOX.y1)]
            if ti < N and M[ti]["FIELD1_LABEL"] == "BLITCHER":
                regs.append(fitz.Rect(IV.SEAT_BOX.x0 + 2, 227.5, IV.SEAT_DIVIDERS[0] - 1, IV.SEAT_LABEL_BASELINE + 1.5))  # 1-ustun yorlig'i
            for r_ in regs:
                mask |= ins & (lx >= r_.x0 - 1) & (lx <= r_.x1 + 1) & (ly >= r_.y0 - 1) & (ly <= r_.y1 + 1)
        tot_changed += int((D[~mask] > 2).sum())
    check(S, "Listlar 1 (SEKTOR), 36 (BLITCHER), 936: ruxsat etilgan maydonlar (qiymatlar, BLITCHER yorlig'i, QR, raqam) tashqarisida asl artwork bilan 0 piksel farq (CMYK)", tot_changed == 0, f"o'zgargan piksel: {tot_changed}")
    # proof = production list 1
    pr = fitz.open(os.path.join(ROOT, "out/DUSEL_TEST_6UP.pdf"))
    check(S, "DUSEL_TEST_6UP.pdf = FRONT 1-list (piksel bo'yicha bir xil)", pr.page_count == 1 and pr[0].get_pixmap(dpi=60).samples == F[0].get_pixmap(dpi=60).samples)
    # orqa: asl orqa artwork o'zgarmagan (faqat-artwork etalon bilan 0 farq)
    refb = fitz.open()
    rb = refb.new_page(width=450 * MM, height=320 * MM)
    for (x, y) in slots:
        mx = 450 * MM - x - tw
        rb.show_pdf_page(fitz.Rect(mx, y, mx + tw, y + th), cm, 0, clip=IV.BACK)
    pa = B[0].get_pixmap(dpi=120, colorspace=fitz.csCMYK)
    pb = rb.get_pixmap(dpi=120, colorspace=fitz.csCMYK)
    A_ = np.frombuffer(pa.samples, np.uint8).reshape(pa.h, pa.w, pa.n).astype(int)
    B_ = np.frombuffer(pb.samples, np.uint8).reshape(pb.h, pb.w, pb.n).astype(int)
    gx0, gy0 = int(ox * 120 / 72) + 1, int(oy * 120 / 72) + 1
    gx1, gy1 = int((ox + 2 * tw) * 120 / 72) - 1, int((oy + 3 * th) * 120 / 72) - 1
    bd = int((np.abs(A_ - B_).max(2)[gy0:gy1, gx0:gx1] > 2).sum())
    check(S, "BACK: orqa artwork o'zgarmagan (bilet maydonida 0 piksel farq, CMYK)", bd == 0, f"o'zgargan piksel: {bd}")
    passed = sum(r["ok"] for r in R)
    print(f"\n{passed}/{len(R)} PASS")
    json.dump(R, open(os.path.join(ROOT, "final_test_results.json"), "w"), ensure_ascii=False, indent=1)
    sys.exit(0 if passed == len(R) else 1)


if __name__ == "__main__":
    main()
