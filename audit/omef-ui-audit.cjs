const { chromium, webkit, devices } = require('playwright');
const fs = require('fs');
const path = require('path');
const os = require('os');
const results = [];
const report = { checkedAt: new Date().toISOString(), source: process.env.GITHUB_SHA, passes: 0, failures: 0, checks: [], browsers: {}, screenshots: [], deployment: {} };
function check(scope, name, passed, detail) {
 const row = { scope, name, passed: Boolean(passed), detail: String(detail ?? '') };
 report.checks.push(row); report[row.passed ? 'passes' : 'failures']++;
 console.log((row.passed ? 'PASS ' : 'FAIL ') + scope + ' :: ' + name + (detail ? ' :: ' + detail : ''));
}
const nap = ms => new Promise(resolve => setTimeout(resolve, ms));
const counts = page => page.locator('#count').innerText().then(s => Number((s.replace(/[^\d]/g,'')) || 0)).catch(() => -1);
async function canvasMetrics(page) {
 return page.evaluate(() => {
  const c = document.getElementById('omefCanvas'), x = c?.getContext('2d', {willReadFrequently: true});
  if (!x) return null;
  const w=c.width,h=c.height,d=x.getImageData(0,0,w,h).data;
  let occupied=0,energy=0,bright=0,cx=0,cy=0,second=0,third=0;
  const bg = getComputedStyle(document.body).getPropertyValue('--canvas').trim().toLowerCase();
  const light = bg==='#fff'||bg==='#ffffff'||bg==='white';
  for(let y=0;y<h;y+=3)for(let z=0;z<w;z+=3){
   const i=(y*w+z)*4;
   const val=(d[i]+d[i+1]+d[i+2])/3, strength=light?255-val:val;
   if(strength>8){occupied++;energy+=strength;cx+=z*strength;cy+=y*strength;second+=z*z*strength;third+=y*y*strength;}
  }
  const total=Math.ceil(w/3)*Math.ceil(h/3);
  const mX=energy?cx/energy:0,mY=energy?cy/energy:0;
  return {width:w,height:h,fill:+(occupied/total).toFixed(5),energy:Math.round(energy),
    spreadX:energy?+Math.sqrt(Math.max(0,second/energy-mX*mX)).toFixed(2):0,
    spreadY:energy?+Math.sqrt(Math.max(0,third/energy-mY*mY)).toFixed(2):0};
 });
}
async function testControls(page, selector, scope) {
 const inputs=await page.locator(selector).evaluateAll(elems=>elems.filter(e=>e.id&&!e.disabled).map(e=>({id:e.id,min:Number(e.min),max:Number(e.max),step:Number(e.step)||.01,old:Number(e.value)})));
 let ok=0,invalid=[],events=0;
 const evaluated=await page.evaluate(rows => {
  const invalid=[];let events=0,ok=0;
  for(const row of rows) {
    const e=document.getElementById(row.id);
    if(!e){invalid.push(row.id+':missing');continue}
    let value=row.max;
    if(Math.abs(value-row.old)<row.step/2)value=row.min;
    e.value=String(value);
    e.dispatchEvent(new Event('input',{bubbles:true}));
    e.dispatchEvent(new Event('change',{bubbles:true}));events+=2;
    const valid=Number.isFinite(Number(e.value))&&Math.abs(Number(e.value)-value)<Math.max(.00001,row.step*1.1);
    const output=document.getElementById(row.id+'v');
    const display=output ? (output.textContent||'').trim().length>0 : true;
    if(valid&&display)ok++;else invalid.push(row.id+':value or readout');
    e.value=String(row.old);
    e.dispatchEvent(new Event('input',{bubbles:true}));
    e.dispatchEvent(new Event('change',{bubbles:true}));events+=2;
  }
  return {tested:rows.length,ok,events,invalid};
 },inputs);
 check(scope,'All range controls accept min/max input, emit events and update their readout',evaluated.tested===evaluated.ok && evaluated.tested>0,'tested='+evaluated.tested+' events='+evaluated.events+' invalid='+evaluated.invalid.join(','));
 return evaluated;
}
async function capture(page, name) {
 const file=path.join('audit-artifacts',name+'.png');
 fs.mkdirSync('audit-artifacts',{recursive:true});
 await page.screenshot({path:file,fullPage:false});
 report.screenshots.push(file);
 return file;
}
async function run(browserType,name){
 let browser,context,page;
 const scopedErrors=[];
 try {
  browser=await browserType.launch({headless:true});
  const device={...devices['iPhone 13'],viewport:{width:390,height:844},deviceScaleFactor:2};
  context=await browser.newContext({...device,acceptDownloads:true});
  page=await context.newPage();
  page.setDefaultTimeout(10000);
  page.on('pageerror',e=>{scopedErrors.push(String(e));console.error('PAGEERROR '+name+' '+String(e));});
  page.on('console',m=>{if(m.type()==='error')scopedErrors.push('console: '+m.text());});
  const local='file://'+path.resolve('apps/omef-exclusive.html');
  await page.goto(local,{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForFunction(()=>Boolean(window.OMEFExclusive && document.getElementById('omefCanvas')),{timeout:30000});
  const api=await page.evaluate(()=>({mode:window.OMEFExclusive.activeMode(),defs:window.OMEFExclusive.allDefs.length}));
  check(name,'Original starts automatically',api.mode==='omef','mode='+api.mode);
  check(name,'All 61 OMEF parameters exposed',api.defs===61,'parameters='+api.defs);
  await page.evaluate(()=>document.querySelector('[data-theme="dark"]')?.click());
  await nap(1300);
  const before=await counts(page),origMetrics=await canvasMetrics(page);
  await nap(850);
  const after=await counts(page);
  check(name,'Original accumulates points in browser',after>before && after>0,'points '+before+' -> '+after);
  check(name,'Original canvas contains visible particles',origMetrics && origMetrics.fill>0.0001,JSON.stringify(origMetrics));
  await capture(page,name+'-original');
  const original=await testControls(page,'#omefUI input[type="range"]',name+' Original');
  await page.locator('#originalPause').click();
  await nap(300);
  const paused0=await counts(page);await nap(600);const paused1=await counts(page);
  check(name,'Pause drawing halts point count',paused1===paused0,paused0+' -> '+paused1);
  await page.locator('#originalPause').click({force:true});
  await nap(500);const resumed=await counts(page);
  check(name,'Resume drawing restores simulation',resumed>paused1,paused1+' -> '+resumed);
  const auto0=await page.locator('#originalAuto').innerText();
  await page.locator('#originalAuto').click();
  const auto1=await page.locator('#originalAuto').innerText();
  check(name,'Auto drift button switches state',auto0!==auto1,auto0+' -> '+auto1);
  const firstSeed=await page.locator('#a').inputValue();
  let pointerError='';
  try {await page.locator('#random').click({timeout:6000});}
  catch(e){pointerError=String(e).slice(0,300);}
  await nap(400);
  const newSeed=await page.locator('#a').inputValue();
  check(name,'Next attractor responds to real mobile pointer click',!pointerError&&firstSeed!==newSeed,'Pair '+firstSeed+' -> '+newSeed+'; '+pointerError);
  await capture(page,name+'-next');
  await page.locator('#originalClear').click({force:true});
  await page.locator('#originalRestart').click({force:true});
  await nap(600);
  check(name,'Restart restores a working native engine',(await counts(page))>0,'points='+(await counts(page)));
  await page.locator('#engineTwin').click();
  await page.waitForFunction(()=>window.OMEFExclusive.activeMode()==='twin',{timeout:30000});
  await nap(1800);
  const coupled0=await counts(page);
  const coupledMetrics=await canvasMetrics(page);
  check(name,'Coupled mode calculates and renders',(coupled0>0)&&coupledMetrics?.fill>0.0001,'points='+coupled0+' metrics='+JSON.stringify(coupledMetrics));
  await capture(page,name+'-coupled');
  const twin=await testControls(page,'#twinUI input[type="range"]',name+' Coupled');
  const selects=await page.evaluate(()=>{
    let ok=0,fail=[];
    for(const e of document.querySelectorAll('#twinUI select')){
      const original=e.value, alt=Array.from(e.options).find(x=>x.value!==original);
      if(!alt)continue;
      e.value=alt.value;e.dispatchEvent(new Event('change',{bubbles:true}));
      if(e.value===alt.value)ok++;else fail.push(e.id);
      e.value=original;e.dispatchEvent(new Event('change',{bubbles:true}));
    }
    return {tested:document.querySelectorAll('#twinUI select').length,ok,fail};
  });
  check(name,'Coupling select menus respond to UI change events',selects.ok===selects.tested && selects.tested>0,JSON.stringify(selects));
  check(name,'All 122 A/B genome controls present',await page.locator('input[id^=twA_], input[id^=twB_]').count()===122,
    'A/B genome='+(await page.locator('input[id^=twA_], input[id^=twB_]').count()));
  const twin1=await counts(page); await nap(700);const twin2=await counts(page);
  check(name,'Coupled continues accumulating after bulk slider interactions',twin2>twin1,'points '+twin1+' -> '+twin2);
  const beforeTap=await page.locator('#twinGlobal').inputValue();
  const drag=await page.locator('#twinGlobal').boundingBox();
  if (drag) {
   await page.locator('#twinGlobal').scrollIntoViewIfNeeded();
   const b=await page.locator('#twinGlobal').boundingBox();
   await page.mouse.move(b.x+b.width*.15,b.y+b.height*.5);
   await page.mouse.down();await page.mouse.move(b.x+b.width*.9,b.y+b.height*.5,{steps:8});await page.mouse.up();
  }
  const afterTap=await page.locator('#twinGlobal').inputValue();
  check(name,'Cross-coupling responds to pointer drag',drag&&beforeTap!==afterTap,beforeTap+' -> '+afterTap);
  await capture(page,name+'-coupled-after-slider');
  const errors=scopedErrors.filter(e=>!e.includes('favicon'));
  check(name,'No uncaught JavaScript runtime errors',errors.length===0,errors.slice(0,7).join(' | '));
  report.browsers[name]={original,twins:twin,errors,originalImage:origMetrics,coupledImage:coupledMetrics,counts:{originalBefore:before,originalAfter:after,coupled:coupled0,coupledAfter:twin2}};
 } catch(err){
  check(name,'Browser suite completed',false,String(err?.stack||err).slice(0,1100));
  report.browsers[name]={error:String(err),consoleErrors:scopedErrors};
 }finally{if(context)await context.close().catch(()=>{});if(browser)await browser.close().catch(()=>{});}
}
async function testLiveDeployment(){
  let browser, page;
  const url='https://maaronfanberg-lab.github.io/me-/apps/omef-exclusive.html?audit='+Date.now();
  try{
    browser=await chromium.launch({headless:true});
    page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:2});
    const resp=await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
    await page.waitForTimeout(1000);
    const info=await page.evaluate(()=>({
      initialized:Boolean(window.OMEFExclusive),originalControls:Boolean(document.getElementById('originalPause')),
      originalCount:window.OMEFExclusive?.allDefs?.length||0,
      title:document.title
    }));
    check('GitHub Pages','Deployed site returns HTTP 200',resp?.status()===200,'HTTP '+resp?.status());
    check('GitHub Pages','Live deployment has the audited Original UI',info.initialized&&info.originalControls&&info.originalCount===61,JSON.stringify(info));
    if(info.initialized)await capture(page,'live-github-pages');
    report.deployment={url,code:resp?.status(),...info};
  }catch(e){check('GitHub Pages','Live site opens in browser',false,String(e).slice(0,350));report.deployment={url,error:String(e)}}
  finally{if(browser)await browser.close().catch(()=>{});}
}
(async()=>{
  for (const [engine,name] of [[chromium,'Chromium-iPhone-size'],[webkit,'WebKit-iPhone-size']])await run(engine,name);
  await testLiveDeployment();
  fs.writeFileSync('audit-artifacts/audit-results.json',JSON.stringify(report,null,2));
  console.log('AUDIT_SUMMARY '+JSON.stringify({passes:report.passes,failures:report.failures,browsers:report.browsers,screenshots:report.screenshots}).slice(0,14000));
  process.exitCode=report.failures?1:0;
})().catch(err=>{console.error(err);process.exitCode=1;});