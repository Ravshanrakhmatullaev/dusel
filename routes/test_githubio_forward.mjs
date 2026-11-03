import { chromium } from 'playwright';
const b = await chromium.launch().catch(() => chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }));
const p = await b.newPage();
await p.route('https://dusel.pages.dev/**', r => r.fulfill({ status: 200, body: 'TARGET' }));
let pass = 0, n = 0;
for (const [c, exp] of [['00330', 'https://dusel.pages.dev/ticket?code=00330'], ['00001', 'https://dusel.pages.dev/ticket?code=00001'], ['11222', 'https://dusel.pages.dev/ticket?code=11222'], ['11223', null], ['000001', null], ['0001', null], ['', null]]) {
  await p.goto(`http://127.0.0.1:8795/dusel/?code=${c}`); await p.waitForTimeout(500);
  const u = p.url(); const ok = exp ? u === exp : u.startsWith('http://127.0.0.1') && (await p.textContent('h1')) === 'Bilet topilmadi';
  n++; if (ok) pass++; console.log((ok ? 'PASS ' : 'FAIL ') + `github.io/dusel/?code=${c} → ${exp || 'yo\'naltirilmaydi, "Bilet topilmadi"'}  (${u})`);
}
console.log(`${pass}/${n} PASS`); await b.close();
