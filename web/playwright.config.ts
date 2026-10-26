import { defineConfig, devices } from '@playwright/test'

// E2E_URL=https://xxxx.cloudfront.net npx playwright test   (default: `make local` on :8077)
export default defineConfig({
  workers: 1, // tests share one backend, and the WhatsApp switch test changes a global setting
  testDir: './e2e',
  timeout: 180_000,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_URL || 'http://localhost:8077',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1366, height: 900 } }, grepInvert: /@mobile/ },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, grep: /@mobile/ },
  ],
})
