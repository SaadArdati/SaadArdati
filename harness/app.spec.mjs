// The GitHub mobile apps ignore <picture> and show the fallback <img>. Simulate that by stripping every <source>,
// then check the fallback looks exactly like what a browser picks for the same width and colour scheme.
import { test, expect } from '@playwright/test';
import { renderMarkdown, showReadme } from './github.mjs';

const html = renderMarkdown('README.md');
const IMAGES = { hero: 'img[alt^="Saad Ardati."]', stack: 'img[alt^="Stack:"]' };

async function shoot(page, markup, info, tag) {
  const box = await showReadme(page, markup);
  await page.waitForTimeout(2500); // entrance animations finish; reduced-motion emulation doesn't reach SVG-as-image
  const shots = {};
  for (const [name, sel] of Object.entries(IMAGES)) {
    const img = box.locator(sel);
    shots[name] = { src: await img.evaluate((i) => i.currentSrc), png: await img.screenshot({ path: `out/app/${info.project.name}-${tag}-${name}.png` }) };
  }
  return shots;
}

// The tide gradient drifts forever and two loads never share a phase, so the portrait band (top `split` of the
// image) is compared by glyph coverage, which still catches a blank render or the wrong theme's ASCII (light and
// dark ramps are inverted, so their densities differ a lot). Everything below it must match pixel for pixel.
async function compare(page, a, b, split) {
  return page.evaluate(async ([a, b, split]) => {
    const load = (b64) => new Promise((ok) => { const i = new Image(); i.onload = () => ok(i); i.src = 'data:image/png;base64,' + b64; });
    const [ia, ib] = await Promise.all([load(a), load(b)]);
    const px = (i) => { const c = new OffscreenCanvas(i.width, i.height).getContext('2d'); c.drawImage(i, 0, 0); return c.getImageData(0, 0, i.width, i.height).data; };
    const [da, db] = [px(ia), px(ib)];
    if (ia.width !== ib.width || ia.height !== ib.height) return { diff: 1, coverage: [0, 0] };
    const cut = Math.round(ia.width * split) * ia.width * 4; // split is a fraction of width (the SVGs are 400 wide)
    const bg = [da[0], da[1], da[2]];
    const ink = (d) => { let n = 0; for (let k = 0; k < cut; k += 4) if (Math.abs(d[k] - bg[0]) + Math.abs(d[k + 1] - bg[1]) + Math.abs(d[k + 2] - bg[2]) > 40) n++; return n / (cut / 4); };
    let n = 0;
    for (let k = cut; k < da.length; k += 4) if (Math.abs(da[k] - db[k]) + Math.abs(da[k + 1] - db[k + 1]) + Math.abs(da[k + 2] - db[k + 2]) > 30) n++;
    const at = (ib.width * 40 + 40) * 4; // inside the fallback's card, clear of its rounded corner
    return { diff: n / ((da.length - cut) / 4), coverage: [ink(da), ink(db)], card: (db[at] + db[at + 1] + db[at + 2]) / 3 };
  }, [a.toString('base64'), b.toString('base64'), split]);
}

test('app fallback matches browser render', async ({ browser }, info) => {
  test.skip(!info.project.name.includes('mobile'), 'the apps are phone-width');
  const ctx = (await browser.newContext(info.project.use)); // fresh contexts so the two renders share no image cache
  const ctx2 = (await browser.newContext(info.project.use));
  const web = await shoot(await ctx.newPage(), html, info, 'web');
  const app = await shoot(await ctx2.newPage(), html.replace(/<source\b[^>]*>/g, ''), info, 'app');
  const scheme = info.project.use.colorScheme;
  for (const name of Object.keys(IMAGES)) {
    expect(web[name].src, 'browser picks the themed mobile asset').toContain(`${name}-mobile-${scheme}.svg`);
    expect(app[name].src, 'app falls back to the auto asset').toContain(`${name}-mobile-auto.svg`);
    // Mobile hero portrait: 300px tall at y=0 in a 400-wide SVG. The stack doesn't animate.
    const { diff, coverage: [cw, ca], card } = await compare(await ctx.newPage(), web[name].png, app[name].png, name === 'hero' ? 305 / 400 : 0);
    if (diff >= 0.002 && scheme === 'dark' && info.project.name.startsWith('webkit')) {
      // WebKit sometimes resolves the image's scheme as light (it follows the page's color-scheme, which GitHub's CSS
      // races). The fallback's opaque card exists for exactly this: it must then be the legible light card.
      expect(card, `${name}: misfired, so it must be the white light-theme card`).toBeGreaterThan(240);
      test.info().annotations.push({ type: 'webkit scheme misfire', description: `${name} showed the light card` });
      continue;
    }
    expect(diff, `${name}: fallback vs browser, below the portrait`).toBeLessThan(0.002);
    if (name === 'hero') expect(Math.abs(ca - cw) / cw, `portrait glyph coverage ${ca.toFixed(3)} vs ${cw.toFixed(3)}`).toBeLessThan(0.1);
  }
  await ctx.close(); await ctx2.close();
});
