#!/usr/bin/env python3
"""Jismoniy qurilma sinovi uchun chop etiladigan varaqlar (A4 PDF).
Barcha bilet QR'lari SINOV formatida (&t=SINOV yoki DUSELTEST:) — faqat STAGING bazasida bilet; PRODUCTION'da "YAROQSIZ QR".
Kupon namunalari diapazondan tashqari raqamlar (9999) — haqiqiy kupon emas.
python3 tools/make_test_kit.py docs/field_test/DUSEL_sinov_varaqasi.pdf
"""
import io, sys, segno
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

out = sys.argv[1] if len(sys.argv) > 1 else "DUSEL_sinov_varaqasi.pdf"
pdfmetrics.registerFont(TTFont("D", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DB", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
W, H = A4
c = canvas.Canvas(out, pagesize=A4)
c.setTitle("DUSEL — skaner sinov varaqasi (faqat STAGING)")
T = lambda n, shape=0: [f"https://dusel.pages.dev/?code={n:05d}&t=SINOV", f"https://dusel.pages.dev/ticket?code={n:05d}&t=SINOV",
                        f"https://ravshanrakhmatullaev.github.io/dusel/?code={n:05d}&t=SINOV"][shape]

def qr(payload, x, y, size):
    buf = io.BytesIO(); segno.make(payload, error="m", micro=False).save(buf, kind="png", scale=10, border=4); buf.seek(0)
    c.drawImage(ImageReader(buf), x, y, size, size)

def page(title, subtitle):
    c.setFillColorRGB(0.92, 0.92, 0.92); c.saveState(); c.translate(W / 2, H / 2); c.rotate(35)
    c.setFont("DB", 90); c.drawCentredString(0, 0, "SINOV"); c.restoreState()
    c.setFillColorRGB(0, 0, 0); c.setFont("DB", 15); c.drawString(15 * mm, H - 17 * mm, title)
    c.setFont("D", 8.5); c.drawString(15 * mm, H - 23 * mm, subtitle)
    c.setFillColorRGB(0.75, 0, 0); c.setFont("DB", 8.5)
    c.drawCentredString(W / 2, 9 * mm, "SINOV VARAG'I — haqiqiy kirish BERMAYDI (production'da \"YAROQSIZ QR\"). Faqat STAGING. Sinovdan keyin yo'q qiling.")
    c.setFillColorRGB(0, 0, 0)

def grid(items, cols, size, top, gap_y=18 * mm):
    cw = (W - 30 * mm) / cols
    for i, (payload, label, expect) in enumerate(items):
        r, k = divmod(i, cols)
        x = 15 * mm + k * cw + (cw - size) / 2; y = top - r * (size + gap_y) - size
        qr(payload, x, y, size)
        c.setFont("DB", 8); c.drawCentredString(x + size / 2, y - 4 * mm, label)
        c.setFont("D", 6.8); c.drawCentredString(x + size / 2, y - 7.5 * mm, "Kutilgan: " + expect)

# 1-varaq: formatlar va rad etish
page("1. QR formatlari va rad etish (STAGING)", "Har birini /scan-test va staging /checkin da skanerlang. Natija \"Kutilgan\" bilan mos bo'lishi kerak.")
grid([
    (T(330, 0), "1) dusel.pages.dev/?code=00330", "SINOV BILETI № 00330 / KIRITISH MUMKIN"),
    (T(6114, 1), "2) /ticket?code=06114", "SINOV BILETI № 06114 / KIRITISH MUMKIN"),
    (T(11222, 2), "3) github.io/dusel/?code=11222", "SINOV BILETI № 11222"),
    ("DUSELTEST:05000", "4) DUSELTEST:05000", "SINOV BILETI № 05000"),
    ("https://dusel.pages.dev/gold?code=9999", "5) GOLD namuna (9999)", "BU KONSERT BILETI EMAS"),
    ("https://dusel.pages.dev/silver?code=9999", "6) SILVER namuna (9999)", "BU KONSERT BILETI EMAS"),
    ("https://dusel.pages.dev/gal?code=9999", "7) GAL namuna (9999)", "BU KONSERT BILETI EMAS"),
    (T(11223, 0), "8) diapazondan tashqari 11223", "YAROQSIZ QR"),
    ("https://example.com/?code=00330", "9) begona sayt", "YAROQSIZ QR"),
], 3, 44 * mm, H - 30 * mm)
c.showPage()
# 2-varaq: tezlik
page("2. Skanerlash tezligi — 24 ta ketma-ket bilet (09001–09024)", "Taymer bilan: 24 ta biletni ketma-ket skanerlang (tezkor rejim). Vaqtni yozing. Har biri bir marta yashil bo'lishi kerak.")
grid([(T(9000 + i, i % 3), f"№ {9000 + i:05d}", "1-skan yashil, 2-skan qizil") for i in range(1, 25)], 6, 26 * mm, H - 30 * mm, 13 * mm)
c.showPage()
# 3-varaq: bir vaqtda kiritish
page("3. Bir vaqtda kiritish — 4 telefon bitta biletni bir lahzada", "Har ustundagi 4 nusxani 4 ta telefonga bering; \"3-2-1\" bilan birga KIRITISH. Har raqam uchun AYNAN BITTA yashil.")
items = []
for n in (9100, 9101, 9102):
    items += [(T(n, k % 3), f"№ {n:05d} · telefon {k + 1}", "4 telefondan faqat 1 yashil") for k in range(4)]
grid(items, 4, 34 * mm, H - 30 * mm, 15 * mm)
c.showPage()
# 4-varaq: inventar takrori
page("4. Inventar: takror skan va ikkinchi qog'oz", "A ni ikki marta skanerlang → \"YO'Q — o'sha qog'oz\". So'ng B ni skanerlang → \"HA — ikkinchi qog'oz\" (D-konvert). Natija: 2 tasdiqlangan qog'oz, nazoratchiga belgi.")
grid([(T(9200, 0), "№ 09200 — qog'oz A", "1-skan: Qayd etildi"), (T(9200, 0), "№ 09200 — qog'oz B", "TAKROR → HA → TASDIQLANGAN DUBLIKAT"),
      (T(9201, 1), "№ 09201 — bitta qog'oz", "2 marta skan → YO'Q → nusxa emas")], 3, 50 * mm, H - 30 * mm)
c.showPage()
c.save()
print(out)
