// DUSEL — HAQIQIY HTTPS orqali qurilma sinovlari (Cloudflare staging preview + production faqat o'qish).
// WebKit (iPhone Safari dvigateli) va Chromium (Android Chrome) — Playwright qurilma emulyatsiyasi.
// node test_devices.mjs <staging_base> <prod_base> <out_dir> [media_dir]
// Hech narsa yozmaydi: /scan-test serverga so'rov yubormaydi; /checkin va /inventory staging'da server sozlamasisiz ("faollashtirilmagan").
import { chromium, webkit, devices } from 'playwright';
import fs from 'fs';
const STG = process.argv[2] || 'https://feature-checkin.dusel.pages.dev';
const PROD = process.argv[3] || 'https://dusel.pages.dev';
const out = process.argv[4] || 'devices'; fs.mkdirSync(out, { recursive: true });
const MEDIA = process.argv[5] || 'media';
// Haqiqiy skaner + telefon kirill (ЙЦУКЕН) tartibida: skaner US jismoniy tugma kodlarini yuboradi, brauzer esa e.key = kirill harf beradi
const scanAsRuKeyboard = (page, text) => page.evaluate((text) => {
  const US = "qwertyuiop[]asdfghjkl;'zxcvbnm,./QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?";
  const RU = 'йцукенгшщзхъфывапролджэячсмитьбю.ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,';
  const P = { '.': ['Period', 0], '>': ['Period', 1], ',': ['Comma', 0], '<': ['Comma', 1], '/': ['Slash', 0], '?': ['Slash', 1], ';': ['Semicolon', 0], ':': ['Semicolon', 1],
              '=': ['Equal', 0], '+': ['Equal', 1], '-': ['Minus', 0], '_': ['Minus', 1], '&': ['Digit7', 1] };
  const fire = (o) => document.body.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...o }));
  for (const ch of text) {
    let code, shift = false;
    if (/[a-z]/.test(ch)) code = 'Key' + ch.toUpperCase(); else if (/[A-Z]/.test(ch)) { code = 'Key' + ch; shift = true; }
    else if (/[0-9]/.test(ch)) code = 'Digit' + ch; else if (P[ch]) { code = P[ch][0]; shift = !!P[ch][1]; }
    const i = US.indexOf(ch); fire({ key: i >= 0 ? RU[i] : ch, code, shiftKey: shift });
  }
  fire({ key: 'Enter', code: 'Enter' });
}, text);
const R = []; const ok = (n, c, d = '') => { R.push({ test: n, ok: !!c, detail: String(d).slice(0, 300) }); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? ' — ' + d : '')); };
const DENY = () => { if (navigator.mediaDevices) navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('Permission denied', 'NotAllowedError')); };

// staging preview yangilanguncha kutamiz (Cloudflare deploy)
const SITE_DIR = process.env.SITE_DIR;   // feature/checkin nusxasi: deploy qilingan fayllar u bilan bir xil bo'lguncha kutamiz
const want = SITE_DIR ? ['assets/common/scanner.js', 'assets/checkin/app.js', 'assets/inventory/app.js'].map((f) => [f, fs.readFileSync(SITE_DIR + '/' + f, 'utf8')]) : [];
for (let i = 0; i < 48; i++) {
  const r = await fetch(STG + '/scan-test', { redirect: 'follow' }).catch(() => null);
  let same = !!(r && r.ok && /scan-test\.js/.test(await r.text()));
  for (const [f, body] of want) { if (!same) break; const x = await fetch(STG + '/' + f + '?v=' + Date.now()).catch(() => null); same = !!(x && x.ok && (await x.text()) === body); }
  if (same) { console.log('staging preview yangilangan (' + (want.length ? 'fayllar mos' : 'scan-test bor') + ')'); break; }
  if (i === 47) { console.log('staging preview yangilanmadi'); process.exit(1); }
  await new Promise((s) => setTimeout(s, 15000));
}
// HTTPS sarlavhalari
for (const p of ['/checkin', '/inventory', '/scan-test']) {
  const r = await fetch(STG + p); const csp = r.headers.get('content-security-policy') || '', pp = r.headers.get('permissions-policy') || '';
  ok(`H ${p}: HTTPS 200, CSP (script-src 'self'), kamera faqat shu sayt, kesh yo'q`, r.ok && r.url.startsWith('https://') && /script-src 'self'/.test(csp) && /frame-ancestors 'none'/.test(csp) && /camera=\(self\)/.test(pp) && /no-store/.test(r.headers.get('cache-control') || ''), r.status + ' ' + pp);
}

