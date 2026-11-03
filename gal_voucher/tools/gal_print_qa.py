#!/usr/bin/env python3
"""DUSEL GAL — bosma PDF QA: soni, raqamlar, QR=raqam, URL, joylashuv (kesilmaydi/ustma-ust emas), varaqlar, dizayn mosligi."""
import argparse, json, math, os, re, subprocess, sys
import numpy as np
import pymupdf as fitz
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol

MM = 72 / 25.4
R = []
def check(name, ok, detail=""):
    R.append(dict(name=name, ok=bool(ok), detail=str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail != "" else ""), flush=True)

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--repo", default="/home/claude/dusel_gal")
ap.add_argument("--qr-dpi", type=int, default=300)
a = ap.parse_args()
cfg = json.load(open(a.config))
ROOT = os.path.dirname(os.path.abspath(a.config))
per = cfg["layout"]["cols"] * cfg["layout"]["rows"]
EXP = [f"{i:06d}" for i in range(1, 1001)]
URL = "https://dusel.pages.dev/gal?code="

def zd(img):
    return [x.data.decode() for x in decode(img, symbols=[ZBarSymbol.QRCODE])]

TEST_PDF = cfg.get("out_test", f"DUSEL_GAL_{per}UP_TEST.pdf")
FINAL_PDF = cfg.get("out_final", "DUSEL_GAL_1000_PRINT_450x320.pdf")
for kind, path, n_exp in (("PROOF", TEST_PDF, per), ("PRINT", FINAL_PDF, 1000)):
    pdf = os.path.join(a.out, path)
    doc = fitz.open(pdf)
    lay = json.load(open(pdf.replace(".pdf", "_layout.json")))
    nums = [x["number"] for x in lay]
    sheets = math.ceil(n_exp / per)
    T = f"{kind}:"
    check(f"{T} bosilgan vaucherlar soni = {n_exp}", len(lay) == n_exp, len(lay))
    check(f"{T} raqamlar {EXP[0]}–{EXP[n_exp - 1]}, ketma-ket, tushib qolgan yo'q", nums == EXP[:n_exp])
    check(f"{T} takroriy raqam yo'q", len(set(nums)) == len(nums))
    check(f"{T} har bir QR manzili {URL}<raqam>", all(x["url"] == URL + x["number"] for x in lay))
    check(f"{T} varaqlar soni = {sheets}", len(doc) == sheets, len(doc))
    check(f"{T} barcha varaqlar 450×320 mm", all(abs(p.rect.width / MM - 450) < 0.05 and abs(p.rect.height / MM - 320) < 0.05 for p in doc))
    cnt = [sum(1 for x in lay if x["sheet"] == s + 1) for s in range(len(doc))]
    exp_cnt = [per] * (sheets - 1) + [n_exp - per * (sheets - 1)]
    check(f"{T} har varaqda to'g'ri soni (oxirgisi {exp_cnt[-1]})", cnt == exp_cnt, f"{per}×{sheets - 1} + {exp_cnt[-1]}")
    # joylashuv
    bad_in, bad_ov, bad_safe = [], [], []
    page_r = fitz.Rect(0, 0, 450 * MM, 320 * MM)
    safe = cfg.get("safe_mm", 3) * MM
    for s in range(len(doc)):
        L = [x for x in lay if x["sheet"] == s + 1]
        for x in L:
            t, b = fitz.Rect(x["trim"]), fitz.Rect(x["bleed"])
            if not page_r.contains(b) or b.x0 < 7 * MM or b.y0 < 7 * MM or b.x1 > page_r.x1 - 7 * MM or b.y1 > page_r.y1 - 7 * MM:
                bad_in.append(x["number"])
            for k in ("qr", "num"):
                q = fitz.Rect(x[k])
                if not (t + (safe, safe, -safe, -safe)).contains(q):
                    bad_safe.append((x["number"], k))
        for i in range(len(L)):
            for j in range(i + 1, len(L)):
                ti, tj = fitz.Rect(L[i]["trim"]), fitz.Rect(L[j]["trim"])
                bi, bj = fitz.Rect(L[i]["bleed"]), fitz.Rect(L[j]["bleed"])
                inter = bi & bj
                if (ti & tj).is_valid and not (ti & tj).is_empty or (inter.is_valid and inter.width > 0.01 and inter.height > 0.01):
                    bad_ov.append((L[i]["number"], L[j]["number"]))
    check(f"{T} hamma vaucher (bleed bilan) varaq ichida, chetdan ≥7 mm (kesish belgilari va qisqich uchun joy)", not bad_in, bad_in[:5])
    check(f"{T} vaucherlar ustma-ust tushmaydi (trim va bleed)", not bad_ov, bad_ov[:3])
    check(f"{T} QR va raqam kesish chizig'idan ≥{cfg.get('safe_mm', 3)} mm ichkarida", not bad_safe, bad_safe[:3])
    # bosilgan raqam (matn) = layout raqami
    bad = []
    for s, p in enumerate(doc):
        words = p.get_text("words")
        for x in [x for x in lay if x["sheet"] == s + 1]:
            t = fitz.Rect(x["trim"])
            w = [w[4] for w in words if re.fullmatch(r"\d{6}", w[4]) and t.contains(fitz.Rect(w[:4]))]
            if w != [x["number"]]:
                bad.append((x["number"], w))
    check(f"{T} har vaucherdagi bosilgan seriya raqami to'g'ri (bitta, o'z joyida)", not bad, bad[:3])
    # QR: render + dekod, payload = raqam
    bad, sizes = [], set()
    for x in lay:
        p = doc[x["sheet"] - 1]
        q = fitz.Rect(x["qr"])
        sizes.add(round(q.width / MM, 2))
        pix = p.get_pixmap(clip=q + (-3, -3, 3, 3), dpi=a.qr_dpi, colorspace=fitz.csGRAY)
        im = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        if zd(im) != [URL + x["number"]]:
            bad.append(x["number"])
    check(f"{T} har bir bosilgan QR ({len(lay)} ta) {a.qr_dpi} dpi'da dekod qilindi va o'z raqamiga mos", not bad, f"xato {bad[:5]}" if bad else f"{len(lay)}/{len(lay)}, QR {sorted(sizes)} mm")
    # kesish belgilari, rang, shrift
    p0 = doc[0]
    regs = [d for d in p0.get_drawings() if d["type"] == "s" and abs((d.get("width") or 0) - 0.25) < 1e-3]
    nmarks = sum(len(d["items"]) for d in regs)
    xs = {round(v, 2) for x in lay if x["sheet"] == 1 for v in (x["trim"][0], x["trim"][2])}
    ys = {round(v, 2) for x in lay if x["sheet"] == 1 for v in (x["trim"][1], x["trim"][3])}
    check(f"{T} kesish belgilari: har kesish chizig'i uchun 2 tadan (Registration 1/1/1/1, 0.25 pt)",
          nmarks == 2 * (len(xs) + len(ys)) and b"1 1 1 1 K" in p0.read_contents(), f"{nmarks} belgi, {len(xs)} vertikal + {len(ys)} gorizontal kesish")
    fonts = {f[3] for p in doc for f in p.get_fonts(full=True)}
    check(f"{T} shriftlar embed qilingan (subset)", fonts and all("+" in f for f in fonts), fonts)
    cat = doc.pdf_catalog()
    check(f"{T} OutputIntent ISO Coated v2 (ECI)", doc.xref_get_key(cat, "OutputIntents")[0] == "array")
    imgs = {i[0]: i for p in doc for i in p.get_images(full=True)}
    check(f"{T} dizayn rasmi CMYK (ISO Coated v2) va bitta obyekt qayta ishlatiladi", len(imgs) == 1 and list(imgs.values())[0][5] in ("ICCBased", "DeviceCMYK"), [(v[2], v[3], v[5]) for v in imgs.values()])

