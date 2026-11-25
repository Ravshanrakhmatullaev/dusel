// DUSEL — xodim akkauntlarini yaratish (admin noutbukida; service_role kaliti FAQAT shu yerda, frontendga hech qachon).
//   SUPABASE_URL=https://<ref>.supabase.co SERVICE_ROLE_KEY=... node tools/create_staff.mjs staff.csv parollar.csv
// staff.csv (UTF-8, vergul):  email,display_name,role      role = INVENTORY | GATE | SUPERVISOR | ADMIN
// Natija: parollar.csv (faqat egasi o'qiy oladi, 0600) — har xodimga shaxsan topshiring, keyin faylni o'chiring.
// Mavjud foydalanuvchiga yangi parol berilmaydi (faqat rol yangilanadi). PRODUCTION bazasi sinov akkauntlarini rad etadi.
import fs from 'fs';
import crypto from 'crypto';
const URL_ = (process.env.SUPABASE_URL || '').replace(/\/$/, ''), KEY = process.env.SERVICE_ROLE_KEY || '';
const [inFile, outFile] = process.argv.slice(2);
if (!URL_ || !KEY || !inFile || !outFile) { console.error('SUPABASE_URL, SERVICE_ROLE_KEY, staff.csv, parollar.csv kerak'); process.exit(2); }
if (fs.existsSync(outFile)) { console.error(outFile + ' allaqachon bor — ustiga yozilmaydi'); process.exit(2); }
const H = { apikey: KEY, authorization: 'Bearer ' + KEY, 'content-type': 'application/json' };
const ROLES = ['INVENTORY', 'GATE', 'SUPERVISOR', 'ADMIN'];
const rows = fs.readFileSync(inFile, 'utf8').replace(/^﻿/, '').split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !/^email\s*,/i.test(l))
  .map((l) => { const [email, display_name, role] = l.split(',').map((x) => (x || '').trim()); return { email: email.toLowerCase(), display_name, role: (role || '').toUpperCase() }; });
const bad = rows.filter((r) => !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(r.email) || !ROLES.includes(r.role));
if (bad.length) { console.error('Noto\'g\'ri qatorlar:', bad); process.exit(3); }
function password() {   // 20 belgi: kichik/katta harf + raqam (Supabase siyosati: lower_upper_letters_digits, ≥ 12)
  const A = 'abcdefghijkmnpqrstuvwxyz', B = 'ABCDEFGHJKLMNPQRSTUVWXYZ', D = '23456789', all = A + B + D;
  const pick = (s) => s[crypto.randomInt(s.length)];
  const p = [pick(A), pick(B), pick(D)]; while (p.length < 20) p.push(pick(all));
  for (let i = p.length - 1; i > 0; i--) { const j = crypto.randomInt(i + 1); [p[i], p[j]] = [p[j], p[i]]; }
  return p.join('');
}
const creds = [];
for (const r of rows) {
  const pw = password();
  const res = await fetch(URL_ + '/auth/v1/admin/users', { method: 'POST', headers: H, body: JSON.stringify({ email: r.email, password: pw, email_confirm: true }) });
  if (res.ok) { creds.push([r.email, r.display_name, r.role, pw]); console.log('yaratildi', r.email, r.role); }
  else if (res.status === 422) { creds.push([r.email, r.display_name, r.role, '(mavjud — parol o\'zgarmadi)']); console.log('mavjud', r.email); }
  else { console.error('XATO', r.email, res.status, await res.text()); process.exit(4); }
}
const rr = await fetch(URL_ + '/rest/v1/rpc/ci_staff_bootstrap', { method: 'POST', headers: H, body: JSON.stringify({ p_rows: rows }) });
const out = await rr.json();
if (!rr.ok) { console.error('Rollarni yozishda xato:', out); process.exit(5); }
fs.writeFileSync(outFile, 'email,ism,rol,parol\n' + creds.map((c) => c.map((x) => '"' + String(x).replace(/"/g, '""') + '"').join(',')).join('\n') + '\n', { mode: 0o600 });
console.log(`OK: ${out.staff} xodim rolga ega. Parollar: ${outFile} (0600). Topshirgandan keyin faylni o'chiring.`);
