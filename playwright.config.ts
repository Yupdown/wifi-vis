import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './web-tests',
  timeout: 90000,
  fullyParallel: false,
  workers: 1,
  use: {
    channel: process.platform === 'win32' ? 'chrome' : undefined,
    viewport: { width: 920, height: 980 },
    baseURL: 'http://127.0.0.1:5173',
    launchOptions: { args: ['--enable-webgl', '--ignore-gpu-blocklist'] },
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run dev -- --port 5173 --strictPort',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
