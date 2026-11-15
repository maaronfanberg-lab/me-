import { test, expect } from '@playwright/test';

async function canvasBox(page){
  const canvas=page.locator('canvas').first();
  await expect(canvas).toBeVisible();
  const box=await canvas.boundingBox();
  expect(box?.width||0).toBeGreaterThan(100);
  expect(box?.height||0).toBeGreaterThan(100);
  return {canvas,box};
}

async function qaSnapshot(page){
  await page.waitForFunction(()=>!!window.__PS_QA__,null,{timeout:10000});
  return page.evaluate(()=>window.__PS_QA__.snapshot());
}

async function drag(page,dx,dy){
  const {box}=await canvasBox(page);
  const sx=box.x+box.width*.5, sy=box.y+box.height*.52;
  await page.evaluate(({sx,sy,dx,dy})=>{
    const canvas=document.querySelector('canvas');
    if(!canvas)throw new Error('QA-CAM canvas disappeared');
    const fire=(type,x,y,buttons)=>canvas.dispatchEvent(new PointerEvent(type,{pointerId:1,pointerType:'touch',isPrimary:true,clientX:x,clientY:y,buttons,bubbles:true,cancelable:true}));
    fire('pointerdown',sx,sy,1);
    for(let i=1;i<=8;i++)fire('pointermove',sx+dx*i/8,sy+dy*i/8,1);
    fire('pointerup',sx+dx,sy+dy,0);
  },{sx,sy,dx,dy});
  await page.waitForTimeout(180);
}

const dist=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));

for(const path of ['index.html']){
  test.beforeEach(async({page})=>{
    const errors=[];
    page.on('pageerror',e=>errors.push('pageerror:'+e.message));
    page.on('console',m=>{if(m.type()==='error')errors.push('console:'+m.text())});
    await page.goto(path+'?qa-ci=1',{waitUntil:'domcontentloaded'});
    await canvasBox(page);
    await page.waitForTimeout(500);
    page.__qaErrors=errors;
  });

  test('QA-BOOT/REN boot and active WebGL render',async({page})=>{
    const {canvas}=await canvasBox(page);
    const s=await qaSnapshot(page);
    expect(s.model.bodies.length,'QA-REN-002 no scene bodies').toBeGreaterThan(0);
    expect(s.renderer.render.calls,'QA-REN-002 renderer has no draw calls').toBeGreaterThan(0);
    const png=await canvas.screenshot();
    expect(png.length,'QA-REN-002 renderer screenshot empty').toBeGreaterThan(1000);
    expect(page.__qaErrors,'QA-BOOT runtime errors').toEqual([]);
    await page.screenshot({path:'qa-results/artifacts/initial.png',fullPage:true});
  });

  test('QA-CAM horizontal and vertical orbit both change camera',async({page})=>{
    const s0=await qaSnapshot(page);
    await drag(page,120,0); const s1=await qaSnapshot(page);
    expect(dist(s0.camera.position,s1.camera.position),'QA-CAM-001 horizontal orbit no camera change').toBeGreaterThan(.05);
    await drag(page,0,-150); const s2=await qaSnapshot(page);
    expect(dist(s1.camera.position,s2.camera.position),'QA-CAM-002 vertical orbit no camera change').toBeGreaterThan(.05);
    await page.screenshot({path:'qa-results/artifacts/orbit-after.png',fullPage:true});
  });

  test('QA-CAM repeated drags continue instead of sticking',async({page})=>{
    let prior=(await qaSnapshot(page)).camera.position; let changed=0;
    for(let i=0;i<4;i++){await drag(page,105,0);const now=(await qaSnapshot(page)).camera.position;if(dist(prior,now)>.03)changed++;prior=now;}
    expect(changed,'QA-CAM-003 repeated horizontal orbit stuck').toBeGreaterThanOrEqual(3);
    prior=(await qaSnapshot(page)).camera.position;changed=0;
    for(let i=0;i<3;i++){await drag(page,0,-95);const now=(await qaSnapshot(page)).camera.position;if(dist(prior,now)>.03)changed++;prior=now;}
    expect(changed,'QA-CAM-003 repeated vertical orbit stuck').toBeGreaterThanOrEqual(2);
  });

  test('QA-UI controls stay inside phone viewport and activate',async({page})=>{
    const overflow=await page.evaluate(()=>[...document.querySelectorAll('button,input,section,nav')].filter(el=>{const r=el.getBoundingClientRect();return r.width&&r.height&&(r.left<0||r.top<0||r.right>innerWidth+1||r.bottom>innerHeight+1)}).map(el=>el.id||el.className||el.tagName));
    expect(overflow,'QA-UI-001 viewport overflow: '+overflow.join(', ')).toEqual([]);
    const body=page.locator('[data-tool="body"]');await body.click();await expect(body).toHaveClass(/active/);
    const spring=page.locator('[data-tool="spring"]');await spring.click();await expect(spring).toHaveClass(/active/);
  });

  test('QA-AUD actual worklet produces finite decaying signal',async({page})=>{
    const result=await page.evaluate(async()=>{
      const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return {skip:'AudioContext unavailable'};
      const ctx=new AC({latencyHint:'interactive'});await ctx.audioWorklet.addModule('./physics-worklet.js?ci='+Date.now());
      const node=new AudioWorkletNode(ctx,'physical-graph',{outputChannelCount:[2]});
      const analyser=new AnalyserNode(ctx,{fftSize:2048});const mute=new GainNode(ctx,{gain:0});node.connect(analyser).connect(mute).connect(ctx.destination);await ctx.resume();
      node.port.postMessage({t:'graph',bodies:[{mass:1,damping:.1,anchor:true},{mass:1,damping:.14,anchor:false}],springs:[{a:0,b:1,stiffness:450,damping:2.5}]});
      const measure=()=>{const a=new Float32Array(analyser.fftSize);analyser.getFloatTimeDomainData(a);let ss=0,peak=0,dc=0,bad=0;for(const v of a){if(!Number.isFinite(v))bad++;ss+=v*v;dc+=v;peak=Math.max(peak,Math.abs(v))}return{rms:Math.sqrt(ss/a.length),peak,dc:dc/a.length,bad}};
      await new Promise(r=>setTimeout(r,100));const pre=measure();node.port.postMessage({t:'hit',index:1,amount:1.8});await new Promise(r=>setTimeout(r,100));const hit=measure();await new Promise(r=>setTimeout(r,700));const tail=measure();await ctx.close();return{pre,hit,tail};
    });
    test.skip(!!result.skip,result.skip||'');
    expect(result.pre.rms,'QA-AUD unexpected pre-hit noise').toBeLessThan(.01);
    expect(result.hit.rms,'QA-AUD-002 silence after hit').toBeGreaterThan(.00005);
    expect(result.hit.bad,'QA-AUD-004 non-finite samples').toBe(0);
    expect(result.hit.peak,'QA-AUD-003 clipping').toBeLessThan(1.05);
    expect(Math.abs(result.hit.dc),'QA-AUD-006 DC offset').toBeLessThan(.1);
    expect(result.tail.rms,'QA-AUD-005 signal did not decay').toBeLessThan(result.hit.rms);
  });
}
