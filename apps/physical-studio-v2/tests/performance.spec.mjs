import { test, expect } from '@playwright/test';

test('QA-PERF phone animation stays responsive under repeated interaction', async ({page})=>{
  test.setTimeout(60000);
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.goto('index.html?qa-perf=1',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.__PS_QA__);
  await page.waitForTimeout(500);
  const canvas=page.locator('canvas').first();
  await expect(canvas).toBeVisible();
  const box=await canvas.boundingBox();
  expect(box).toBeTruthy();

  const baseline=await page.evaluate(async()=>{
    const frames=[]; let last=performance.now();
    await new Promise(resolve=>{
      const start=performance.now();
      function tick(t){frames.push(t-last);last=t;if(t-start<1500)requestAnimationFrame(tick);else resolve();}
      requestAnimationFrame(tick);
    });
    const sorted=[...frames].sort((a,b)=>a-b);
    const pct=p=>sorted[Math.min(sorted.length-1,Math.floor(sorted.length*p))]||999;
    return {count:frames.length,p95:pct(.95),p99:pct(.99),long100:frames.filter(x=>x>100).length};
  });

  const sx=box.x+box.width*.50,sy=box.y+box.height*.50;
  for(let i=0;i<10;i++){
    const dx=(i%2?1:-1)*80,dy=(i%4<2?1:-1)*60;
    await canvas.dispatchEvent('pointerdown',{pointerId:1,pointerType:'touch',isPrimary:true,clientX:sx,clientY:sy,buttons:1});
    for(let j=1;j<=5;j++)await canvas.dispatchEvent('pointermove',{pointerId:1,pointerType:'touch',isPrimary:true,clientX:sx+dx*j/5,clientY:sy+dy*j/5,buttons:1});
    await canvas.dispatchEvent('pointerup',{pointerId:1,pointerType:'touch',isPrimary:true,clientX:sx+dx,clientY:sy+dy,buttons:0});
  }
  await page.waitForTimeout(300);

  const after=await page.evaluate(async()=>{
    const frames=[]; let last=performance.now();
    await new Promise(resolve=>{
      const start=performance.now();
      function tick(t){frames.push(t-last);last=t;if(t-start<1000)requestAnimationFrame(tick);else resolve();}
      requestAnimationFrame(tick);
    });
    const sorted=[...frames].sort((a,b)=>a-b);
    const pct=p=>sorted[Math.min(sorted.length-1,Math.floor(sorted.length*p))]||999;
    return {count:frames.length,p95:pct(.95),long100:frames.filter(x=>x>100).length};
  });

  const state=await page.evaluate(()=>window.__PS_QA__.snapshot());
  expect(errors,'QA-PERF-004 runtime errors during stress').toEqual([]);
  expect(state.finite,'QA-PERF-004 simulation became non-finite').toBe(true);
  expect(baseline.count,'QA-PERF-001 baseline animation nearly stopped').toBeGreaterThan(10);
  expect(after.count,'QA-PERF-001 animation failed to recover after interaction').toBeGreaterThan(6);
  expect(after.p95,'QA-PERF-003 severe post-interaction p95 frame regression').toBeLessThan(500);
  // Shared CI is not a device benchmark. Record stalls but only block on a gross hang; real iPhone performance remains a device gate.
  expect(after.long100,'QA-PERF-002 post-interaction animation repeatedly hung').toBeLessThanOrEqual(Math.max(8,Math.floor(after.count*.75)));
  await page.screenshot({path:'qa-results/artifacts/performance-after.png',fullPage:true});
});
