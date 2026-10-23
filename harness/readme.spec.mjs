import { test, expect } from '@playwright/test';
import { renderMarkdown, showReadme, fitViewport } from './github.mjs';

test('README.md', async ({ page }, info) => {
  const box = await showReadme(page, renderMarkdown('README.md'));
  await page.waitForTimeout(2500); // the hero's entrance animations finish; the tide drift stays within maxDiffPixelRatio
  await box.screenshot({ path: `out/README/${info.project.name}.png` });
  await expect(box).toHaveScreenshot('README.png', { animations: 'allow', scale: 'device', maxDiffPixelRatio: 0.01 });
});

// Untouched live profile, for eyeballing harness fidelity against what GitHub actually serves.
test('live', async ({ page }, info) => {
  await page.goto('https://github.com/SaadArdati', { waitUntil: 'load' });
  await fitViewport(page);
  await page.locator('.profile-readme').screenshot({ path: `out/live/${info.project.name}.png` });
});
