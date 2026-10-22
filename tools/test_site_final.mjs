import { chromium } from 'playwright';
import fs from 'fs';
const base=process.argv[2]||'http://localhost:8765/'; const ROOT=process.argv[3]||'/home/claude/work/final'; const out=ROOT+'/web'; fs.mkdirSync(out,{recursive:true});
const lines=fs.readFileSync(ROOT+'/master/DUSEL_MASTER_FINAL.csv','utf8').replace(/^\uFEFF/,'').trim().split('\n'); const hdr=lines[0].split(',');
const I=n=>hdr.indexOf(n); const M={}; for(const l of lines.slice(1)){const c=l.split(','); M[c[I('TICKET_NUMBER')]]={s:c[I('SECTOR')],q:c[I('ROW')],j:c[I('SEAT')],z:c[I('ZONE')],st:c[I('STATUS')]};}
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'}).catch(()=>chromium.launch());
const R=[]; const ok=(n,c,d='')=>{R.push({test:n,ok:!!c,detail:String(d)});console.log((c?'PASS ':'FAIL ')+n+(d?' — '+d:''))};
const ctx=await b.newContext({viewport:{width:390,height:844},deviceScaleFactor:3,isMobile:true,hasTouch:true});
await ctx.route(/google\.com|yandex\./, r=>r.fulfill({status:200,contentType:'text/html',body:'<title>stub</title>'}));
const p=await ctx.newPage();
const st=async()=>p.evaluate(()=>{const s=document.getElementById('seats');return {cls:s.className,S:vS.textContent,Q:vQ.textContent,J:vJ.textContent,note:getComputedStyle(seatNote).display!=='none',msg:getComputedStyle(seatMsg).display!=='none'?seatMsg.textContent:'',body:document.body.innerText}});
const pick=(f)=>Object.keys(M).filter(k=>f(M[k]));
const special=[...pick(m=>m.s==='A203'&&m.q==='15').slice(0,1),...pick(m=>m.s==='C211'&&m.q==='14').slice(-1),...pick(m=>m.s==='C210'&&m.q==='16'&&(m.j==='18'||m.j==='19')),...pick(m=>m.s==='C212'&&m.q==='5').slice(0,1)];
const list=['00001','00002','00003','00006','05611','10000','10001','11221','11222',...special];
for(const c of list){
  await p.goto(base+'?code='+c); await p.waitForFunction(()=>!document.getElementById('seats').classList.contains('loading'));
  const s=await st(); const m=M[c];
  const right=s.S===m.s&&s.Q===m.q&&s.J===m.j; const noteOk=(m.st==='REVIEW_REQUIRED')===s.note;
  ok(`${c}: sayt ${s.S}/${s.Q}/${s.J} = master ${m.s}/${m.q}/${m.j} (${m.st})`, right&&noteOk&&!/TEST NAMUNA/.test(s.body), m.st==='REVIEW_REQUIRED'?'neytral izoh ko‘rinadi':'izohsiz');
}
await p.goto(base+'?code=00001'); await p.waitForTimeout(3300); await p.screenshot({path:out+'/ticket_00001.png'});
const rv=special[0]; await p.goto(base+'?code='+rv); await p.waitForTimeout(3300); await p.screenshot({path:out+`/ticket_${rv}_review.png`});
await p.goto(base+'?code=11222'); await p.waitForTimeout(3300);
await p.tap('#whereBtn'); await p.waitForTimeout(450); await p.screenshot({path:out+'/ticket_11222_maps.png'});
for (const [sel,exp] of [['#gmap','https://www.google.com/maps/search/?api=1&query=Humo+Arena+Tashkent'],['#ymap','https://yandex.uz/maps/org/42137198861/']]){
  const [pop]=await Promise.all([p.waitForEvent('popup'),p.tap(sel)]); ok(`${sel} → Humo Arena`, pop.url()===exp, pop.url()); await pop.close();
}
const icons=await p.evaluate(()=>[...document.querySelectorAll('#maps a')].map(a=>({svg:!!a.querySelector('svg.mi'),h:a.querySelector('svg.mi').getBoundingClientRect().height,label:a.getAttribute('aria-label')})));
ok('Google/Yandex brend SVG ikonkalari, aria-label', icons.every(i=>i.svg&&i.h===22&&i.label), JSON.stringify(icons.map(i=>i.h)));
for(const q of ['?code=11223','?code=00000','?code=1234','']){await p.goto(base+q); await p.waitForTimeout(300);
  ok(`Noto'g'ri havola "${q||'(bo\'sh)'}" rad etiladi`, await p.$eval('#ticket',e=>e.classList.contains('invalid')) && await p.$eval('#seats',e=>getComputedStyle(e).display==='none'));}
for (const [n,vp] of [['320x568',{width:320,height:568}],['360x740',{width:360,height:740}],['375x667',{width:375,height:667}],['412x915',{width:412,height:915}],['1366x900',{width:1366,height:900}]]){
  const c=await b.newContext({viewport:vp,isMobile:vp.width<700,hasTouch:vp.width<700}); const pg=await c.newPage();
  await pg.goto(base+'?code=11222'); await pg.waitForFunction(()=>document.getElementById('ticket').classList.contains('done'),null,{timeout:20000}); await pg.waitForTimeout(200);
  const m=await pg.evaluate(()=>({sw:document.documentElement.scrollWidth,of:[...document.querySelectorAll('.seat b,.seat .k')].some(e=>e.scrollWidth>e.clientWidth+1),shown:[...document.querySelectorAll('.wheel')].map(w=>{const r=w.getBoundingClientRect();const sp=[...w.querySelectorAll('span')].find(s=>Math.abs(s.getBoundingClientRect().top-r.top)<2);return sp?sp.textContent:'?'}).join('')}));
  ok(`${n}: siljish yo'q, kartalar sig'adi, raqam 11222`, m.sw<=vp.width&&!m.of&&m.shown==='11222', 'scrollWidth '+m.sw); await c.close();
}
// eski va yangi URL mosligi: 150 tasodifiy + chegaralar, sayt qiymati = master
const pc=await (await b.newContext()).newPage(); const bad=[]; const cs=['00001','01000','01001','09999','10000','10001','11000','11001','11222'];
for(let i=0;i<150;i++) cs.push(String(1+Math.floor(Math.random()*11222)).padStart(5,'0'));
for(const c of cs){await pc.goto(base+'?code='+c); await pc.waitForFunction(()=>!document.getElementById('seats').classList.contains('loading'));
  const r=await pc.evaluate(()=>({inv:document.getElementById('ticket').classList.contains('invalid'),S:vS.textContent,Q:vQ.textContent,J:vJ.textContent,cls:document.getElementById('seats').className}));
  const m=M[c]; if(r.inv||r.S!==m.s||r.Q!==m.q||r.J!==m.j) bad.push(c);}
ok(`${cs.length} ta URL (00001–10000 eski + 10001–11222 yangi): sahifa ochiladi, joy = master`, !bad.length, bad.join(','));
// 404 sahifa: ildizda (Cloudflare) to'g'ri qaytaradi
const p4=await (await b.newContext()).newPage();
await p4.goto(base+'404.html'); await p4.waitForURL(/code=invalid/,{timeout:5000}).catch(()=>{});
ok("404 sahifa ildizda (dusel.pages.dev) bosh sahifaga qaytaradi", new URL(p4.url()).pathname==='/' && p4.url().includes('code=invalid'), p4.url());
await b.close(); fs.writeFileSync(out+'/site_tests_final.json',JSON.stringify(R,null,1));
console.log(`${R.filter(r=>r.ok).length}/${R.length} PASS`);
