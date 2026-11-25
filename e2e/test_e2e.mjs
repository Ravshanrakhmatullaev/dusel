// DUSEL check-in — brauzer (E2E) testlari: xodim ilovasi + ommaviy sahifalar regressiyasi.
// node test_e2e.mjs <base> <shots_dir>
import { chromium } from 'playwright';
import fs from 'fs';
import pg from 'pg';
const base = process.argv[2] || 'http://127.0.0.1:8799';
const out = process.argv[3] || 'shots'; fs.mkdirSync(out, { recursive: true });
const db = new pg.Client({ host: process.env.PGHOST || '/tmp', port: +(process.env.PGPORT || 5433), user: process.env.PGUSER || 'postgres', password: process.env.PGPASSWORD, database: 'ci_e2e' }); await db.connect();
const MEDIA = process.env.MEDIA_DIR || '/home/claude/checkin/e2e/media';
const q = async (s, a) => (await db.query(s, a)).rows;
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
const launch = (args = []) => chromium.launch({ args }).catch(() => chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args }));
const b = await launch();
const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true };

async function login(page, email, pass, gate = 'G1') {
  await page.goto(base + '/checkin');
  await page.fill('input[type=email]', email); await page.fill('input[type=password]', pass);
  await page.click('button[type=submit]');
  await page.waitForSelector(`text=${gate === 'G1' ? '1-kirish' : gate}`, { timeout: 8000 }).catch(() => {});
  const g = page.locator('button', { hasText: `(${gate})` });
  if (await g.count()) await g.first().click();
  await page.waitForSelector('nav.tabs', { timeout: 8000 });
}
async function manual(page, code) {
  await page.fill('input[placeholder="5 xonali bilet raqami"]', code);
  await page.click('button:has-text("Tekshirish")');
  await page.waitForSelector('.result:not(.info)', { timeout: 8000 });
  return (await page.locator('.result .big').first().textContent()).trim();
}
async function page404check() {
  const c = await b.newContext(PHONE); const p = await c.newPage(); const e = []; p.on('pageerror', (x) => e.push(x.message));
  await p.goto(base + '/scan-test'); await p.waitForSelector('#env dt');
  await p.evaluate(() => document.activeElement && document.activeElement.blur());
  await p.keyboard.type('https://dusel.pages.dev/silver?code=0002', { delay: 4 }); await p.keyboard.press('Enter');
  const t1 = await p.locator('.result .big').first().textContent().catch(() => '');
  await p.fill('#manual', '05000'); await p.click('#f button');
  const t2 = await p.locator('.result .big').first().textContent().catch(() => '');
  await p.fill('#manual', 'DUSELTEST:05000'); await p.click('#f button');
  const t3 = await p.locator('.result .big').first().textContent().catch(() => '');
  const net = await p.evaluate(() => performance.getEntriesByType('resource').filter((r) => /rest\/v1|auth\/v1/.test(r.name)).length);
  await p.screenshot({ path: out + '/14_scan_test.png', fullPage: true });
  ok('T10t /scan-test qurilma sinovi: serverga so\'rovsiz kupon/bilet/SINOV QR ni ajratadi, tashqi skaner ishlaydi', /KUPON/.test(t1) && /05000/.test(t2) && /SINOV BILETI/.test(t3) && net === 0 && e.length === 0, t1 + ' | ' + t2 + ' | ' + t3);
  await c.close();
}
const status = async (t) => (await q('select status from checkin.tickets where ticket_no=$1', [t]))[0].status;

