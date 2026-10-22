#!/usr/bin/env python3
"""
Asl Bilet_final.pdf dan bosma uchun artwork tayyorlash (dizayn O'ZGARMAYDI).

1) src_fixed.pdf  — asl fayl; faqat 2 ta texnik kontur (0.216 pt, 100K, aynan kesish chizig'ida,
                    CorelDRAW sahifa/kesish konturi) bo'yalmaydigan qilinadi: yo'l "s" -> "n".
                    Boshqa hech bir operator o'zgarmaydi.
2) src_cmyk.pdf   — src_fixed.pdf ni convert_cmyk.py bilan CMYK ga o'tkazish (tuzilma saqlanadi).
                    Maqsad profil: dizayner faylining o'zida joylashgan "ISO Coated v2 (ECI)" (FOGRA39 asosida).
                    Rendering intent: Relative Colorimetric + Black Point Compensation. Rasmlar yo'qotishsiz (Flate).
"""
import os, re, subprocess, sys, io
import pymupdf as fitz

SRC = sys.argv[1] if len(sys.argv) > 1 else "../kit/Bilet_final.pdf"
OUT = sys.argv[2] if len(sys.argv) > 2 else "artwork"
os.makedirs(OUT, exist_ok=True)

HAIRLINES = [
    b"14.1732 598.1751 m\r\n581.1024 598.1751 l\r\n581.1024 314.7106 l\r\n14.1732 314.7106 l\r\nh\r\ns\r\n",  # old tomon
    b"14.1732 300.1592 m\r\n581.1024 300.1592 l\r\n581.1024 16.6946 l\r\n14.1732 16.6946 l\r\nh\r\ns\r\n",  # orqa tomon
]

d = fitz.open(SRC)
p = d[0]
xrefs = p.get_contents()
assert len(xrefs) == 1, xrefs
raw = d.xref_stream(xrefs[0])
new = raw
for h in HAIRLINES:
    assert new.count(h) == 1, "kontur topilmadi yoki bir nechta"
    new = new.replace(h, h[:-3] + b"n\r\n")
assert len(new) == len(raw)
diff = sum(1 for a, b in zip(raw, new) if a != b)
assert diff == 2, diff  # faqat 2 bayt: "s" -> "n"
d.update_stream(xrefs[0], new)
fixed = os.path.join(OUT, "src_fixed.pdf")
d.save(fixed, garbage=0, deflate=True)
print("src_fixed.pdf: o'zgargan baytlar =", diff)

# ICC profilni asl fayldan olish
icc_ref = int(d.xref_object(17).split("/ICCBased")[1].split()[0])
icc = d.xref_stream(icc_ref)
icc_path = os.path.join(OUT, "ISOcoated_v2_eci_from_source.icc")
open(icc_path, "wb").write(icc)
srgb_ref = int(d.xref_object(14).split("/ICCBased")[1].split()[0])
srgb_path = os.path.join(OUT, "sRGB_from_source.icc")
open(srgb_path, "wb").write(d.xref_stream(srgb_ref))
from PIL import ImageCms
print("CMYK profil:", ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc))).strip())

# CMYK konversiya: convert_cmyk.py (Ghostscript gradientlarni 90 ppi rasmga aylantirgani uchun ishlatilmadi)
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "convert_cmyk.py"),
                fixed, os.path.join(OUT, "src_cmyk.pdf")], check=True)
