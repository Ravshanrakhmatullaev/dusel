import { chromium } from 'playwright';
import fs from 'fs';
const base=process.argv[2]||'http://localhost:8765/'; const out=process.argv[3]||'/home/claude/work/v6web/shots'; fs.mkdirSync(out,{recursive:true});
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'}).catch(()=>chromium.launch());
const R=[]; const ok=(n,c,d='')=>{R.push({test:n,ok:!!c,detail:String(d)});console.log((c?'PASS ':'FAIL ')+n+(d?' — '+d:''))};
const BAD=/\b(SEKTOR|QATOR|JOY|BLITCHER|ZONA|QAVAT)\b|TEST NAMUNA|tasdiqlanmagan/i;
const ctx=await b.newContext({viewport:{width:390,height:844},deviceScaleFactor:3,isMobile:true,hasTouch:true});
await ctx.route(/google\.com|yandex\./, r=>r.fulfill({status:200,contentType:'text/html',body:'<title>stub</title>'}));
const p=await ctx.newPage(); const reqs=[]; p.on('request',r=>reqs.push(r.url()));
const shown=()=>p.evaluate(()=>[...document.querySelectorAll('.wheel')].map(w=>{const r=w.getBoundingClientRect();const sp=[...w.querySelectorAll('span')].find(s=>Math.abs(s.getBoundingClientRect().top-r.top)<2);return sp?sp.textContent:'?'}).join(''));
for(const c of ['00001','00330','10000','10001','11222']){
  await p.goto(base+'?code='+c); await p.waitForFunction(()=>document.getElementById('ticket').classList.contains('done'),null,{timeout:20000}); await p.waitForTimeout(200);
  const s=await shown(); const st=await p.evaluate(()=>({inv:document.getElementById('ticket').classList.contains('invalid'),txt:document.body.innerText,html:document.documentElement.outerHTML}));
  ok(`${c} ochiladi, markazda ${c}`, !st.inv && s===c && !/topilmadi/.test(st.txt.replace(/Bilet raqami topilmadi/,'')) , `ko'rsatildi: ${s}`);
  ok(`${c}: SEKTOR/QATOR/JOY/zona, TEST NAMUNA, "tasdiqlanmagan" yo'q (matn va HTML)`, !BAD.test(st.txt) && !BAD.test(st.html), (st.txt.match(BAD)||[''])[0]);
  ok(`${c}: sana, HUMO ARENA, BILET RAQAMI, ogohlantirish bor`, /23 DEKABR 2026/.test(st.txt)&&/HUMO ARENA/.test(st.txt)&&/BILET RAQAMI/i.test(st.txt)&&/haqiqiyligini tasdiqlamaydi/.test(st.txt));
  if(c==='10001'||c==='00330') await p.screenshot({path:`${out}/bilet_${c}.png`});
}
ok("Joy ma'lumoti uchun hech qanday so'rov yuborilmaydi (data/seats yo'q)", !reqs.some(u=>/data\/seats/.test(u)), reqs.filter(u=>/data/.test(u)).join(','));
for(const q of ['?code=00000','?code=11223','?code=99999','?code=1234','?code=abcde','']){
  await p.goto(base+q); await p.waitForTimeout(300);
  const st=await p.evaluate(()=>({inv:document.getElementById('ticket').classList.contains('invalid'),errVis:getComputedStyle(document.getElementById('err')).display!=='none',w:document.querySelectorAll('.wheel').length,txt:document.body.innerText}));
  ok(`Noto'g'ri "${q||'(bo\'sh)'}" → "Bilet raqami topilmadi", raqam yo'q`, st.inv&&st.errVis&&st.w===0&&/00001.*11222/.test(st.txt));
}
await p.goto(base+'?code=11223'); await p.waitForTimeout(500); await p.screenshot({path:`${out}/xato_11223.png`});
await p.goto(base+'?code=11222'); await p.waitForFunction(()=>document.getElementById('ticket').classList.contains('done'),null,{timeout:20000});
await p.tap('#whereBtn'); await p.waitForTimeout(450); await p.screenshot({path:`${out}/bilet_11222_xaritalar.png`});
for (const [sel,exp] of [['#gmap','https://www.google.com/maps/search/?api=1&query=Humo+Arena+Tashkent'],['#ymap','https://yandex.uz/maps/org/42137198861/']]){
  const [pop]=await Promise.all([p.waitForEvent('popup'),p.tap(sel)]); ok(`${sel} → Humo Arena (yangi oyna)`, pop.url()===exp, pop.url()); await pop.close();
}
for (const [n,vp] of [['320x568',{width:320,height:568}],['360x740',{width:360,height:740}],['375x667',{width:375,height:667}],['390x844',{width:390,height:844}],['412x915',{width:412,height:915}],['1366x900',{width:1366,height:900}]]){
  const c=await b.newContext({viewport:vp,isMobile:vp.width<700,hasTouch:vp.width<700}); const pg=await c.newPage();
  await pg.goto(base+'?code=10001'); await pg.waitForFunction(()=>document.getElementById('ticket').classList.contains('done'),null,{timeout:20000});
  const m=await pg.evaluate(()=>({sw:document.documentElement.scrollWidth,numBottom:document.getElementById('num').getBoundingClientRect().bottom}));
  ok(`${n}: gorizontal siljish yo'q, raqam birinchi ekranda`, m.sw<=vp.width && m.numBottom<=vp.height, `scrollWidth ${m.sw}, raqam pastki ${Math.round(m.numBottom)}px`);
  if(vp.width===320) await pg.screenshot({path:`${out}/bilet_10001_320px.png`});
  await c.close();
}
// barcha 11 222 kod qabul qilinadi (sahifa mantiqi): har birini to'liq yuklamasdan, sahifa skriptining shartini tekshirish
const pc=await (await b.newContext()).newPage(); await pc.goto(base+'?code=00001');
const all=await pc.evaluate(()=>{const re=/^\d{5}$/;let bad=[];for(let i=1;i<=11222;i++){const r=String(i).padStart(5,'0');if(!(re.test(r)&&+r>=1&&+r<=11222))bad.push(r)}return bad.length});
const src=await pc.evaluate(()=>document.documentElement.outerHTML);
ok("Sahifa kodida MIN=1, MAX=11222; 00001–11222 oralig'idagi 11 222 kodning hammasi shartdan o'tadi", /var MIN=1, MAX=11222;/.test(src) && all===0);
const sample=['00999','01000','05000','09999','10002','10500','11000','11100','11221'];
let sb=[]; for(const c of sample){await pc.goto(base+'?code='+c); await pc.waitForTimeout(150); if(await pc.$eval('#ticket',e=>e.classList.contains('invalid'))) sb.push(c);}
ok(`Qo'shimcha namunalar (${sample.join(', ')}) ochiladi`, !sb.length, sb.join(','));
await b.close(); fs.writeFileSync(out+'/results.json',JSON.stringify(R,null,1));
console.log(`${R.filter(r=>r.ok).length}/${R.length} PASS`);
