// Renders a markdown file the way github.com/SaadArdati shows it, using the real live page as the shell.
import { execFileSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, extname } from 'node:path';

const ROOT = resolve(import.meta.dirname, '..');
const REPO = 'SaadArdati/SaadArdati';
const RAW_PREFIXES = [
  `https://github.com/${REPO}/raw/main/`,
  `https://raw.githubusercontent.com/${REPO}/main/`,
  `https://raw.githubusercontent.com/${REPO}/refs/heads/main/`,
];
const LOCAL = RAW_PREFIXES[0];
const TYPES = { '.svg': 'image/svg+xml', '.png': 'image/png', '.gif': 'image/gif', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp' };

// GitHub's /markdown API does the real sanitizing + camo rewriting, but it is an older pipeline than the
// one serving profile READMEs. Patch the known differences (verified against /repos/:r/readme html):
// 1. imgs with numeric width AND height get an aspect-ratio placeholder style + muted bg + 6px radius.
// 2. relative srcs resolve to the repo's raw/main path.
// 3. Live leaves <picture> intact with a bare, unstyled <img> (verified on biomejs/biome, tailwindlabs/tailwindcss).
//    The API auto-links that <img>, and inside an <a> it even hoists it out of <picture>, so <source> selection
//    breaks. Each <picture> is rendered on its own (still sanitized + camo'd), unwrapped, then spliced back.
const api = (text) => execFileSync('gh', ['api', 'markdown', '--input', '-'],
  { input: JSON.stringify({ text, mode: 'markdown', context: REPO }), encoding: 'utf8' });

export function renderMarkdown(file) {
  const pictures = [];
  const source = readFileSync(resolve(ROOT, file), 'utf8')
    .replace(/<picture>[\s\S]*?<\/picture>/g, (pic) => `GHPICTURE${pictures.push(pic) - 1}X`);
  return api(source)
    .replace(/GHPICTURE(\d+)X/g, (_, i) => api(pictures[i])
      .match(/<themed-picture[\s\S]*<\/themed-picture>/)[0]
      .replace(/<a target="_blank" rel="noopener noreferrer(?: nofollow)?" href="[^"]*">(<img\b[^>]*>)<\/a>/g, '$1')
      .replace(/(<img\b[^>]*?) style="[^"]*"/g, '$1'))
    .replace(/<img\b[^>]*>/g, (tag) => {
      const w = tag.match(/\swidth="(\d+)"/)?.[1];
      const h = tag.match(/\sheight="(\d+)"/)?.[1];
      const style = `style="max-width: 100%; height: auto; max-height: ${h}px;"`;
      if (!w || !h || !tag.includes(style)) return tag;
      return tag.replace(style,
        `style="max-width: 100%; height: auto; max-height: ${h}px;; aspect-ratio: ${w} / ${h}; background-color: var(--bgColor-muted); border-radius: 6px" class="js-gh-image-fallback"`);
    })
    .replace(/\s(src|srcset|href)="(?!https?:|#|mailto:|\/)([^"]+)"/g, (_, attr, path) => ` ${attr}="${LOCAL}${path}"`);
}

// Serve own-repo raw URLs (direct or via camo) from the working copy so unpushed assets render.
function localFor(url) {
  if (url.startsWith('https://camo.githubusercontent.com/')) {
    const hex = url.split('/').pop().split('?')[0];
    try { url = Buffer.from(hex, 'hex').toString('utf8'); } catch { return null; }
  }
  const prefix = RAW_PREFIXES.find((p) => url.startsWith(p));
  if (!prefix) return null;
  const path = resolve(ROOT, decodeURIComponent(url.slice(prefix.length).split(/[?#]/)[0]));
  return path.startsWith(ROOT) && existsSync(path) ? path : null;
}

// Signed-in users who pick a GitHub theme get data-color-mode="dark"|"light" server-side instead of "auto", which
// switches <themed-picture> into rewriting <source> media. Logged-out pages are always "auto", so emulate it.
export async function forceColorMode(page, mode) {
  await page.addInitScript((mode) => new MutationObserver(() => {
    const html = document.documentElement;
    if (html.dataset.colorMode && html.dataset.colorMode !== mode) html.dataset.colorMode = mode;
  }).observe(document, { subtree: true, attributes: true, attributeFilter: ['data-color-mode'], childList: true }), mode);
}

export async function showReadme(page, html) {
  await page.route('**/*', (route) => {
    const path = localFor(route.request().url());
    if (!path) return route.continue();
    return route.fulfill({ body: readFileSync(path), contentType: TYPES[extname(path)] ?? 'application/octet-stream' });
  });
  await page.goto('https://github.com/SaadArdati', { waitUntil: 'domcontentloaded' });
  const article = page.locator('.profile-readme article.markdown-body');
  await article.evaluate((el, html) => { el.innerHTML = html; }, html);
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForFunction(() => [...document.querySelectorAll('.profile-readme img')].every((i) => i.complete), null, { timeout: 15000 }).catch(() => {});
  await fitViewport(page);
  return page.locator('.profile-readme');
}

// Element screenshots scroll, and GitHub's JS-driven sticky tab bar then lands on top of the box. A viewport as
// tall as the page means nothing scrolls. Height doesn't affect GitHub's layout; width (the breakpoint) is kept.
export async function fitViewport(page) {
  const { width } = page.viewportSize();
  await page.setViewportSize({ width, height: await page.evaluate(() => document.documentElement.scrollHeight) });
}
