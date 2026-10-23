// Which asset each visitor actually gets. GitHub's <themed-picture> JS only kicks in for signed-in users with an
// explicit theme, and it drops width conditions, so this covers every theme setting × OS scheme × width.
import { test, expect } from '@playwright/test';
import { renderMarkdown, showReadme, forceColorMode } from './github.mjs';

const html = renderMarkdown('README.md');

for (const mode of ['auto', 'dark', 'light']) {
  test(`github theme: ${mode}`, async ({ page }, info) => {
    await forceColorMode(page, mode);
    const box = await showReadme(page, html);
    const { colorScheme, viewport } = info.project.use;
    const theme = mode === 'auto' ? colorScheme : mode;
    // Width switching survives only in "auto"; an explicit theme always gets the desktop asset (see themed_picture()).
    const mobile = viewport.width < 768 && mode === 'auto';
    for (const name of ['hero', 'stack']) {
      const src = await box.locator(name === 'hero' ? 'img[alt^="Saad Ardati."]' : 'img[alt^="Stack:"]').evaluate((i) => i.currentSrc);
      expect(src.split('/').pop()).toBe(`${name}${mobile ? '-mobile' : ''}-${theme}.svg`);
    }
  });
}