# dizayn mosligi: proof vaucheri vs asl rasm (o'zgaruvchi zonalardan tashqari)
doc = fitz.open(os.path.join(a.out, TEST_PDF))
lay = json.load(open(os.path.join(a.out, TEST_PDF.replace(".pdf", "_layout.json"))))
art = Image.open(os.path.join(ROOT, cfg["artwork"])).convert("RGB")
W, H = art.size
x = lay[0]
t = fitz.Rect(x["trim"])
pad = cfg.get("pad_px") or {}
ppm_ = W / cfg["voucher_mm"][0]
t = fitz.Rect(t.x0, t.y0 + pad.get("top", 0) / ppm_ * MM, t.x1, t.y1 - pad.get("bottom", 0) / ppm_ * MM)   # asl dizayn qismi (fon davomisiz)
pix = doc[0].get_pixmap(clip=t, dpi=150)
ren = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
if cfg["layout"].get("rotated"):
    ren = ren.transpose(Image.ROTATE_90)
ren = ren.resize((W // 4, H // 4), Image.LANCZOS)
ref = art.resize((W // 4, H // 4), Image.LANCZOS)
A, B = np.asarray(ref, np.int16), np.asarray(ren, np.int16)
mask = np.ones(A.shape[:2], bool)
for e in cfg.get("erase", []) + [cfg["qr_box"] + [None], cfg["serial"]["box"] + [None]]:
    x0, y0, x1, y1 = [int(v / 4) for v in e[:4]]
    mask[max(0, y0 - 3):y1 + 3, max(0, x0 - 3):x1 + 3] = False
d = np.abs(A - B).mean(axis=2)[mask]
check("Dizayn: proof'dagi vaucher asl rasmga mos (o'zgaruvchi zonalardan tashqari; CMYK konvertatsiya farqi hisobga olingan)",
      d.mean() < 12 and np.percentile(d, 99) < 60, f"o'rtacha farq {d.mean():.1f}/255, 99-persentil {np.percentile(d, 99):.0f}")
ratio = (t.width / t.height) if not cfg["layout"].get("rotated") else (t.height / t.width)
check("Asl dizayn bir xil masshtabda (eni va bo'yi bo'yicha) — cho'zilmagan", abs(ratio - W / H) / (W / H) < 0.002, f"vaucher {ratio:.4f} / asl {W / H:.4f}")

# boshqa tizimlar o'zgarmagan
if os.path.isdir(a.repo):
    def blob(ref, f):
        return subprocess.run(["git", "-C", a.repo, "rev-parse", f"{ref}:{f}"], capture_output=True, text=True).stdout.strip()
    same = {f: blob("origin/main", f) == blob("HEAD", f) for f in ("index.html", "coupon.html", "assets/logo.svg")}
    check("Bilet (index.html) va GOLD/SILVER (coupon.html) sahifalari main bilan bayt-bayt bir xil", all(same.values()), same)

json.dump(R, open(os.path.join(a.out, "gal_print_qa_results.json"), "w"), ensure_ascii=False, indent=1)
print(f"\n{sum(r['ok'] for r in R)}/{len(R)} PASS")
sys.exit(0 if all(r["ok"] for r in R) else 1)
