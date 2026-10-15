import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  timeout: 30000,
  outputDir: '../artifacts/browser',
  use: {
    baseURL: process.env.TEST_BASE_URL || 'http://127.0.0.1:3001',
    channel: process.env.TEST_BROWSER_CHANNEL || 'msedge',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'off',
  },
});
