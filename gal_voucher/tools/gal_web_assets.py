#!/usr/bin/env python3
"""GAL veb sahifasi uchun asl dizayndan kesimlar (hero, sarlavha, summa) — qizil fon shaffof qilinadi."""
import os, sys
import numpy as np
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "input", "Vaucher(1).png")
OUT = os.path.join(ROOT, "web", "assets", "gal")
os.makedirs(OUT, exist_ok=True)
im = Image.open(SRC).convert("RGB")
a = np.asarray(im).copy()
# hero kesimiga tushadigan "...15 KUN ICHIDA AMAL QILADI!" qatori qismini fon bilan to'ldirish (faqat veb; bosmada asl matn qoladi)
y0, y1, x0, x1 = 192, 258, 1150, 1700
top, bot = a[y0 - 6:y0 - 2, x0:x1].mean(axis=0), a[y1 + 2:y1 + 6, x0:x1].mean(axis=0)
for k, y in enumerate(range(y0, y1)):
    t = k / (y1 - y0)
    a[y, x0:x1] = (top * (1 - t) + bot * t).astype(np.uint8)


def crop(box, name, w, feather, lo, hi):
    c = a[box[1]:box[3], box[0]:box[2]].astype(float)
    H, W = c.shape[:2]
    # mahalliy fon: chekka piksellar medianasi asosida, qatorma-qator gradient
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    edge = np.concatenate([c[:4].reshape(-1, 3), c[-4:].reshape(-1, 3), c[:, :4].reshape(-1, 3), c[:, -4:].reshape(-1, 3)])
    bg = np.median(edge, axis=0)
    # fon gradientini hisobga olish: qizil kanal yaqin, yashil/ko'k past bo'lsa — fon
    d = np.sqrt(((c - bg) ** 2).sum(axis=2))
    redness = (c[..., 0] > 150) & (c[..., 1] < 70) & (c[..., 2] < 45)
    key = np.clip((d - lo) / (hi - lo), 0, 1)
    key = np.where(redness, key, 1.0)
    dd = np.minimum.reduce([xx, yy, W - 1 - xx, H - 1 - yy]); f = feather * min(W, H)
    fe = np.clip(dd / f, 0, 1); fe = fe * fe * (3 - 2 * fe)
    al = key * fe
    o = Image.fromarray(np.dstack([c.astype(np.uint8), (al * 255).astype(np.uint8)]), "RGBA").resize((w, round(H * w / W)), Image.LANCZOS)
    o.save(os.path.join(OUT, name + ".webp"), "WEBP", quality=84, method=6)
    # yaltirash maskasi (faqat oltin/oq harflar)
    oa = np.asarray(o).astype(int)
    r, g, b = oa[..., 0], oa[..., 1], oa[..., 2]
    m = (((r > 190) & (g > 120) & (b < 170) & (g - b > 40)) | (np.minimum(np.minimum(r, g), b) > 205)) & (oa[..., 3] > 200)
    mk = np.zeros_like(oa, dtype=np.uint8); mk[..., :3] = 255; mk[..., 3] = m * 255
    Image.fromarray(mk, "RGBA").save(os.path.join(OUT, name + "_mask.webp"), "WEBP", quality=70)
    print(name, o.size, "bg", bg.round())


crop((1170, 90, 2690, 1425), "hero", 960, 0.05, 22, 60)
crop((150, 455, 1200, 895), "title", 840, 0.05, 34, 78)
crop((165, 1015, 1240, 1395), "amount", 860, 0.05, 34, 78)
