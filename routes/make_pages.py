#!/usr/bin/env python3
"""coupon.html (o'zgarmaydi, eski /coupon?type=… havolalari uchun) asosida alohida gold.html va silver.html;
index.html asosida ticket.html. Har sahifa faqat o'z mahsulotini biladi."""
import sys, os
R = sys.argv[1]
src = open(os.path.join(R, "coupon.html"), encoding="utf-8").read()
T_OLD = """  var T={gold:{max:2000,name:'GOLD',prize:'10 TA AVTOMOBIL',hero:'assets/coupon/gold_hero.webp',alt:"Sovg'a avtomobillar"},
         silver:{max:4000,name:'SILVER',prize:'100 TA CHET ELGA SAYOHAT',hero:'assets/coupon/silver_hero.webp',alt:'Chet elga sayohat'}};"""
assert src.count(T_OLD) == 1
TYPE_OLD = "  var type=(q.get('type')||'').toLowerCase(), code=q.get('code')||'';"
assert src.count(TYPE_OLD) == 1
CMT_OLD = "  // KUPON mantiqi bilet sahifasidan butunlay alohida: /coupon?type=gold|silver&code=NNNN"
assert src.count(CMT_OLD) == 1
ERR_OLD = "<p>Havolada kupon turi va 4 xonali raqam bo'lishi kerak:<br><b>GOLD</b> — <code>0001</code>–<code>2000</code>, <b>SILVER</b> — <code>0001</code>–<code>4000</code>.<br>Kupondagi QR kodni qayta skanerlang.</p>"
assert src.count(ERR_OLD) == 1
D = {
 "gold": dict(T="  var T={gold:{max:2000,name:'GOLD',prize:'10 TA AVTOMOBIL',hero:'assets/coupon/gold_hero.webp',alt:\"Sovg'a avtomobillar\"}};",
              err="<p>Havolada 4 xonali GOLD kupon raqami bo'lishi kerak:<br><code>0001</code>–<code>2000</code>.<br>Kupondagi QR kodni qayta skanerlang.</p>",
              name="GOLD", prize="10 TA AVTOMOBIL", title="DUSEL — GOLD kupon"),
 "silver": dict(T="  var T={silver:{max:4000,name:'SILVER',prize:'100 TA CHET ELGA SAYOHAT',hero:'assets/coupon/silver_hero.webp',alt:'Chet elga sayohat'}};",
              err="<p>Havolada 4 xonali SILVER kupon raqami bo'lishi kerak:<br><code>0001</code>–<code>4000</code>.<br>Kupondagi QR kodni qayta skanerlang.</p>",
              name="SILVER", prize="100 TA CHET ELGA SAYOHAT", title="DUSEL — SILVER kupon"),
}
for t, d in D.items():
    s = src.replace(T_OLD, d["T"]).replace(TYPE_OLD, f"  var type='{t}', code=q.get('code')||'';   // tur yo'ldan: /{t} — 'type' parametri e'tiborga olinmaydi")
    s = s.replace(CMT_OLD, f"  // {d['name']} kupon sahifasi: faqat /{t}?code=NNNN (0001–{2000 if t == 'gold' else 4000}); bilet, GAL va boshqa kupon turi bu yerda hech qachon ko'rsatilmaydi")
    s = s.replace(ERR_OLD, d["err"])
    s = s.replace("<title>DUSEL — Kupon</title>", f"<title>{d['title']}</title>")
    s = s.replace('<html lang="uz">', f'<html lang="uz" data-type="{t}">', 1)
    s = s.replace('<div class="type metal" id="ttl">GOLD</div>', f'<div class="type metal" id="ttl">{d["name"]}</div>')
    s = s.replace('<div class="prize" id="prize">10 TA AVTOMOBIL</div>', f'<div class="prize" id="prize">{d["prize"]}</div>')
    s = s.replace('<span id="chip">GOLD KUPON</span>', f'<span id="chip">{d["name"]} KUPON</span>')
    s = s.replace('<meta name="description" content="DUSEL electrical — GOLD va SILVER lototron kuponi.">', f'<meta name="description" content="DUSEL electrical — {d['name']} lototron kuponi.">')
    s = s.replace("  // fon effekti: GOLD — ko'tariluvchi oltin uchqunlar; SILVER — sovuq kumush yulduzchalar", "  // fon effekti (kupon turiga mos)")
    s = s.replace("/* --- mavzu tokenlari: GOLD (standart) --- */", "/* --- mavzu tokenlari --- */")
    other = "SILVER" if t == "gold" else "GOLD"
    assert other not in s.replace("'" + other.lower(), ""), (t, [l for l in s.splitlines() if other in l][:3])
    open(os.path.join(R, f"{t}.html"), "w", encoding="utf-8").write(s)
    print("OK", t)
idx = open(os.path.join(R, "index.html"), encoding="utf-8").read()
assert "var MIN=1, MAX=11222;" in idx and "/^\\d{5}$/.test(raw)" in idx
open(os.path.join(R, "ticket.html"), "w", encoding="utf-8").write(idx)
print("OK ticket")
