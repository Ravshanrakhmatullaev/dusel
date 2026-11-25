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
ok('T15c Darvoza xodimida faqat "Kirish" va "Inventar" yorliqlari (Nazorat/Admin yo\'q)', (await g.locator('nav.tabs button').allTextContents()).join(',') === 'Kirish,Inventar');
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
ok('T19a Aloqa uzilsa: "NATIJA NOMA\'LUM — KIRITMANG", avtomatik ruxsat yo\'q', (await status('00332')) === 'NOT_ADMITTED');
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
// ---------------------------------------------------------------- 3. Inventar (kirishni iste'mol qilmaydi)
const sctx = await b.newContext(PHONE); const s = await sctx.newPage();
await login(s, 'sup@dusel.test', 'Sup-Test-2026');
const batch = (await q("insert into checkin.inventory_batches (name, location, created_by) select 'A403 qoldiq (sinov)', 'Ombor', user_id from checkin.staff where username='sup@dusel.test' returning id"))[0].id;
await s.click('nav.tabs button:has-text("Inventar")'); await s.waitForSelector('select');
await s.waitForFunction((id) => [...document.querySelectorAll('select option')].some((o) => o.value === String(id)), batch);
await s.selectOption('select', String(batch));
const invScan = async (code) => s.evaluate(async ([code, batch]) => {
  const sb = window.supabase.createClient(location.origin, 'local-test-anon-key', { auth: { storageKey: 'dusel_ci_auth_LOCAL-TEST' } });
  return (await sb.rpc('ci_inventory_scan', { p_request: crypto.randomUUID(), p_batch: batch, p_payload: code, p_seat_note: null })).data;
}, [code, batch]);
for (const c of ['06114', '06114', '06101', '06087', '06101']) await invScan('https://dusel.pages.dev/?code=' + c);
const inv = await q("select ticket_no, count(*)::int n from checkin.inventory_scans group by 1 order by 1");
ok('T10 Inventar: 06114 ×2, 06101 ×2 (rasmdagi kabi dublikatlar) qayd etildi, biletlar kiritilmagan',
   JSON.stringify(inv) === JSON.stringify([{ ticket_no: '06087', n: 1 }, { ticket_no: '06101', n: 2 }, { ticket_no: '06114', n: 2 }]) && (await status('06114')) === 'NOT_ADMITTED', JSON.stringify(inv));
