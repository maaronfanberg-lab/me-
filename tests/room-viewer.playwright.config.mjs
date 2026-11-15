import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: ['room-viewer-live.spec.mjs','room-viewer-cors.spec.mjs'],
  timeout: 30000,
  expect: { timeout: 10000 },
  retries: 0,
  workers: 1,
  reporter: [['line']],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...devices['iPhone 13'],
  },
  projects: [
    {
      name: 'mobile-webkit',
      use: {
        browserName: 'webkit',
        ...devices['iPhone 13'],
      },
    },
  ],
});