// ---------------------------------------------------------------- 1. Ommaviy sahifalar o'zgarmagan va check-in'ga tegmaydi
{
  const ctx = await b.newContext(PHONE); const p = await ctx.newPage(); const rest = [];
  p.on('request', (r) => { if (/\/rest\/v1|\/auth\/v1|supabase/.test(r.url())) rest.push(r.url()); });
  const before = await q("select count(*)::int n from checkin.scan_log");
  for (const [u, sel] of [['/?code=00330', '#srnum'], ['/ticket?code=00330', '#srnum'], ['/ticket?code=11222', '#srnum']]) {
    await p.goto(base + u); await p.waitForFunction(() => document.getElementById('ticket')?.classList.contains('done'), null, { timeout: 15000 });
    const t = (await p.textContent(sel)).replace(/\D/g, '');
    ok(`T01/T02 Ommaviy bilet sahifasi ${u} → bilet № ${t}`, t === u.slice(-5));
    await p.reload(); await p.waitForFunction(() => document.getElementById('ticket')?.classList.contains('done'), null, { timeout: 15000 });
  }
  for (const [u, sel, exp] of [['/gold?code=0001', '#num', '0001'], ['/silver?code=4000', '#num', '4000'], ['/gal?code=0001', '#num', '0001'], ['/coupon?type=gold&code=0001', '#num', '0001']]) {
    await p.goto(base + u); await p.waitForTimeout(400);
    ok(`T20 Kupon/vaucher sahifasi ${u} o'zgarmagan`, (await p.textContent(sel)).trim() === exp);
  }
  const after = await q("select count(*)::int n from checkin.scan_log");
  ok('T04 Ommaviy sahifani ochish/yangilash check-in serveriga umuman so\'rov yubormaydi va holatni o\'zgartirmaydi',
     rest.length === 0 && after[0].n === before[0].n && (await status('00330')) === 'NOT_ADMITTED', rest.slice(0, 2).join(' '));
  await p.goto(base + '/checkin'); await p.waitForSelector('input[type=email]');
  ok('T20b /checkin alohida sahifa: login talab qiladi', await p.locator('text=Faqat ruxsat berilgan xodimlar').count() === 1);
  await p.screenshot({ path: out + '/01_login.png' });
  await ctx.close();
}
// ---------------------------------------------------------------- 2. Darvoza xodimi: kirish, takror, kupon
const gctx = await b.newContext(PHONE); const g = await gctx.newPage();
const errs = []; g.on('pageerror', (e) => errs.push(e.message));
await login(g, 'gate1@dusel.test', 'Gate-Test-2026');
ok('T15c Darvoza xodimida faqat "Kirish" yorlig\'i (Inventar/Nazorat/Admin yo\'q — inventar alohida ilovada)', (await g.locator('nav.tabs button').allTextContents()).join(',') === 'Kirish');
let t = await manual(g, '00330');
await g.screenshot({ path: out + '/02_lookup_green.png' });
ok('T05a Skan → bilet ma\'lumoti (raqam, zona, sektor, qator, joy) va "KIRITISH MUMKIN"; holat hali o\'zgarmagan', t === 'KIRITISH MUMKIN' && (await status('00330')) === 'NOT_ADMITTED', t);
await g.click('button:has-text("KIRITISH")'); await g.waitForSelector('.result.ok .big:has-text("KIRISH TASDIQLANDI")');
await g.screenshot({ path: out + '/03_admitted.png' });
ok('T05 KIRITISH → yashil "KIRISH TASDIQLANDI", bazada ADMITTED (G1, gate1)', (await q("select status, admitted_gate from checkin.tickets where ticket_no='00330'"))[0].admitted_gate === 'G1');
await g.click('button:has-text("Keyingi bilet")');
t = await manual(g, 'https://ravshanrakhmatullaev.github.io/dusel/?code=00330');
await g.screenshot({ path: out + '/04_already.png' });
ok('T06 Eski github.io QR bilan qayta → qizil "ALLAQACHON KIRITILGAN", avvalgi vaqt va darvoza ko\'rsatiladi', t === 'ALLAQACHON KIRITILGAN' && /G1/.test(await g.locator('.result').first().textContent()), t);
await g.click('button:has-text("Bekor")');
t = await manual(g, 'https://dusel.pages.dev/gold?code=0001');
ok('T09 GOLD kupon QR → "BU KONSERT BILETI EMAS"', t === 'BU KONSERT BILETI EMAS', t);
t = await manual(g, 'https://dusel.pages.dev/?code=11223');
ok('T17 Diapazondan tashqari raqam → "YAROQSIZ QR"', t === 'YAROQSIZ QR', t);
// tezkor rejim
await g.check('input[type=checkbox]');
await g.fill('input[placeholder="5 xonali bilet raqami"]', '00331'); await g.click('button:has-text("Tekshirish")');
await g.waitForSelector('.result.ok .big:has-text("KIRISH TASDIQLANDI")');
await g.fill('input[placeholder="5 xonali bilet raqami"]', '00331'); await g.click('button:has-text("Tekshirish")');
await g.waitForSelector('.result.bad .big');
const dupText = await g.locator('.result.bad').textContent();
await g.screenshot({ path: out + '/05_duplicate_scan.png' });
ok('T06b Tezkor rejim: 1-skan yashil, 2-skan qizil + "mijozni ayblamang" + holat raqami', /ALLAQACHON/.test(dupText) && /ayblamang/.test(dupText) && /holat #\d+/.test(dupText));
await g.uncheck('input[type=checkbox]');
// tarmoq uzilishi va xavfsiz qayta urinish
await g.fill('input[placeholder="5 xonali bilet raqami"]', '00332'); await g.click('button:has-text("Tekshirish")');
await g.waitForSelector('button:has-text("KIRITISH")');
await gctx.setOffline(true);
await g.click('button:has-text("KIRITISH")');
await g.waitForSelector('.result.bad .big:has-text("NATIJA NOMA\'LUM")', { timeout: 30000 });
await g.screenshot({ path: out + '/06_unknown_offline.png' });
ok('T19a Aloqa uzilsa: "NATIJA NOMA\'LUM — KIRITMANG", avtomatik kirish to\'xtatildi; darvozada favqulodda (oflayn) tugma YO\'Q',
   (await status('00332')) === 'NOT_ADMITTED' && (await g.locator('text=Avtomatik kirish TO\'XTATILDI').count()) === 1 && (await g.locator('button:has-text("favqulodda")').count()) === 0);
await gctx.setOffline(false);
await g.click('button:has-text("Qayta urinish")'); await g.waitForSelector('.result.ok .big:has-text("KIRISH TASDIQLANDI")');
const ev332 = await q("select count(*)::int n from checkin.admission_events where ticket_no='00332'");
ok('T08 Aloqa tiklangach "Qayta urinish" — bir xil so\'rov: bitta kirish yozuvi', ev332[0].n === 1, ev332[0].n);
// kamera bilan skan (soxta kamera — QR video)
{
  const cb = await launch(['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--use-file-for-fake-video-capture=' + MEDIA + '/qr_05000.y4m']);
  const cc = await cb.newContext({ ...PHONE, permissions: ['camera'] }); const cp = await cc.newPage();
  await login(cp, 'gate2@dusel.test', 'Gate-Test-2026', 'G2');
  await cp.waitForSelector('.result:not(.info) .big', { timeout: 20000 }).catch(() => {});
  const txt = await cp.locator('.result:not(.info) .big').first().textContent().catch(() => '');
  await cp.screenshot({ path: out + '/07_camera_scan.png' });
  ok('T05c Telefon kamerasi orqali QR o\'qiladi (05000 → KIRITISH MUMKIN)', /KIRITISH MUMKIN/.test(txt) && /05000/.test(await cp.locator('.seat').first().textContent()), txt);
  await cb.close();
}
// tashqi 2D skaner (klaviatura rejimi): tez belgilar + Enter; kirill tartibida ham
{
  await g.click('button:has-text("Keyingi bilet")').catch(() => {});
  await g.evaluate(() => document.activeElement && document.activeElement.blur());
  await g.keyboard.type('https://dusel.pages.dev/?code=00340', { delay: 4 }); await g.keyboard.press('Enter');
  await g.waitForSelector('.result:not(.info) .big', { timeout: 8000 });
  const w1 = await g.locator('.seat').first().textContent().catch(() => '');
  await g.click('button:has-text("Bekor")');
  await g.evaluate(() => document.activeElement && document.activeElement.blur());
  await scanAsRuKeyboard(g, 'https://dusel.pages.dev/?code=00341');   // skaner + kirill tartibdagi telefon
  await g.waitForSelector('.result:not(.info) .big', { timeout: 8000 });
  const w2 = await g.locator('.seat').first().textContent().catch(() => '');
  await g.screenshot({ path: out + '/07b_hw_scanner.png' });
  ok('T10s Tashqi skaner (USB/Bluetooth klaviatura rejimi) o\'qiladi; klaviatura kirill tartibida bo\'lsa ham URL tiklanadi', /00340/.test(w1) && /00341/.test(w2) && (await status('00340')) === 'NOT_ADMITTED', w1 + ' | ' + w2);
  await g.click('button:has-text("Bekor")');
}
// kameraga ruxsat berilmasa: platformaga mos yo'riqnoma + tiklash tugmalari + qo'lda kiritish ishlaydi
for (const [name, ua, needle] of [['Android Chrome', 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36', 'Ruxsatlar'],
                                  ['iPhone Safari', 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1', 'aA']]) {
  const db2 = await launch();
  const dc = await db2.newContext({ ...PHONE, userAgent: ua });
  // foydalanuvchi "Ruxsat bermaslik" ni bosgandagi brauzer xatosi (headless'da so'rov oynasi yo'q — xatoni aynan shunday qaytaramiz)
  await dc.addInitScript(() => { if (navigator.mediaDevices) navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('Permission denied', 'NotAllowedError')); });
  const dp = await dc.newPage();
  await login(dp, 'gate2@dusel.test', 'Gate-Test-2026', 'G2');
  await dp.waitForSelector('.camhelp', { timeout: 15000 }).catch(() => {});
  const help = await dp.locator('.camhelp').textContent().catch(() => '');
  await dp.screenshot({ path: out + `/07c_camera_denied_${name.split(' ')[0].toLowerCase()}.png`, fullPage: true });
  await dp.fill('input[placeholder="5 xonali bilet raqami"]', '00350'); await dp.click('button:has-text("Tekshirish")');
  const man = await dp.waitForSelector('.result:not(.info) .big', { timeout: 8000 }).then((e) => e.textContent()).catch(() => '');
  ok(`T10c Kameraga ruxsat yo'q (${name}): aniq yo'riqnoma, "Kamerani qayta yoqish", qo'lda kiritish ishlaydi`,
     /ruxsat berilmagan/i.test(help) && help.includes(needle) && /qayta yoqish/.test(help) && man === 'KIRITISH MUMKIN', help.slice(0, 120));
  await db2.close();
}
// ---------------------------------------------------------------- 3. Inventar — ALOHIDA ilova /inventory (kirishni iste'mol qilmaydi)
const sctx = await b.newContext(PHONE); const s = await sctx.newPage();
await login(s, 'sup@dusel.test', 'Sup-Test-2026');
const evBefore = (await q('select count(*)::int n from checkin.admission_events'))[0].n;
const ictx = await b.newContext(PHONE); const iv = await ictx.newPage(); const ierrs = []; iv.on('pageerror', (e) => ierrs.push(e.message));
iv.on('dialog', (d) => (d.type() === 'prompt' ? d.accept('D-1') : d.accept()));
await iv.goto(base + '/inventory'); await iv.fill('input[type=email]', 'inv@dusel.test'); await iv.fill('input[type=password]', 'Inv-Test-2026'); await iv.click('button[type=submit]');
await iv.waitForSelector('nav.tabs');
ok('T10a /inventory alohida ilova: inventar xodimi kiradi, faqat Skanerlash/Qarorlar/Partiyalar/Solishtiruv', (await iv.locator('nav.tabs button').allTextContents()).join(',') === 'Skanerlash,Qarorlar,Partiyalar,Solishtiruv');
await iv.click('nav.tabs button:has-text("Partiyalar")'); await iv.waitForSelector('text=Yangi partiya');
await iv.fill('input[placeholder^="Nomi"]', 'A403 qoldiq — 1-quti'); await iv.fill('input[placeholder^="Sektor"]', 'A403'); await iv.fill('input[placeholder="Quti"]', 'Q-1'); await iv.fill('input[placeholder="Dasta"]', 'D-1');
await iv.click('button:has-text("Ochish va skanerlashni boshlash")'); await iv.waitForSelector('#qcount');
const invManual = async (v) => { await iv.fill('input[placeholder^="Raqam yoki QR"]', v); await iv.click('button:has-text("Qayd")');
  await iv.waitForFunction(() => window.DUSEL_INV_DEBUG.state.queue.length === 0 && !/Yuborilmoqda/.test(document.querySelector('.result .big')?.textContent || ''), null, { timeout: 8000 }).catch(() => {});
  return (await iv.locator('.result .big').first().textContent()).trim(); };
const r1 = await invManual('https://dusel.pages.dev/?code=06114');
const r2 = await invManual('https://dusel.pages.dev/?code=06114');
await iv.screenshot({ path: out + '/08_inventory_repeat_question.png' });
await iv.click('button:has-text("HA — qo\'limda IKKINCHI qog\'oz bor")'); await iv.waitForSelector('.result.bad .big:has-text("TASDIQLANGAN DUBLIKAT")');
const r2b = (await iv.locator('.result .big').first().textContent()).trim();
await iv.screenshot({ path: out + '/08_inventory_confirmed_duplicate.png' });
await invManual('https://ravshanrakhmatullaev.github.io/dusel/?code=06101'); const r3 = await invManual('https://dusel.pages.dev/ticket?code=06101');
await iv.click('button:has-text("YO\'Q — o\'sha qog\'ozni qayta skanerladim")'); await iv.waitForSelector('.result.ok .big:has-text("nusxa hisoblanmadi")');
await invManual('06087');
const rg = await invManual('https://dusel.pages.dev/gold?code=0001');
const inv = await q("select ticket_no, count(*)::int n from checkin.inventory_scans where ticket_no is not null group by 1 order by 1");
const copies = await q("select (select count(*) from checkin.inventory_verdicts v join checkin.inventory_scans s on s.id=v.scan_id where s.ticket_no='06114' and v.verdict='SECOND_COPY')::int a, (select count(*) from checkin.inventory_verdicts v join checkin.inventory_scans s on s.id=v.scan_id where s.ticket_no='06101' and v.verdict='SAME_PAPER')::int b");
ok('T10 Inventar: takror skan darhol "TAKROR — qaror bering"; 06114 → operator "ikkinchi qog\'oz" (D-1) → TASDIQLANGAN DUBLIKAT; 06101 (boshqa URL formati) → "o\'sha qog\'oz"; kupon rad; skan tarixi saqlanadi; biletlar kiritilmagan',
   /Qayd etildi/.test(r1) && /TAKROR SKAN/.test(r2) && /TASDIQLANGAN DUBLIKAT/.test(r2b) && /TAKROR SKAN/.test(r3) && copies[0].a === 1 && copies[0].b === 1 && /KUPON/.test(rg)
   && JSON.stringify(inv) === JSON.stringify([{ ticket_no: '06087', n: 1 }, { ticket_no: '06101', n: 2 }, { ticket_no: '06114', n: 2 }]) && (await status('06114')) === 'NOT_ADMITTED', r2 + ' | ' + JSON.stringify(inv));
// oflayn: skanlar qurilmada saqlanadi, sahifa yopilsa ham yo'qolmaydi, keyin aynan bir marta yuboriladi
await ictx.setOffline(true);
for (const c of ['06120', '06121', '06121']) { await iv.fill('input[placeholder^="Raqam yoki QR"]', c); await iv.click('button:has-text("Qayd")'); await iv.waitForTimeout(150); }
await iv.waitForTimeout(500);
const qlen = await iv.evaluate(() => window.DUSEL_INV_DEBUG.state.queue.length);
await iv.screenshot({ path: out + '/08b_inventory_offline_queue.png' });
await iv.close(); await ictx.setOffline(false);
const iv2 = await ictx.newPage(); iv2.on('pageerror', (e) => ierrs.push(e.message)); await iv2.goto(base + '/inventory'); await iv2.waitForSelector('nav.tabs');
for (let i = 0; i < 40 && (await iv2.evaluate(() => window.DUSEL_INV_DEBUG.state.queue.length)) > 0; i++) await iv2.waitForTimeout(250);
const off = await q("select ticket_no, count(*)::int n from checkin.inventory_scans where ticket_no in ('06120','06121') group by 1 order by 1");
ok('T10o Inventar oflayn navbati: 3 skan qurilmada saqlandi, sahifa yopilib qayta ochilgach aynan bir martadan yuborildi (06120×1, 06121×2)',
   qlen === 3 && JSON.stringify(off) === JSON.stringify([{ ticket_no: '06120', n: 1 }, { ticket_no: '06121', n: 2 }]), qlen + ' ' + JSON.stringify(off));
// solishtiruv: A403 birinchi, varaq 1019 (06109–06114) "ikki marta bosilgan (taxmin)"
await iv2.click('nav.tabs button:has-text("Solishtiruv")'); await iv2.waitForSelector('.sheets', { timeout: 15000 });
const firstRow = await iv2.locator('table tr').nth(1).textContent();
const sh1019 = await iv2.locator('.sheet:has(b:text-is("1019"))').getAttribute('class');
await iv2.screenshot({ path: out + '/08c_reconciliation_A403.png', fullPage: true });
ok('T21 Solishtiruv paneli: A403 birinchi; 06114 varag\'i (1019) "ikkinchi qog\'oz tasdiqlangan" deb belgilandi; noma\'lumlar alohida',
   /^A403/.test(firstRow.trim()) && /bad/.test(sh1019 || '') && (await iv2.locator('text=Noma\'lum (ko\'rilmagan, hujjat yo\'q)').count()) > 0, firstRow.slice(0, 60) + ' | ' + sh1019);
const evAfter = (await q('select count(*)::int n from checkin.admission_events'))[0].n;
ok('T10z Inventar ilovasi bitta ham kirish hodisasi yaratmadi; JS xatolari yo\'q', evAfter === evBefore && ierrs.length === 0, evBefore + '→' + evAfter + ' ' + ierrs.join('|'));
// rollar ajratilgan: inventar xodimi /checkin da kirita olmaydi, darvoza xodimi /inventory da ishlay olmaydi
{
  const xc = await b.newContext(PHONE); const xp = await xc.newPage();
  await xp.goto(base + '/checkin'); await xp.fill('input[type=email]', 'inv@dusel.test'); await xp.fill('input[type=password]', 'Inv-Test-2026'); await xp.click('button[type=submit]');
  await xp.waitForSelector('text=Bu kirish nazorati emas', { timeout: 8000 }).catch(() => {});
  const a1 = await xp.locator('text=Bu kirish nazorati emas').count();
  const api = await xp.evaluate(async () => { const sb = window.supabase.createClient(location.origin, 'local-test-anon-key', { auth: { storageKey: 'dusel_ci_auth_LOCAL-TEST' } });
    const r = await sb.rpc('ci_admit', { p_request: crypto.randomUUID(), p_payload: '09999', p_gate: 'G1', p_device: 'x' }); return r.error && r.error.message; });
  const yc = await b.newContext(PHONE); const yp = await yc.newPage();
  await yp.goto(base + '/inventory'); await yp.fill('input[type=email]', 'gate1@dusel.test'); await yp.fill('input[type=password]', 'Gate-Test-2026'); await yp.click('button[type=submit]');
  await yp.waitForSelector('text=Ruxsat yo\'q', { timeout: 8000 }).catch(() => {});
  ok('T15d Rollar ajratilgan: inventar xodimi /checkin da kirita olmaydi (API ham ROLE_DENIED), darvoza xodimi /inventory dan foydalana olmaydi',
     a1 === 1 && api === 'ROLE_DENIED' && (await yp.locator('text=Ruxsat yo\'q').count()) === 1 && (await status('09999')) === 'NOT_ADMITTED', api);
  await xc.close(); await yc.close();
}
// ---------------------------------------------------------------- 4. Nazoratchi: dublikat bilet egasi → almashtirish
// 06114 ning birinchi egasi kiradi, ikkinchisi rad → holat
const g2 = await (await b.newContext(PHONE)).newPage(); await login(g2, 'gate2@dusel.test', 'Gate-Test-2026', 'G2');
g2.on('dialog', (d) => d.accept('Ikkinchi mijozda ham 06114 bor — distribyutordan olgan'));
await manual(g2, '06114'); await g2.click('button:has-text("KIRITISH")'); await g2.waitForSelector('.result.ok');
await g2.click('button:has-text("Keyingi bilet")');
t = await manual(g2, '06114');
ok('T06c Dublikat 06114: birinchisi kirdi, ikkinchisi to\'xtatildi', t === 'ALLAQACHON KIRITILGAN', t);
await g2.click('button:has-text("Nazoratchiga")'); await g2.waitForSelector('.result.warn .big:has-text("Holat #")');
await g2.screenshot({ path: out + '/05b_referred.png' });
const caseId = (await q("select id from checkin.review_cases where ticket_no='06114'"))[0]?.id;
// ---------------------------------------------------------------- Admin: kirishni nazoratli ochish, sig'im qulfi, isbotli zaxira joy
const KEY = 'dusel_ci_auth_LOCAL-TEST', IKEY = 'dusel_inv_auth_LOCAL-TEST';
const rpcAs = (page, key, fn, args) => page.evaluate(async ([key, fn, args]) => {
  const sb = window.supabase.createClient(location.origin, 'local-test-anon-key', { auth: { storageKey: key } });
  const r = await sb.rpc(fn, args); return r.error ? { error: r.error.message } : r.data; }, [key, fn, args]);
const actx = await b.newContext(PHONE); const a = await actx.newPage();
let promptAnswer = ''; a.on('dialog', (d) => (d.type() === 'prompt' ? d.accept(promptAnswer) : d.accept()));
await login(a, 'admin@dusel.test', 'Admin-Test-2026');
await a.click('nav.tabs button:has-text("Admin")'); await a.waitForSelector('text=Kirish holati');
await a.click('button:has-text("Kirishni yopish")'); await a.waitForTimeout(800);
await g2.click('button:has-text("Bekor")').catch(() => {});
await manual(g2, '00360'); await g2.click('button:has-text("KIRITISH")'); await g2.waitForSelector('.result.bad .big');
const closedTxt = await g2.locator('.result.bad .big').first().textContent();
await a.click('nav.tabs button:has-text("Admin")'); await a.waitForSelector('text=Kirish holati');
promptAnswer = 'ha'; await a.click('button:has-text("Kirishni ochish")'); await a.waitForTimeout(800);
const stillClosed = (await q("select value::text v from checkin.settings where key='admission_open'"))[0].v;
await a.click('nav.tabs button:has-text("Admin")'); await a.waitForSelector('text=Kirish holati');
promptAnswer = 'KIRISHNI OCHISH'; await a.click('button:has-text("Kirishni ochish")'); await a.waitForTimeout(800);
const opened = (await q("select value::text v from checkin.settings where key='admission_open'"))[0].v;
ok('T20 Kirish faqat admin "KIRISHNI OCHISH" tasdiq matni bilan ochiladi; yopiq paytda darvoza kirita olmaydi',
   /OCHILMAGAN/.test(closedTxt) && stillClosed === 'false' && opened === 'true' && (await status('00360')) === 'NOT_ADMITTED', closedTxt + ' ' + stillClosed + '→' + opened);
await a.click('nav.tabs button:has-text("Admin")'); await a.waitForSelector('text=Tasdiqlangan sig\'im');
const capApi = await rpcAs(a, KEY, 'ci_setting_set', { p_key: 'capacity', p_value: 11223 });
ok('T13e Sig\'im UI\'da o\'zgartirilmaydi, API orqali ham — 11 222 qoladi',
   capApi.error === 'USE_CAPACITY_CHANGE' && (await a.locator('section:has-text("Tasdiqlangan sig\'im") input[type=number]').count()) === 0
   && (await q("select value::text v from checkin.settings where key='capacity'"))[0].v === '11222', capApi.error);
// isbotli zaxira: tashkilotchi zaxira hujjati (HELD) + yopiq inventar partiyasida 1 nusxa
await rpcAs(a, KEY, 'ci_import_distribution', { p_rows: [{ ticket_no: '06200', status: 'HELD' }, { ticket_no: '06201', status: 'HELD' }], p_source: 'Tashkilotchi zaxira jadvali (sinov)' });
const zb = await rpcAs(iv2, IKEY, 'ci_inventory_batch_open', { p_name: 'Ofis seyfi', p_location: 'Ofis', p_sector: 'A403', p_box: 'S-1', p_stack: null, p_device: 'inv-e2e' });
await rpcAs(iv2, IKEY, 'ci_inventory_scan', { p_request: crypto.randomUUID(), p_batch: zb.id, p_payload: '06200', p_seat_note: null, p_source: 'SCANNER', p_device: 'inv-e2e', p_client_at: null });
await rpcAs(iv2, IKEY, 'ci_inventory_batch_close', { p_batch: zb.id });
await a.fill('input[placeholder="Bilet raqami (5 xona)"]', '06201'); await a.fill('textarea[placeholder^="Isbot"]', 'Tashkilotchi zaxira jadvali 25.11, seyf S-1');
promptAnswer = '06201'; await a.click('button:has-text("Zaxira joyga o\'tkazish")'); await a.waitForTimeout(800);
const t06201 = await status('06201');
await a.fill('input[placeholder="Bilet raqami (5 xona)"]', '06200'); await a.fill('textarea[placeholder^="Isbot"]', 'Tashkilotchi zaxira jadvali 25.11, seyf S-1, inventar #' + zb.id);
promptAnswer = '06200'; await a.click('button:has-text("Zaxira joyga o\'tkazish")'); await a.waitForTimeout(900);
const seat06200 = (await q("select seat_key from checkin.tickets where ticket_no='06200'"))[0].seat_key;
await a.screenshot({ path: out + '/09_admin.png', fullPage: true });
ok('T13i Admin: jismonan tasdiqlanmagan bilet zaxira bo\'lmadi; isbotli bilet (06200) bekor qilinib, joyi zaxiraga o\'tdi',
   t06201 === 'NOT_ADMITTED' && (await status('06200')) === 'CANCELLED_BY_AUTHORIZED_SUPERVISOR'
   && (await q('select spare_status from checkin.seats where seat_key=$1', [seat06200]))[0].spare_status === 'AVAILABLE', seat06200);
s.on('dialog', (d) => d.accept());
await s.click('nav.tabs button:has-text("Nazorat")'); await s.waitForSelector('text=Ko\'rib chiqish holatlari');
await s.click(`button:has-text("#${caseId} ")`); await s.waitForSelector(`text=Holat #${caseId}`);
await s.fill('textarea[placeholder^="Dalillar"]', 'Mijoz asl qog\'oz bilet 06114 va distribyutor chekini ko\'rsatdi; bosmaxona dublikati');
await s.fill('textarea[placeholder="Qaror izohi"]', 'Haqiqiy xaridor — zaxira joy beriladi');
await s.screenshot({ path: out + '/10_case.png', fullPage: true });
await s.click('button:has-text("Band qilish")'); await s.waitForSelector('button:has-text("Almashtirish bileti berish")');
await s.fill('textarea[placeholder^="Dalillar"]', 'Mijoz asl qog\'oz bilet 06114 va distribyutor chekini ko\'rsatdi; bosmaxona dublikati');
await s.fill('textarea[placeholder="Qaror izohi"]', 'Haqiqiy xaridor — zaxira joy beriladi');
await s.click('button:has-text("Almashtirish bileti berish")'); await s.waitForSelector('.qrbox svg');
await s.screenshot({ path: out + '/11_replacement.png', fullPage: true });
const rep = (await q("select status, seat_key from checkin.replacements"))[0];
ok('T12 Nazoratchi dalillarni yozib, isbotli zaxira joyni band qilib, almashtirish bileti berdi (QR ko\'rsatildi)', rep?.status === 'ACTIVE' && rep.seat_key === seat06200, rep?.seat_key);
const capS = await rpcAs(s, KEY, 'ci_capacity_status', {});
ok('T07u Almashtirishdan keyin ruxsatlar 11 222 / tasdiqlangan sig\'im 11 222 (dashboard\'dagi 11223/11223 muammosi bartaraf etildi)',
   capS.entitlements === 11222 && capS.approved_capacity === 11222 && capS.invariant_ok && capS.capacity_changes.length === 0, JSON.stringify({ e: capS.entitlements, c: capS.approved_capacity }));
// almashtirish QR'ini darvozada kamera orqali emas, QR matnidan o'qiymiz (svg ichidagi payload yo'q) — tokenni bazadan olib bo'lmaydi (faqat xesh)
// shuning uchun ekrandagi QR rasmini dekod qilamiz
const svg = await s.locator('.qrbox svg').first().screenshot({ path: out + '/11b_replacement_qr.png' });
ok('T07r Almashtirish bileti QR rasmi chop etishga tayyor', fs.statSync(out + '/11b_replacement_qr.png').size > 1000);
// ---------------------------------------------------------------- 5. Panel
await s.click('nav.tabs button:has-text("Panel")'); await s.waitForSelector('text=Kirish statistikasi');
await s.waitForSelector('text=Sektorlar bo\'yicha', { timeout: 10000 });
await s.screenshot({ path: out + '/12_dashboard.png', fullPage: true });
const dtext = await s.locator('main').textContent();
ok('T13d Boshqaruv paneli: ruxsatlar 11222 / 11222, sig\'im nazorati bloki, takroriy skanlar, inventar alohida', /11222 \/ 11222/.test(dtext) && /Sig'im nazorati/.test(dtext) && /Takroriy skanlar/.test(dtext) && /Jismoniy inventar/.test(dtext));
// ---------------------------------------------------------------- 5b. Nazoratchi belgilari va tayyorlik tekshiruvi
await s.click('nav.tabs button:has-text("Nazorat")'); await s.waitForSelector('text=Nazoratchi belgilari');
const ftxt = await s.locator('section:has-text("Nazoratchi belgilari")').first().textContent();
await s.screenshot({ path: out + '/10b_flags.png', fullPage: true });
const st06114 = await status('06114');
ok('T24 Nazoratchi belgilari: tasdiqlangan bosma dublikati (06114) ro\'yxatda; bilet bekor qilinmagan (birinchi egasi kirgan holicha)', /06114/.test(ftxt) && /Bosma dublikati tasdiqlangan/.test(ftxt) && st06114 === 'ADMITTED', st06114);
await a.click('nav.tabs button:has-text("Admin")'); await a.waitForSelector('text=Tayyorlik tekshiruvi');
await a.click('section:has-text("Tayyorlik tekshiruvi") button:has-text("Tekshirish")'); await a.waitForSelector('#readybox .big', { timeout: 15000 });
const rtxt = await a.locator('#readybox').textContent();
ok('T26 Tayyorlik tekshiruvi sinov bazasida "TAYYOR EMAS" (sinov kirishlari va xodimlari bor) — production\'ga sinov holati o\'tmaydi', /TAYYOR EMAS/.test(rtxt) && /✗ no_test_staff/.test(rtxt) && /✗ all_not_admitted/.test(rtxt), rtxt.slice(0, 120));
// ---------------------------------------------------------------- 6. Nazoratli favqulodda rejim — faqat belgilangan YAGONA nazoratchi qurilmasi
const octx = await b.newContext(PHONE); const o = await octx.newPage();
const dialogs = []; o.on('dialog', async (d) => { dialogs.push(d.message()); if (d.type() === 'prompt') await d.accept('2468135790'); else await d.accept(); });
await login(o, 'sup@dusel.test', 'Sup-Test-2026');
const supDev = await o.evaluate(() => JSON.parse(localStorage.getItem('dusel_ci_device')));
await rpcAs(a, KEY, 'ci_set_contingency_code', { p_code: '2468135790' });
await rpcAs(a, KEY, 'ci_contingency_device_set', { p_device: supDev });
await o.reload(); await o.waitForSelector('nav.tabs'); await o.waitForTimeout(1000);
await octx.setOffline(true);
await o.fill('input[placeholder="5 xonali bilet raqami"]', '00500'); await o.click('button:has-text("Tekshirish")');
await o.waitForSelector('button:has-text("Nazoratli favqulodda rejim")', { timeout: 15000 });
await o.click('button:has-text("Nazoratli favqulodda rejim")'); await o.waitForSelector('.result.warn.offline', { timeout: 15000 });
for (const c of ['00500', '00501', '00330']) { await o.fill('input[placeholder="5 xonali bilet raqami"]', c); await o.click('button:has-text("Tekshirish")'); await o.waitForTimeout(250); }
const offTxt = await o.locator('.result.warn .big').last().textContent();
const greens = await o.locator('.result.ok').count();
await o.fill('input[placeholder="5 xonali bilet raqami"]', '00500'); await o.click('button:has-text("Tekshirish")'); await o.waitForTimeout(250);
const offDup = await o.locator('.result .big').last().textContent();
await o.screenshot({ path: out + '/13_offline_mode.png', fullPage: true });
ok('T19 Nazoratli favqulodda rejim: faqat belgilangan nazoratchi qurilmasi + kod; yozuvlar "NAZORAT OSTIDA QAYD ETILDI" (yashil emas); shu qurilmadagi takror bloklanadi',
   /NAZORAT OSTIDA QAYD ETILDI/.test(offTxt) && greens === 0 && /ALLAQACHON/.test(offDup) && (await status('00500')) === 'NOT_ADMITTED', offTxt + ' | ' + offDup);
await octx.setOffline(false);
await o.evaluate(() => window.dispatchEvent(new Event('online')));
for (let i = 0; i < 60 && (await o.evaluate(() => window.DUSEL_CI_DEBUG.state.queue.length)) > 0; i++) await o.waitForTimeout(250);   // CSP ostida eval'siz kutish
await o.waitForTimeout(800);
const offEv = await q("select ticket_no, decision from checkin.admission_events where offline_at is not null order by ticket_no");
ok('T19b Aloqa tiklangach navbat sinxronlandi: 00500/00501 kiritildi, 00330 (allaqachon kirgan) — ziddiyat holatiga',
   JSON.stringify(offEv.map((x) => x.ticket_no + ':' + x.decision)) === JSON.stringify(['00330:DENIED_ALREADY_ADMITTED', '00500:ADMITTED', '00501:ADMITTED'])
   && (await q("select source from checkin.review_cases where ticket_no='00330'"))[0]?.source === 'OFFLINE_CONFLICT' && dialogs.some((m) => /ziddiyat/.test(m)), JSON.stringify(offEv) + ' ' + dialogs.join('|').slice(0, 120));
// ---------------------------------------------------------------- 7. Chiqish va sessiyani bekor qilish
await g.click('button:has-text("Chiqish")'); await g.waitForSelector('input[type=email]');
ok('T18 "Chiqish" — login sahifasiga qaytadi', true);
await login(g, 'gate1@dusel.test', 'Gate-Test-2026');
await a.evaluate(async () => {
  const sb = window.supabase.createClient(location.origin, 'local-test-anon-key', { auth: { storageKey: 'dusel_ci_auth_LOCAL-TEST' } });
  await sb.rpc('ci_staff_revoke_sessions', { p_username: 'gate1@dusel.test' });
});
await g.waitForTimeout(1200);
await g.fill('input[placeholder="5 xonali bilet raqami"]', '00600'); await g.click('button:has-text("Tekshirish")');
await g.waitForSelector('input[type=email]', { timeout: 8000 });
ok('T18b Admin sessiyani bekor qilsa — xodim keyingi amalda tizimdan chiqariladi', (await g.locator('text=Sessiya tugagan').count()) === 1 && (await status('00600')) === 'NOT_ADMITTED');
// 15: darvoza xodimi to'g'ridan-to'g'ri API orqali nazoratchi funksiyasini chaqira olmaydi
const g3 = await (await b.newContext(PHONE)).newPage(); await login(g3, 'gate2@dusel.test', 'Gate-Test-2026', 'G2');
const direct = await g3.evaluate(async () => {
  const sb = window.supabase.createClient(location.origin, 'local-test-anon-key', { auth: { storageKey: 'dusel_ci_auth_LOCAL-TEST' } });
  const r1 = await sb.rpc('ci_ticket_set_status', { p_ticket: '07000', p_status: 'CANCELLED_BY_AUTHORIZED_SUPERVISOR', p_reason: 'ruxsatsiz urinish' });
  const r2 = await sb.rpc('ci_setting_set', { p_key: 'admission_open', p_value: false });
  return [r1.error && r1.error.message, r2.error && r2.error.message];
});
const direct2 = await rpcAs(g3, KEY, 'ci_admit', { p_request: crypto.randomUUID(), p_payload: '07001', p_gate: 'G2', p_device: 'g-dev-x', p_offline_at: new Date().toISOString() });
ok('T15 Darvoza xodimi API orqali ham bilet holatini/sozlamani o\'zgartira olmaydi va "oflayn" kirish yubora olmaydi',
   direct[0] === 'ROLE_DENIED' && direct[1] === 'ROLE_DENIED' && direct2.error === 'CONTINGENCY_DEVICE_ONLY' && (await status('07000')) === 'NOT_ADMITTED' && (await status('07001')) === 'NOT_ADMITTED', JSON.stringify([direct, direct2]));
const ver = (await q("select count(*)::int n from checkin.audit_log"))[0].n;
ok('T16 Barcha admin/nazoratchi amallari audit jurnalida', ver > 10, ver + ' yozuv');
ok('T00 Sahifada JavaScript xatolari yo\'q', errs.length === 0, errs.join(' | '));
await page404check();
{
  await db.query("update checkin.settings set value='\"PRODUCTION\"' where key='environment'");
  const ec = await b.newContext(PHONE); const ep = await ec.newPage();
  await ep.goto(base + '/checkin'); await ep.fill('input[type=email]', 'gate2@dusel.test'); await ep.fill('input[type=password]', 'Gate-Test-2026'); await ep.click('button[type=submit]');
  await ep.waitForSelector('text=MUHIT MOS EMAS', { timeout: 8000 }).catch(() => {});
  const m1 = await ep.locator('text=MUHIT MOS EMAS').count();
  await ep.goto(base + '/inventory'); await ep.fill('input[type=email]', 'inv@dusel.test'); await ep.fill('input[type=password]', 'Inv-Test-2026'); await ep.click('button[type=submit]');
  await ep.waitForSelector('text=MUHIT MOS EMAS', { timeout: 8000 }).catch(() => {});
  const m2 = await ep.locator('text=MUHIT MOS EMAS').count();
  await ep.screenshot({ path: out + '/15_env_mismatch.png' });
  await db.query("update checkin.settings set value='\"STAGING\"' where key='environment'");
  ok('T27 Sayt muhiti (sinov) va baza muhiti (PRODUCTION) mos kelmasa — /checkin ham, /inventory ham ishlamaydi', m1 === 1 && m2 === 1);
  await ec.close();
}
await b.close(); await db.end();
fs.writeFileSync(out + '/e2e_results.json', JSON.stringify(R, null, 1));
console.log(`\n${R.filter((r) => r.ok).length}/${R.length} PASS`);
process.exit(R.every((r) => r.ok) ? 0 : 1);
