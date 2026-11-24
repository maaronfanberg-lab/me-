const {chromium}=require('playwright');
const path=require('path'),assert=require('assert/strict'),fs=require('fs');
(async()=>{const browser=await chromium.launch({headless:true});const results=[];try{for(const viewport of [{width:1280,height:800},{width:390,height:844}]){
const page=await browser.newPage({viewport,isMobile:viewport.width<500,hasTouch:viewport.width<500});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.goto('file://'+path.resolve('apps/omef-exclusive.html'));await page.waitForFunction(()=>window.OMEFExclusive);
await page.locator('#engineTwin').click();await page.waitForFunction(()=>window.OMEFExclusive.coupledState()?.drawn>1000);
const click=id=>page.locator('#'+id).click();const state=()=>page.evaluate(()=>window.OMEFExclusive.coupledState());
const slider=async(id,v)=>{await page.locator('#'+id).evaluate((e,v)=>{e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));},v)};
await click('twinPause');const frozen=await state(),pixels=await page.locator('#omefCanvas').evaluate(e=>e.toDataURL());await page.waitForTimeout(600);assert.equal((await state()).drawn,frozen.drawn);assert.equal(await page.locator('#omefCanvas').evaluate(e=>e.toDataURL()),pixels);
await slider('twinGlobal',2);await page.waitForTimeout(200);assert.equal((await state()).drawn,frozen.drawn);assert.equal((await state()).targets.global,2);
await click('twinPause');await page.waitForFunction(n=>window.OMEFExclusive.coupledState()?.drawn>n,frozen.drawn);await slider('twinMix',.7);await click('twinDecouple');let st=await state();assert.equal(st.targets.mix,.7);assert.equal(st.targets.global,2);assert(st.targets.links.every(l=>l.strength===0));
await click('twinRestore');st=await state();assert.equal(st.targets.mix,.7);assert(st.targets.links.every(l=>l.strength!==0));
await click('twinRestoreFilament');st=await state();assert.equal(st.targets.global,.45);assert.equal(st.targets.mix,.16);assert.equal(st.targets.seed,1);assert.equal(await page.locator('#twinAutoToggle').getAttribute('aria-pressed'),'false');
await click('twinVerify');assert((await page.locator('#twinSolverReport').textContent()).startsWith('PASS'));assert.deepEqual(errors,[]);
await page.waitForTimeout(1000);await page.locator('#omefCanvas').screenshot({path:'omef-'+viewport.width+'.png'});await click('engineOriginal');assert.equal(await page.evaluate(()=>window.OMEFExclusive.activeMode()),'omef');results.push({viewport,pass:true,errors});await page.close();
}}catch(e){results.push({pass:false,error:String(e),stack:e.stack});process.exitCode=1}finally{await browser.close();fs.writeFileSync('omef-browser-result.json',JSON.stringify(results,null,2));}})().catch(e=>{console.error(e);process.exit(1)});
