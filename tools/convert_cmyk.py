#!/usr/bin/env python3
"""
Artwork'ni CMYK ga o'tkazish — PDF tuzilmasi O'ZGARMAYDI (vektor vektorligicha, gradient gradientligicha,
rasm o'lchami/ruxsati o'sha, shriftlar o'sha), faqat rang qiymatlari ICC orqali almashtiriladi.

Manba profil: asl PDF ichidagi sRGB IEC61966-2.1 (CS14).
Maqsad profil: asl PDF ichidagi "ISO Coated v2 (ECI)" (CS17, FOGRA39 asosida) — dizaynerning o'z ish oqimi profili.
Intent: Relative Colorimetric + Black Point Compensation (CorelDRAW standarti; asl PDF dagi /RI ham RelativeColorimetric).

Ishlatish: python convert_cmyk.py artwork/src_fixed.pdf artwork/src_cmyk.pdf
"""
import io, re, sys
import pymupdf as fitz
from PIL import Image, ImageCms

SRC, DST = sys.argv[1], sys.argv[2]
d = fitz.open(SRC)
page = d[0]

RGB_CS, CMYK_CS = 14, 17
rgb_icc = d.xref_stream(int(d.xref_object(RGB_CS).split("/ICCBased")[1].split()[0]))
cmyk_icc = d.xref_stream(int(d.xref_object(CMYK_CS).split("/ICCBased")[1].split()[0]))
p_rgb = ImageCms.ImageCmsProfile(io.BytesIO(rgb_icc))
p_cmyk = ImageCms.ImageCmsProfile(io.BytesIO(cmyk_icc))
assert "sRGB" in ImageCms.getProfileDescription(p_rgb)
assert "ISO Coated v2" in ImageCms.getProfileDescription(p_cmyk)
XF = ImageCms.buildTransform(p_rgb, p_cmyk, "RGB", "CMYK",
                             renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
                             flags=ImageCms.Flags.BLACKPOINTCOMPENSATION)
_cache = {}


def rgb2cmyk(r, g, b):
    key = (round(r * 255), round(g * 255), round(b * 255))
    if key not in _cache:
        im = Image.new("RGB", (1, 1), key)
        c = ImageCms.applyTransform(im, XF).getpixel((0, 0))
        _cache[key] = tuple(v / 255 for v in c)
    return _cache[key]


log = {"content_ops": 0, "images": [], "shadings": []}

# 1) Kontent oqimi: /CS14 cs r g b scn  ->  /CS17 cs c m y k scn
cx = page.get_contents()
assert len(cx) == 1
cs = d.xref_stream(cx[0])
pat = re.compile(rb"/CS14 (cs|CS) ([\d.]+) ([\d.]+) ([\d.]+) (scn|SCN)")


def rep(m):
    c = rgb2cmyk(float(m.group(2)), float(m.group(3)), float(m.group(4)))
    log["content_ops"] += 1
    return b"/CS17 " + m.group(1) + b" " + " ".join(f"{v:.4f}" for v in c).encode() + b" " + m.group(5)


cs2 = pat.sub(rep, cs)
assert b"/CS14" not in cs2
assert not re.search(rb"\b(rg|RG)\b", cs2)
d.update_stream(cx[0], cs2)

# 2) Gradientlar: rang fazosi CMYK, funksiya 32 bo'lakli namunaga almashtiriladi (asl egri chiziq saqlanadi)


def eval_fn(xref, t):
    o = d.xref_object(xref)
    ft = int(re.search(r"/FunctionType (\d)", o).group(1))
    if ft == 2:
        c0 = [float(v) for v in re.search(r"/C0 \[([^\]]*)\]", o).group(1).split()]
        c1 = [float(v) for v in re.search(r"/C1 \[([^\]]*)\]", o).group(1).split()]
        n = float(re.search(r"/N ([\d.]+)", o).group(1))
        return [a + (t ** n) * (b - a) for a, b in zip(c0, c1)]
    if ft == 3:
        subs = [int(x) for x in re.findall(r"(\d+) 0 R", re.search(r"/Functions \[([^\]]*)\]", o).group(1))]
        assert len(subs) == 1, "faqat bitta ichki funksiya kutilgan"
        e = [float(v) for v in re.search(r"/Encode \[([^\]]*)\]", o).group(1).split()]
        return eval_fn(subs[0], e[0] + t * (e[1] - e[0]))
    raise ValueError(ft)


for sh in (32, 62, 72):
    o = d.xref_object(sh)
    assert "/ColorSpace 14 0 R" in o and "/ShadingType 2" in o
    fx = int(re.search(r"/Function (\d+) 0 R", o).group(1))
    N = 32
    samples = [rgb2cmyk(*eval_fn(fx, i / N)) for i in range(N + 1)]
    subs = []
    for i in range(N):
        a, b = samples[i], samples[i + 1]
        x = d.get_new_xref()
        d.update_object(x, "<< /FunctionType 2 /Domain [0 1] /C0 [%s] /C1 [%s] /N 1 >>" % (
            " ".join(f"{v:.5f}" for v in a), " ".join(f"{v:.5f}" for v in b)))
        subs.append(x)
    nf = d.get_new_xref()
    d.update_object(nf, "<< /FunctionType 3 /Domain [0 1] /Functions [%s] /Bounds [%s] /Encode [%s] >>" % (
        " ".join(f"{x} 0 R" for x in subs), " ".join(f"{i / N:.5f}" for i in range(1, N)), " ".join(["0 1"] * N)))
    d.xref_set_key(sh, "ColorSpace", f"{CMYK_CS} 0 R")
    d.xref_set_key(sh, "Function", f"{nf} 0 R")
    log["shadings"].append((sh, "C0", [round(v, 3) for v in samples[0]], "C1", [round(v, 3) for v in samples[-1]]))

# 3) Rasmlar: piksel RGB -> CMYK (o'lcham, ruxsat, SMask o'zgarmaydi)
for img in page.get_images(full=True):
    x = img[0]
    if d.xref_get_key(x, "ColorSpace")[1] != f"{RGB_CS} 0 R":
        continue
    pix = fitz.Pixmap(d, x)
    assert pix.n == 3 and not pix.alpha, (x, pix.n, pix.alpha)
    w, h = pix.width, pix.height
    im = Image.frombytes("RGB", (w, h), pix.samples)
    cm = ImageCms.applyTransform(im, XF)
    d.update_stream(x, cm.tobytes(), compress=True)
    d.xref_set_key(x, "Filter", "/FlateDecode")
    d.xref_set_key(x, "DecodeParms", "null")
    d.xref_set_key(x, "ColorSpace", f"{CMYK_CS} 0 R")
    d.xref_set_key(x, "BitsPerComponent", "8")
    log["images"].append((x, w, h))

# 4) Resurslardan RGB rang fazosini olib tashlash
d.xref_set_key(page.xref, "Resources/ColorSpace", f"<</DefaultCMYK {CMYK_CS} 0 R/CS17 {CMYK_CS} 0 R>>")
d.save(DST, garbage=3, deflate=True)
print("content ops:", log["content_ops"], "| images:", len(log["images"]), "| shadings:", len(log["shadings"]))
for s in log["shadings"]:
    print("  shading", s)
