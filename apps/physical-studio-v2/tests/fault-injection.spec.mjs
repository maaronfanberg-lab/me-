import { test, expect } from '@playwright/test';

async function loadQA(page){
  await page.goto('index.html?qa=1',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.__PS_QA__,null,{timeout:10000});
}

function uiOverflowDetector(){
  return [...document.querySelectorAll('button,input,section,nav')].filter(el=>{
    const r=el.getBoundingClientRect();
    return r.width&&r.height&&(r.left<0||r.top<0||r.right>innerWidth+1||r.bottom>innerHeight+1);
  }).length>0;
}

function modelIntegrity(snapshot){
  const n=snapshot.model.bodies.length;
  return snapshot.model.springs.every(s=>Number.isInteger(s.a)&&Number.isInteger(s.b)&&s.a>=0&&s.b>=0&&s.a<n&&s.b<n);
}

test('QA-HARNESS catches deliberate UI overflow',async({page})=>{
  await loadQA(page);
  expect(await page.evaluate(uiOverflowDetector)).toBe(false);
  await page.evaluate(()=>{const b=document.querySelector('#palette button');b.style.position='fixed';b.style.left='calc(100vw + 50px)';});
  expect(await page.evaluate(uiOverflowDetector),'QA-HARNESS-002 failed to catch known-bad UI overflow').toBe(true);
});

test('QA-HARNESS catches missing renderer canvas',async({page})=>{
  await loadQA(page);
  expect(await page.locator('canvas').count()).toBeGreaterThan(0);
  await page.evaluate(()=>document.querySelector('canvas').remove());
  expect(await page.locator('canvas').count(),'QA-HARNESS-002 failed to catch missing canvas').toBe(0);
});

test('QA-HARNESS catches invalid spring reference',async({page})=>{
  await loadQA(page);
  const good=await page.evaluate(()=>window.__PS_QA__.snapshot());
  expect(modelIntegrity(good)).toBe(true);
  const broken=structuredClone(good);
  broken.model.springs[0].a=999999;
  expect(modelIntegrity(broken),'QA-HARNESS-002 failed to catch invalid spring endpoint').toBe(false);
});

test('QA-HARNESS catches non-finite physics state',async({page})=>{
  await loadQA(page);
  const state=await page.evaluate(()=>window.__PS_QA__.snapshot());
  const finite=s=>s.model.bodies.every(b=>b.p.every(Number.isFinite));
  expect(finite(state)).toBe(true);
  state.model.bodies[0].p[0]=NaN;
  expect(finite(state),'QA-HARNESS-002 failed to catch NaN position').toBe(false);
});

test('QA interface can deliberately perturb and restore model',async({page})=>{
  await loadQA(page);
  const before=await page.evaluate(()=>window.__PS_QA__.exportModel());
  await page.evaluate(m=>{const x=structuredClone(m);x.bodies[1].p[1]+=0.75;window.__PS_QA__.importModel(x)},before);
  const changed=await page.evaluate(()=>window.__PS_QA__.exportModel());
  expect(changed.bodies[1].p[1]).not.toBe(before.bodies[1].p[1]);
  await page.evaluate(m=>window.__PS_QA__.importModel(m),before);
  const restored=await page.evaluate(()=>window.__PS_QA__.exportModel());
  expect(restored).toEqual(before);
});
