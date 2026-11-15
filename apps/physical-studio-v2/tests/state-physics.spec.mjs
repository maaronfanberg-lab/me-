import { test, expect } from '@playwright/test';

async function bootQA(page){
  await page.goto('index.html?qa=1',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.__PS_QA__);
  return page.evaluate(()=>window.__PS_QA__.snapshot());
}

const canon=x=>JSON.stringify(x,(k,v)=>typeof v==='number'?Math.round(v*1e8)/1e8:v);

test('QA-PHY direct state remains finite and anchors stay fixed',async({page})=>{
  const initial=await bootQA(page);
  expect(initial.finite,'QA-PHY-001 initial state non-finite').toBe(true);
  const before=await page.evaluate(()=>window.__PS_QA__.validate());
  expect(before.invalidSprings,'QA-PHY-003 invalid spring indices').toEqual([]);
  const anchors0=before.anchors;
  await page.evaluate(()=>{window.__PS_QA__.hit(1,8);window.__PS_QA__.step(800)});
  const after=await page.evaluate(()=>window.__PS_QA__.validate());
  expect(after.finite,'QA-PHY-001 non-finite after stress').toBe(true);
  expect(after.invalidSprings,'QA-PHY-003 invalid spring indices after stress').toEqual([]);
  expect(after.anchors.length).toBe(anchors0.length);
  for(let i=0;i<anchors0.length;i++){
    const a=anchors0[i],b=after.anchors[i];
    expect(Math.hypot(...a.p.map((v,j)=>v-b.p[j])),'QA-PHY-002 anchor moved').toBeLessThan(1e-7);
  }
});

test('QA-PHY hit changes dynamic body and reset restores baseline',async({page})=>{
  const initial=await bootQA(page);
  const p0=initial.model.bodies[1].p;
  const moved=await page.evaluate(()=>{window.__PS_QA__.hit(1,2.5);window.__PS_QA__.step(90);return window.__PS_QA__.snapshot()});
  const p1=moved.model.bodies[1].p;
  expect(Math.hypot(...p0.map((v,i)=>v-p1[i])),'QA-PHY excitation did not move dynamic body').toBeGreaterThan(1e-5);
  const reset=await page.evaluate(()=>{window.__PS_QA__.reset();return window.__PS_QA__.snapshot()});
  expect(reset.finite,'QA-PHY-005 reset non-finite').toBe(true);
  expect(canon(reset.model),'QA-PHY-005 reset did not restore baseline model').toBe(canon(initial.model));
});

test('QA-STATE export/import is lossless for current model schema',async({page})=>{
  await bootQA(page);
  const result=await page.evaluate(()=>{
    const q=window.__PS_QA__;
    const original=q.exportModel();
    const changed=structuredClone(original);
    changed.bodies[1].mass=3.75;
    changed.bodies[2].damping=.77;
    changed.springs[0].stiffness=777;
    changed.springs[0].damping=6.5;
    changed.mic.gain=-17;
    changed.mic.spread=.72;
    changed.exciter.impulse=3.2;
    changed.exciter.hardness=.91;
    const imported=q.importModel(changed);
    return {changed,imported,valid:q.validate()};
  });
  expect(result.valid.finite,'QA-STATE imported model non-finite').toBe(true);
  expect(result.valid.invalidSprings,'QA-STATE imported model has orphan links').toEqual([]);
  expect(canon(result.imported),'QA-STATE-001 round trip changed model').toBe(canon(result.changed));
});

test('QA-PERF renderer resource counts remain bounded across model reset cycles',async({page})=>{
  const initial=await bootQA(page);
  const start=initial.renderer.memory;
  const samples=[];
  for(let i=0;i<12;i++){
    const s=await page.evaluate(()=>{const q=window.__PS_QA__;const m=q.exportModel();q.importModel(m);return q.snapshot().renderer.memory});
    samples.push(s);
  }
  const last=samples.at(-1);
  expect(last.geometries,'QA-PERF resource geometry runaway').toBeLessThanOrEqual(start.geometries+10);
  expect(last.textures,'QA-PERF texture runaway').toBeLessThanOrEqual(start.textures+2);
});
