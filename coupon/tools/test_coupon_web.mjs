import { chromium } from 'playwright';
import fs from 'fs';
const base=process.argv[2]||'http://localhost:8777'; const out=process.argv[3]||'/home/claude/work/coupon/web_shots'; fs.mkdirSync(out,{recursive:true});
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'}).catch(()=>chromium.launch());
const R=[]; const ok=(n,c,d='')=>{R.push({test:n,ok:!!c,detail:String(d)});console.log((c?'PASS ':'FAIL ')+n+(d?' — '+d:''))};
const ctx=await b.newContext({viewport:{width:390,height:844},deviceScaleFactor:3,isMobile:true,hasTouch:true}); const p=await ctx.newPage();
const st=()=>p.evaluate(()=>({type:document.documentElement.getAttribute('data-type'),ttl:document.getElementById('ttl').textContent,num:document.getElementById('num').textContent,
  chip:document.getElementById('chip').textContent,prize:document.getElementById('prize').textContent,txt:document.body.innerText,wheels:document.querySelectorAll('.wheel').length,
  hero:getComputedStyle(document.getElementById('hero')).backgroundImage,errVis:getComputedStyle(document.querySelector('.err')).display!=='none'}));
for(const [t,c,exp] of [['gold','0001',['GOLD','10 TA AVTOMOBIL']],['gold','1000',['GOLD','10 TA AVTOMOBIL']],['gold','2000',['GOLD','10 TA AVTOMOBIL']],
                        ['silver','0001',['SILVER','100 TA CHET ELGA SAYOHAT']],['silver','2001',['SILVER','100 TA CHET ELGA SAYOHAT']],['silver','4000',['SILVER','100 TA CHET ELGA SAYOHAT']]]){
  await p.goto(`${base}/coupon?type=${t}&code=${c}`); await p.waitForTimeout(400); const s=await st();
  ok(`/coupon?type=${t}&code=${c} → ${exp[0]} kupon № ${c}`, s.type===t&&s.ttl===exp[0]&&s.num===c&&s.chip===exp[0]+' KUPON'&&s.prize===exp[1]&&!s.errVis&&/webp/.test(s.hero), `${s.ttl} ${s.num} · ${s.prize}`);
  ok(`  ${t} ${c}: bilet bloklari yo'q (BILET RAQAMI, sektor/qator/joy, raqam g'ildiraklari)`, s.wheels===0 && !/BILET RAQAMI|SEKTOR|QATOR|JOY №|HUMO ARENA/i.test(s.txt));
}
await p.goto(`${base}/coupon?type=gold&code=0001`); await p.waitForTimeout(1600); await p.screenshot({path:out+'/gold_0001_390.png'});
await p.goto(`${base}/coupon?type=silver&code=0001`); await p.waitForTimeout(1600); await p.screenshot({path:out+'/silver_0001_390.png'});
// animatsiya ishlayapti (canvas kadrlari o'zgaradi)
const f1=await p.evaluate(()=>document.getElementById('fx').toDataURL()); await p.waitForTimeout(400); const f2=await p.evaluate(()=>document.getElementById('fx').toDataURL());
ok('Fon effekti (canvas) jonli — kadrlar o\'zgaradi', f1!==f2);
for(const q of ['type=gold&code=2001','type=gold&code=0000','type=silver&code=4001','type=gold&code=00001','type=gold&code=1','type=bronze&code=0001','code=0001','type=gold','']){
  await p.goto(`${base}/coupon?${q}`); await p.waitForTimeout(300); const s=await st();
  ok(`Noto'g'ri kupon "${q||'(bo\'sh)'}" → "Kupon topilmadi"`, s.type==='none'&&s.errVis&&/Kupon topilmadi/.test(s.txt));
}
await p.goto(`${base}/coupon?type=gold&code=2001`); await p.waitForTimeout(500); await p.screenshot({path:out+'/xato_gold_2001.png'});
// bilet tizimi o'zgarmagan
for(const c of ['00001','10001','11222']){
  await p.goto(`${base}/?code=${c}`); await p.waitForFunction(()=>document.getElementById('ticket')&&document.getElementById('ticket').classList.contains('done'),null,{timeout:20000});
  const r=await p.evaluate(()=>({w:document.querySelectorAll('.wheel').length,txt:document.body.innerText,coupon:!!document.getElementById('fx')}));
  ok(`Bilet /?code=${c} avvalgidek bilet sahifasi (kuponga aloqasi yo'q)`, r.w===5 && /BILET RAQAMI/i.test(r.txt) && !r.coupon);
}
await p.goto(`${base}/?code=0001`); await p.waitForTimeout(300);
ok("4 xonali kupon raqami bilet sahifasida bilet sifatida qabul qilinmaydi (/?code=0001 → xato)", await p.evaluate(()=>document.getElementById('ticket').classList.contains('invalid')));
for (const [n,vp] of [['320x568',{width:320,height:568}],['360x740',{width:360,height:740}],['375x667',{width:375,height:667}],['412x915',{width:412,height:915}],['1366x900',{width:1366,height:900}]]){
  for(const t of ['gold','silver']){
    const c=await b.newContext({viewport:vp,isMobile:vp.width<700,hasTouch:vp.width<700}); const pg=await c.newPage();
    await pg.goto(`${base}/coupon?type=${t}&code=${t==='gold'?'2000':'4000'}`); await pg.waitForTimeout(1500);
    const m=await pg.evaluate(()=>{const r=document.getElementById('num').getBoundingClientRect();return {sw:document.documentElement.scrollWidth,bottom:r.bottom,right:r.right,ov:document.getElementById('num').scrollWidth>document.querySelector('.plate').clientWidth+2}});
    ok(`${n} ${t}: gorizontal siljish yo'q, raqam birinchi ekranda va to'liq sig'adi`, m.sw<=vp.width && m.bottom<=vp.height && m.right<=vp.width && !m.ov, `scrollWidth ${m.sw}, raqam pastki ${Math.round(m.bottom)}px`);
    if(vp.width===320) await pg.screenshot({path:`${out}/${t}_320.png`});
    await c.close();
  }
}
const rm=await b.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'}); const pr=await rm.newPage(); await pr.goto(`${base}/coupon?type=gold&code=0007`); await pr.waitForTimeout(300);
ok('Kamroq harakat (reduced motion) sozlamasida effektlar o\'chadi, raqam ko\'rinadi', await pr.evaluate(()=>getComputedStyle(document.getElementById('fx')).display==='none' && document.getElementById('num').textContent==='0007'));
await b.close(); fs.writeFileSync(out+'/results.json',JSON.stringify(R,null,1));
console.log(`${R.filter(r=>r.ok).length}/${R.length} PASS`);
