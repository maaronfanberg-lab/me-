import { test, expect } from '@playwright/test';

test('QA-HARNESS simulator self-test proves detectors can pass and fail correctly', async ({page}) => {
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('simulator-selftest.html',{waitUntil:'domcontentloaded'});
  await page.locator('#run').click();
  await expect(page.locator('#state')).toContainText(/PASS|FAIL/,{timeout:10000});
  const state=await page.locator('#state').innerText();
  const log=await page.locator('#log').innerText();
  expect(errors,'QA-HARNESS-001 runtime error in self-test').toEqual([]);
  expect(state,'QA-HARNESS-001 self-test did not pass\n'+log).toContain('PASS');
  expect(log,'QA-HARNESS-002 known-bad fixture was not exercised').toContain('UI bounds rejects overflow');
  expect(log,'QA-HARNESS-002 invalid-signal fixture was not exercised').toContain('NaN/Infinity guard rejects invalid signal');
});
