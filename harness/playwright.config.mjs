import { defineConfig } from '@playwright/test';

// Widths measured from the live profile: 1280 → 846px article, 390 → 308px article.
const desktop = { width: 1280, height: 900 };
const mobile = { width: 390, height: 844 };

export default defineConfig({
  testMatch: ['readme.spec.mjs', 'app.spec.mjs', 'theme.spec.mjs'],
  timeout: 60_000,
  reporter: [['list'], ['html', { open: 'never' }]],
  snapshotPathTemplate: 'goldens/{arg}-{projectName}{ext}',
  use: { headless: true },
  projects: [
    ['chromium', 'desktop', 'light'], ['chromium', 'desktop', 'dark'],
    ['chromium', 'mobile', 'light'], ['chromium', 'mobile', 'dark'],
    // WebKit = Safari, which has known prefers-color-scheme-inside-SVG bugs.
    ['webkit', 'desktop', 'light'], ['webkit', 'desktop', 'dark'],
    // WebKit mobile ≈ the iOS app's WKWebView; Chromium mobile ≈ Android's WebView.
    ['webkit', 'mobile', 'light'], ['webkit', 'mobile', 'dark'],
  ].map(([browserName, size, colorScheme]) => ({
    name: `${browserName}-${size}-${colorScheme}`,
    use: { browserName, colorScheme, viewport: size === 'desktop' ? desktop : mobile, deviceScaleFactor: 2 },
  })),
});