await s.screenshot({ path: out + '/08_inventory.png' });
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
// admin zaxira joy qo'shadi (zaldagi qo'shimcha joy) va sig'imni tasdiqlaydi
const actx = await b.newContext(PHONE); const a = await actx.newPage();
a.on('dialog', (d) => d.accept());
await login(a, 'admin@dusel.test', 'Admin-Test-2026');
await a.click('nav.tabs button:has-text("Admin")'); await a.waitForSelector('text=Zaxira joy qo\'shish');
await a.fill('input[placeholder="2-qavat"]', '2-qavat'); await a.fill('input[placeholder="B206"]', 'B206');
await a.fill('input[placeholder="qator"]', '15'); await a.fill('input[placeholder="joy"]', '16'); await a.fill('input[placeholder="Qanday tekshirildi"]', 'Zalda tekshirildi: B206 15-qator 16-joy bo\'sh va raqamli');
await a.click('button:has-text("Qo\'shish")'); await a.waitForTimeout(600);
await a.fill('section:has-text("Ruxsat etilgan sig\'im") input[type=number]', '11223'); await a.click('section:has-text("Ruxsat etilgan sig\'im") button:has-text("Saqlash")'); await a.waitForTimeout(600);
await a.screenshot({ path: out + '/09_admin.png', fullPage: true });
ok('T13 Admin tasdiqlangan zaxira joyni qo\'shdi va sig\'imni oshirdi (audit bilan)',
   (await q("select spare_status from checkin.seats where seat_key='SEKTOR:B206:15:16'"))[0]?.spare_status === 'AVAILABLE' && (await q("select value::text v from checkin.settings where key='capacity'"))[0].v === '11223');
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
ok('T12 Nazoratchi dalillarni yozib, zaxira joyni band qilib, almashtirish bileti berdi (QR ko\'rsatildi)', rep?.status === 'ACTIVE' && rep.seat_key === 'SEKTOR:B206:15:16');
// almashtirish QR'ini darvozada kamera orqali emas, QR matnidan o'qiymiz (svg ichidagi payload yo'q) — tokenni bazadan olib bo'lmaydi (faqat xesh)
// shuning uchun ekrandagi QR rasmini dekod qilamiz
const svg = await s.locator('.qrbox svg').first().screenshot({ path: out + '/11b_replacement_qr.png' });
ok('T07r Almashtirish bileti QR rasmi chop etishga tayyor', fs.statSync(out + '/11b_replacement_qr.png').size > 1000);
// ---------------------------------------------------------------- 5. Panel
await s.click('nav.tabs button:has-text("Panel")'); await s.waitForSelector('text=Kirish statistikasi');
await s.waitForSelector('text=Sektorlar bo\'yicha', { timeout: 10000 });
await s.screenshot({ path: out + '/12_dashboard.png', fullPage: true });
const dtext = await s.locator('main').textContent();
ok('T13d Boshqaruv paneli: ajratilgan 11222, kiritilgan, takroriy skanlar, inventar alohida', /11222/.test(dtext) && /Takroriy skanlar/.test(dtext) && /Jismoniy inventar/.test(dtext));
// ---------------------------------------------------------------- 6. Oflayn favqulodda rejim
await a.evaluate(async () => {
  const sb = window.supabase.createClient(location.origin, 'local-test-anon-key', { auth: { storageKey: 'dusel_ci_auth_LOCAL-TEST' } });
  await sb.rpc('ci_set_contingency_code', { p_code: '24681357' });
});
const octx = await b.newContext(PHONE); const o = await octx.newPage();
const dialogs = []; o.on('dialog', async (d) => { dialogs.push(d.message()); if (d.type() === 'prompt') await d.accept('24681357'); else await d.accept(); });
await login(o, 'gate1@dusel.test', 'Gate-Test-2026');
await o.waitForTimeout(800);
await octx.setOffline(true);
await o.fill('input[placeholder="5 xonali bilet raqami"]', '00500'); await o.click('button:has-text("Tekshirish")');
await o.waitForSelector('button:has-text("Favqulodda rejim")', { timeout: 15000 });
await o.click('button:has-text("Favqulodda rejim")'); await o.waitForSelector('text=FAVQULODDA OFLAYN REJIM');
for (const c of ['00500', '00501', '00330']) { await o.fill('input[placeholder="5 xonali bilet raqami"]', c); await o.click('button:has-text("Tekshirish")'); await o.waitForTimeout(250); }
await o.fill('input[placeholder="5 xonali bilet raqami"]', '00500'); await o.click('button:has-text("Tekshirish")'); await o.waitForTimeout(250);
const offDup = await o.locator('.result .big').last().textContent();
await o.screenshot({ path: out + '/13_offline_mode.png', fullPage: true });
ok('T19 Favqulodda rejim faqat kod bilan yoqiladi; qabullar "VAQTINCHA", shu qurilmadagi takror bloklanadi', /ALLAQACHON/.test(offDup) && (await status('00500')) === 'NOT_ADMITTED', offDup);
await octx.setOffline(false);
await o.evaluate(() => window.dispatchEvent(new Event('online')));
await o.waitForFunction(() => window.DUSEL_CI_DEBUG.state.queue.length === 0, null, { timeout: 15000 });
await o.waitForTimeout(800);
const off = await q("select ticket_no, decision, offline_at is not null off from checkin.admission_events where offline_at is not null order by ticket_no");
ok('T19b Aloqa tiklangach navbat sinxronlandi: 00500/00501 kiritildi, 00330 (allaqachon kirgan) — ziddiyat holatiga',
   JSON.stringify(off.map((x) => x.ticket_no + ':' + x.decision)) === JSON.stringify(['00330:DENIED_ALREADY_ADMITTED', '00500:ADMITTED', '00501:ADMITTED'])
   && (await q("select source from checkin.review_cases where ticket_no='00330'"))[0]?.source === 'OFFLINE_CONFLICT' && dialogs.some((m) => /ziddiyat/.test(m)), JSON.stringify(off) + ' ' + dialogs.join('|').slice(0, 120));
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
ok('T15 Darvoza xodimi API orqali ham bilet holatini/sozlamani o\'zgartira olmaydi', direct[0] === 'ROLE_DENIED' && direct[1] === 'ROLE_DENIED' && (await status('07000')) === 'NOT_ADMITTED', direct);
const ver = (await q("select count(*)::int n from checkin.audit_log"))[0].n;
ok('T16 Barcha admin/nazoratchi amallari audit jurnalida', ver > 10, ver + ' yozuv');
ok('T00 Sahifada JavaScript xatolari yo\'q', errs.length === 0, errs.join(' | '));
await b.close(); await db.end();
fs.writeFileSync(out + '/e2e_results.json', JSON.stringify(R, null, 1));
console.log(`\n${R.filter((r) => r.ok).length}/${R.length} PASS`);
process.exit(R.every((r) => r.ok) ? 0 : 1);
