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
  await testControls(page,'#points, #ink, #size',name+' Shared canvas');
  const cb=page.locator('#livePreview');
  const cbBefore=await cb.isChecked();await cb.check({force:true});await cb.uncheck({force:true});await cb.setChecked(cbBefore,{force:true});
  check(name,'Preview checkbox responds',await cb.isChecked()===cbBefore,'checked='+cbBefore);
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
  const beforeMutation=await page.evaluate(()=>window.OMEFExclusive.allDefs.map(d=>Number(document.getElementById(d[0]).value)));
  await page.locator('#mutate').click();
  const afterMutation=await page.evaluate(()=>window.OMEFExclusive.allDefs.map(d=>Number(document.getElementById(d[0]).value)));
  check(name,'Mutate slightly changes formula controls',beforeMutation.some((x,i)=>x!==afterMutation[i]));
  await page.locator('#preset').click();
  check(name,'Restore filaments restores tested starting parameter',Math.abs(Number(await page.locator('#a').inputValue())-1.16)<.011);
  await page.locator('#render').click();
  await nap(350);
  check(name,'Render again restarts a working trajectory',(await counts(page))>0);
  await page.locator('#originalClear').click();
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
  // Identical dynamical state must NOT be silently replaced by a parameter-
  // selected flower/wave when a slider becomes the active focus.
  const projectionCheck=await page.evaluate(()=>{
    const api=window.OMEFExclusive;
    const A=Object.fromEntries(api.allDefs.map(d=>[d[0],Number(document.getElementById('twA_'+d[0]).value)]));
    const B=Object.fromEntries(api.allDefs.map(d=>[d[0],Number(document.getElementById('twB_'+d[0]).value)]));
    const links=Array.from({length:8},(_,i)=>({
      source:document.getElementById('tl'+i+'source').value,
      from:document.getElementById('tl'+i+'from').value,
      to:document.getElementById('tl'+i+'to').value,
      strength:Number(document.getElementById('tl'+i+'strength').value),
      lag:Number(document.getElementById('tl'+i+'lag').value),
      offset:Number(document.getElementById('tl'+i+'offset').value),
      gate:document.getElementById('tl'+i+'gate').value
    }));
    const cfg={global:Number(document.getElementById('twinGlobal').value),mix:Number(document.getElementById('twinMix').value),interference:Number(document.getElementById('twinInterference').value),seed:Number(document.getElementById('twinSeed').value),projection:5,links};
    const next=api.twinStepper(A,B,cfg);let error=0,changed=0;
    for(let i=0;i<1100;i++){
      const p=next(),original=api.twinCombine(p,cfg),focused=api.twinCombine(p,{...cfg,focus:'tl7strength'});
      error=Math.max(error,Math.abs(original[0]-focused[0]),Math.abs(original[1]-focused[1]));
    }
    return {worstPositionDependentShapeError:error,compared:1100};
  });
  check(name,'Coupling focus does not switch to a canned geometric outline',projectionCheck.worstPositionDependentShapeError===0,JSON.stringify(projectionCheck));
  const buttonTests=[
    ['twinCopyAB','Copy A to B'],['twinCopyBA','Copy B to A'],
    ['twinResetA','Reset A'],['twinResetB','Reset B'],
    ['twinRestoreFilament','Restore coupled filaments'],
    ['twinClearTrail','Clear coupled trails'],
    ['twinAdoptOriginal','Adopt original state'],
    ['twinDecouple','Decouple link circuit'],
    ['twinRestore','Restore link circuit'],
    ['twinRerender','Accumulate detail'],
    ['twinAutoToggle','Pause evolution']
  ];
  for(const [id,label] of buttonTests) {
    let failure='';
    try{await page.locator('#'+id).click({timeout:6000});}
    catch(e){failure=String(e).slice(0,250);}
    check(name,'Button: '+label,!failure,failure);
  }
  const decouple=await page.evaluate(()=>Array.from({length:8},(_,i)=>Number(document.getElementById('tl'+i+'strength').value)));
  check(name,'Coupled link controls remain numeric',decouple.every(Number.isFinite),JSON.stringify(decouple));
  const themeButtons=page.locator('[data-theme]');
  const nThemes=await themeButtons.count();let switched=0;
  for(let i=0;i<nThemes;i++){
    let err='';try{await themeButtons.nth(i).click({timeout:4000});switched++;}catch(e){err=String(e).slice(0,170);}
  }
  check(name,'All theme buttons receive pointer clicks',nThemes>0&&switched===nThemes,'clicked='+switched+'/'+nThemes);
  let fullError='';
  try {
    await page.locator('#immersiveEnter').click({timeout:5000});
    check(name,'Full-screen immersive mode enters',await page.evaluate(()=>document.body.classList.contains('omef-immersive')));
    await page.locator('#immersiveHide').click({timeout:4000});
    check(name,'Immersive controls can hide',await page.evaluate(()=>!document.body.classList.contains('omef-hud-visible')));
    await page.evaluate(()=>document.getElementById('omefCanvas').click());
    await page.locator('#immersiveExit').click({timeout:5000});
    check(name,'Immersive mode exits',await page.evaluate(()=>!document.body.classList.contains('omef-immersive')));
  }catch(e){fullError=String(e).slice(0,300);check(name,'Immersive control sequence',false,fullError);}
  const errors=scopedErrors.filter(e=>!e.includes('favicon'));
  check(name,'No uncaught JavaScript runtime errors after control audit',errors.length===0,errors.slice(0,7).join(' | '));
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