const configs = [
  { name: 'iPhone 15 · Safari (WebKit)', type: webkit, dev: devices['iPhone 15'], ios: true },
  { name: 'Pixel 7 · Chrome (Chromium)', type: chromium, dev: devices['Pixel 7'], ios: false }
];
for (const c of configs) {
  const tag = c.ios ? 'ios' : 'android';
  const launchArgs = c.ios ? {} : { args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--use-file-for-fake-video-capture=' + MEDIA + '/qr_05000.y4m'] };
  const br = await c.type.launch(launchArgs).catch((e) => { ok(`${c.name}: brauzer ishga tushdi`, false, e.message); return null; });
  if (!br) continue;
  // 1) eski QR'lar production'da shu qurilmada (faqat o'qish)
  {
    const ctx = await br.newContext({ ...c.dev }); const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message));
    for (const u of ['/?code=00330', '/ticket?code=06114', 'https://ravshanrakhmatullaev.github.io/dusel/?code=11222']) {
      const url = u.startsWith('http') ? u : PROD + u;
      await p.goto(url, { waitUntil: 'load' });
      await p.waitForFunction(() => document.getElementById('ticket')?.classList.contains('done'), null, { timeout: 20000 }).catch(() => {});
      const n = ((await p.textContent('#srnum').catch(() => '')) || '').replace(/\D/g, '');
      ok(`${c.name}: eski QR ${url.replace(/^https:\/\//, '')} → № ${n}`, n === url.slice(-5), n);
    }
    await p.screenshot({ path: `${out}/${tag}_old_qr.png` });
    ok(`${c.name}: bilet sahifalarida JS xatosi yo'q`, errs.length === 0, errs.join('|'));
    await ctx.close();
  }
  // 2) /scan-test: HTTPS xavfsiz kontekst, kamera, tashqi skaner, kirill tartibi
  {
    const ctx = await br.newContext({ ...c.dev, ...(c.ios ? {} : { permissions: ['camera'] }) }); const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message));
    await p.goto(STG + '/scan-test'); await p.waitForSelector('#env dt');
    const secure = await p.evaluate(() => window.isSecureContext);
    const res = await p.waitForSelector('.result .big', { timeout: 15000 }).then((e) => e.textContent()).catch(() => '');
    const camStatus = await p.textContent('#camstatus').catch(() => '');
    const help = await p.locator('.camhelp').getAttribute('data-code').catch(() => null);
    await p.screenshot({ path: `${out}/${tag}_scan_test_camera.png`, fullPage: true });
    if (c.ios) ok(`${c.name}: HTTPS xavfsiz kontekst; kamera natijasi qayd etildi (WebKit emulyatsiyasida kamera qurilmasi yo'q bo'lishi mumkin)`, secure && (/05000/.test(res) || help || /Kamera/.test(camStatus)), `secure=${secure} help=${help} status=${camStatus}`);
    else ok(`${c.name}: HTTPS orqali kamera QR'ni o'qidi (05000)`, secure && /05000/.test(res), res + ' | ' + camStatus);
    await p.evaluate(() => document.activeElement && document.activeElement.blur());
    await p.keyboard.type('https://dusel.pages.dev/gal?code=0007', { delay: 5 }); await p.keyboard.press('Enter');
    const w1 = await p.locator('.result .big').first().textContent();
    await p.evaluate(() => document.activeElement && document.activeElement.blur());
    await scanAsRuKeyboard(p, 'https://dusel.pages.dev/ticket?code=06114');
    const w2 = await p.locator('.result .big').first().textContent();
    await p.fill('#manual', '11223'); await p.click('#f button'); const w3 = await p.locator('.result .big').first().textContent();
    await p.screenshot({ path: `${out}/${tag}_scan_test_scanner.png`, fullPage: true });
    ok(`${c.name}: tashqi skaner — kupon rad, kirill tartibidagi /ticket URL tiklandi (06114), 11223 rad`, /KUPON/.test(w1) && /06114/.test(w2) && /Diapazon/.test(w3), [w1, w2, w3].join(' | '));
    ok(`${c.name}: /scan-test JS xatosiz`, errs.length === 0, errs.join('|'));
    await ctx.close();
  }
  // 3) kamera ruxsati rad etilsa — platformaga mos yo'riqnoma va tiklash tugmasi
  {
    const ctx = await br.newContext({ ...c.dev }); await ctx.addInitScript(DENY); const p = await ctx.newPage();
    await p.goto(STG + '/scan-test'); await p.waitForSelector('.camhelp', { timeout: 15000 }).catch(() => {});
    const help = await p.locator('.camhelp').textContent().catch(() => '');
    await p.screenshot({ path: `${out}/${tag}_camera_denied.png`, fullPage: true });
    ok(`${c.name}: ruxsat rad etilsa — ${c.ios ? '«aA» → Veb-sayt sozlamalari' : 'qulf → Ruxsatlar'} yo'riqnomasi + «Kamerani qayta yoqish»`,
       /ruxsat berilmagan/i.test(help) && help.includes(c.ios ? 'aA' : 'Ruxsatlar') && /qayta yoqish/.test(help), help.slice(0, 100));
    await ctx.close();
  }
  // 4) /checkin va /inventory haqiqiy Cloudflare CSP ostida (server sozlanmagan — "faollashtirilmagan")
  {
    const ctx = await br.newContext({ ...c.dev }); const p = await ctx.newPage(); const errs = [], cons = [];
    p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error') cons.push(m.text()); });
    for (const path of ['/checkin', '/inventory']) {
      await p.goto(STG + path); await p.waitForSelector('main h1');
      const h = await p.textContent('main h1');
      ok(`${c.name}: ${path} HTTPS + CSP ostida yuklanadi (${h.trim()})`, /faollashtirilmagan/i.test(h) && errs.length === 0 && cons.length === 0, errs.concat(cons).join('|'));
    }
    await ctx.close();
  }
  await br.close();
}
fs.writeFileSync(out + '/devices_results.json', JSON.stringify(R, null, 1));
console.log(`\n${R.filter((r) => r.ok).length}/${R.length} PASS`);
process.exit(R.every((r) => r.ok) ? 0 : 1);
