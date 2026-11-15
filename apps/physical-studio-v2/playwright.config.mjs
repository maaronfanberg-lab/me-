import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  expect: { timeout: 5000 },
  fullyParallel: false,
  workers: 1,
  retries: 1,
  reporter: [
    ['list'],
    ['json', { outputFile: 'qa-results/playwright-results.json' }],
    ['html', { outputFolder: 'qa-results/html', open: 'never' }]
  ],
  use: {
    baseURL: 'http://127.0.0.1:4173/apps/physical-studio-v2/',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  webServer: {
    command: 'python3 -m http.server 4173 --directory ../..',
    url: 'http://127.0.0.1:4173/apps/physical-studio-v2/index.html',
    reuseExistingServer: true,
    timeout: 15000
  },
  projects: [
    {
      name: 'webkit-iphone',
      use: {
        ...devices['iPhone 13'],
        browserName: 'webkit'
      }
    },
    {
      name: 'chromium-phone',
      use: {
        ...devices['iPhone 13'],
        browserName: 'chromium'
      }
    }
  ]
});
