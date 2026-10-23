"""Builds README.md and its themed SVGs in assets/. Run: python3 -I scripts/build_readme.py

Stats are fetched live (CurseForge via cfwidget, pub.dev) and rounded up to the next 5. If a source is down,
the last good numbers in scripts/stats.json are reused. CI runs this on a schedule (.github/workflows/readme.yml).
"""
import json, math, re, subprocess, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / 'scripts'
RAW = 'https://raw.githubusercontent.com/SaadArdati/SaadArdati/main/assets'

RAMP = ' .:-=+*#%@'
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
CHAR_ASPECT = 0.6  # monospace advance / font-size; textLength pins it so every OS font lines up
LINE = 1.1
NBSP = ' '  # Chrome collapses regular spaces in SVG text despite xml:space, wrecking alignment
THEMES = {
    'dark': dict(fg='#f0f6fc', muted='#9198a1', faint='#3d444d', bg='#0d1117'),
    'light': dict(fg='#1f2328', muted='#59636e', faint='#d1d9e0', bg='#ffffff'),
}
TIDE = {  # saad-ardati.dev logo 'tide' noise ranges: deep blue → cyan. Dark is lifted off #0d1117.
    'dark': ['#2b6cf0', '#1fa5e0', '#4ff0ff', '#1fa5e0', '#2b6cf0'],
    'light': ['#0a2f8a', '#0e6aa0', '#0a95b0', '#0e6aa0', '#0a2f8a'],
}

TAGLINE = 'Software Engineer · Open Source Creator · Caffeine Consumer'
LABEL = 'Saad Ardati. Software Engineer, Open Source Creator, Caffeine Consumer. Beirut, Lebanon.'
BIO = ('Full-stack software engineer, team lead and Flutter expert for over 6 years. I build scalable backend systems and high-performance '
       'cross-platform apps for mobile and desktop. Along the way I led engineering at an AI startup and directed an open-source team of 8 for 7 years.\n\n'
       'Beirut is home and coffee is load-bearing.')
STACK = [  # (group, [(simple-icons slug, label)]). Java's mark lives under 'openjdk'.
    ('languages', [('dart', 'Dart'), ('openjdk', 'Java'), ('typescript', 'TypeScript'), ('kotlin', 'Kotlin'), ('swift', 'Swift'), ('python', 'Python')]),
    ('frameworks', [('flutter', 'Flutter'), ('springboot', 'Spring Boot'), ('nodedotjs', 'Node.js')]),
    ('cloud & data', [('firebase', 'Firebase'), ('googlecloud', 'Google Cloud'), ('supabase', 'Supabase'), ('postgresql', 'PostgreSQL'), ('docker', 'Docker')]),
    ('tooling', [('git', 'Git'), ('githubactions', 'GitHub Actions'), ('codemagic', 'Codemagic'), ('figma', 'Figma'), ('intellijidea', 'IntelliJ IDEA'), ('linux', 'Linux')]),
]
CORE = [('flutter', 'Flutter'), ('dart', 'Dart'), ('openjdk', 'Java'), ('typescript', 'TypeScript'), ('firebase', 'Firebase'), ('googlecloud', 'Google Cloud'), ('supabase', 'Supabase')]
PACKAGES = [
    ('plugin_kit', 'pure Dart plugin runtime with lifecycle and events'),
    ('flutter_box_transform', 'resizable, draggable boxes with handles (co-maintained)'),
    ('hyper_effects', 'scroll and pointer effects with minimal code'),
    ('flutter_operations', 'type-safe async operation state management'),
    ('hyper_logger', 'structured, hierarchical logging for Dart'),
]
ARTICLES = [
    ('Flutter Operations Part II: Dart Zones & Unrepresentation', 'https://medium.com/@saadoardati/flutter-operations-part-ii-dart-zones-unrepresentation-0a200d1df939', 2026),
    ('Building the Plugin Runtime Dart Is Missing', 'https://medium.com/@saadoardati/building-the-plugin-runtime-dart-is-missing-913a1701ac0f', 2026),
    ('Exhaustive Pattern Matching for Exhausted Flutter Developers', 'https://medium.com/@saadoardati/exhaustive-pattern-matching-for-exhausted-flutter-developers-cd6837459862', 2025),
    ('Mastering Resizable & Draggable Boxes with Flutter Box Transform', 'https://medium.com/@saadoardati/mastering-resizable-draggable-boxes-with-flutter-box-transform-building-figmas-crop-ui-461ad264af3f', 2023),
    ('Flying High with Flutter, podcast interview', 'https://youtu.be/iOqRqV0IiGI', 2023),
]
LINKS = [('saad-ardati.dev', 'https://saad-ardati.dev'), ('LinkedIn', 'https://linkedin.com/in/saad-ardati'), ('X', 'https://twitter.com/SaadArdati'),
         ('Bluesky', 'https://bsky.app/profile/saad-ardati.dev'), ('Medium', 'https://medium.com/@saadoardati'), ('Email', 'mailto:saadoardati@gmail.com')]
MODS = ['wizardry-mod', 'librarianlib', 'refraction', 'shotguns-glitter']
PUBLISHERS = ['hyperdesigned.dev', 'saad-ardati.dev']


# ── Stats ───────────────────────────────────────────────────────────────────
def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'SaadArdati-readme (github.com/SaadArdati/SaadArdati)'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_stats():
    mods = sum(get_json(f'https://api.cfwidget.com/minecraft/mc-mods/{m}')['downloads']['total'] for m in MODS)
    packages = set()
    for pub in PUBLISHERS:
        url = f'https://pub.dev/api/search?q=publisher:{pub}'
        while url:
            page = get_json(url)
            packages |= {p['package'] for p in page['packages']}
            url = page.get('next')
    monthly = sum(get_json(f'https://pub.dev/api/packages/{p}/score')['downloadCount30Days'] or 0 for p in sorted(packages))
    return {'mod_downloads': mods, 'pub_monthly_downloads': monthly}


def load_stats():
    cache = HERE / 'stats.json'
    try:
        stats = fetch_stats()
        cache.write_text(json.dumps(stats, indent=2) + '\n')
    except Exception as e:  # a flaky third-party API must not break the README
        print(f'stats fetch failed ({e}); using {cache.name}')
        stats = json.loads(cache.read_text())
    return stats


def up5(n, unit, suffix):
    """Rounds up to the next multiple of 5 in the display unit: 38.45M → 40M+."""
    return f'{math.ceil(n / unit / 5) * 5}{suffix}+'


# ── SVG primitives ──────────────────────────────────────────────────────────
def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def ascii_rows(cols, theme):
    """Luminance → glyph density. Dark theme: bright = dense. Light theme: dark = dense.
    Contrast is stretched over opaque pixels only; unsharp mask keeps glasses + beard edges legible."""
    src = Image.open(HERE / 'headshot.png').convert('RGBA')
    rows = round(cols * CHAR_ASPECT / LINE)
    alpha = src.split()[3].resize((cols, rows), Image.LANCZOS)
    lum = src.convert('L').filter(ImageFilter.UnsharpMask(6, 160, 2)).resize((cols, rows), Image.LANCZOS)
    vals = sorted(lum.getpixel((x, y)) for y in range(rows) for x in range(cols) if alpha.getpixel((x, y)) > 128)
    lo, hi = vals[len(vals) * 2 // 100], vals[len(vals) * 98 // 100]
    out = []
    for y in range(rows):
        line = ''
        for x in range(cols):
            if alpha.getpixel((x, y)) < 77:
                line += ' '
                continue
            v = min(1, max(0, (lum.getpixel((x, y)) - lo) / (hi - lo)))
            v = (v if theme == 'dark' else 1 - v) ** 0.8
            line += RAMP[min(len(RAMP) - 1, int(v * len(RAMP)))]
        out.append(line)
    return out


def ascii_text(rows, x, y, width):
    cw = width / len(rows[0])
    fs = cw / CHAR_ASPECT
    lh = fs * LINE
    out = [f'<text class="mono" x="{x:.2f}" y="{y + (i + 1) * lh:.2f}" font-size="{fs:.3f}" textLength="{width:.2f}" '
           f'lengthAdjust="spacingAndGlyphs">{esc(r).replace(" ", NBSP)}</text>' for i, r in enumerate(rows)]
    return '\n'.join(out), len(rows) * lh


def css(theme, w=None, scope='svg'):
    pre = '' if scope == 'svg' else scope + ' '
    t, tide = THEMES[theme], TIDE[theme]
    # The portrait gradient vector is (w, .35w); one repeat along x is |v|^2 / vx = 1.1225w, so the loop is seamless.
    motion = f'''{pre}.tide {{ animation: tide 14s linear infinite; }}
@keyframes tide {{ to {{ transform: translateX(-{w * 1.1225:.2f}px); }} }}
{pre}.reveal {{ animation: reveal 1.4s ease-out both; }}
@keyframes reveal {{ from {{ opacity: 0; }} }}''' if w else ''
    return f"""<style>
{scope} {{ font-family: {SANS}; fill: {t['fg']}; }}
{pre}.mono {{ font-family: {MONO}; }}
{pre}.muted {{ fill: {t['muted']}; }}
{pre}.accent {{ fill: {tide[1]}; }}
{pre}.num {{ fill: url(#tg); }}
{pre}.pill {{ stroke: {tide[1]}; stroke-opacity: .45; }}
{pre}.in {{ animation: rise .8s cubic-bezier(.2,.7,.2,1) both; }}
@keyframes rise {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
{motion}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
</style>"""


def svg(w, h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">\n{body}\n</svg>\n')


def write(name, content):
    if name.endswith('.svg'):
        ET.fromstring(content)  # an invalid SVG renders as a broken image on GitHub, so fail the build instead
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f'{len(content) / 1024:6.1f} KB  {name}')


def fade_mask(id_, x, y, w, h):
    return (f'<linearGradient id="{id_}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/>'
            f'<stop offset=".72" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            f'<mask id="{id_}" maskUnits="userSpaceOnUse"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{id_}g)"/></mask>')


def tide_grad(theme, x1, x2):
    """Stat numbers carry the same tide gradient as the portrait."""
    stops = ''.join(f'<stop offset="{i / 2}" stop-color="{c}"/>' for i, c in enumerate(TIDE[theme][:3]))
    return f'<linearGradient id="tg" gradientUnits="userSpaceOnUse" x1="{x1}" y1="0" x2="{x2}" y2="0">{stops}</linearGradient>'


# ── Icons: simple-icons (CC0), resolved through the package's own exports ──
def load_icons():
    slugs = sorted({s for _, items in STACK for s, _ in items} | {s for s, _ in CORE})
    js = ("import * as si from 'simple-icons'; const by = Object.fromEntries(Object.values(si).filter((i) => i && i.slug).map((i) => [i.slug, i]));"
          f"console.log(JSON.stringify(Object.fromEntries({json.dumps(slugs)}.map((s) => [s, by[s].path]))))")
    out = subprocess.run(['node', '--input-type=module', '-e', js], cwd=HERE, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


ICONS = load_icons()


def icon(slug, x, y, size, theme):
    return f'<svg x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" viewBox="0 0 24 24"><path fill="{TIDE[theme][1]}" d="{ICONS[slug]}"/></svg>'


# ── Hero ────────────────────────────────────────────────────────────────────
def portrait(theme, x, y, w, cols, uid):
    """ASCII glyphs as a mask over a tide gradient that slides one period sideways, forever."""
    art, ah = ascii_text(ascii_rows(cols, theme), x, y, w)
    stops = ''.join(f'<stop offset="{i / 4}" stop-color="{c}"/>' for i, c in enumerate(TIDE[theme]))
    defs = (fade_mask(f'f{uid}', x - 10, y, w + 20, ah)
            + f'<mask id="g{uid}" maskUnits="userSpaceOnUse"><g fill="#fff" mask="url(#f{uid})">{art}</g></mask>'
            + f'<linearGradient id="t{uid}" gradientUnits="userSpaceOnUse" x1="{x}" y1="0" x2="{x + w}" y2="{w * .35:.0f}" spreadMethod="repeat">{stops}</linearGradient>')
    body = f'<g mask="url(#g{uid})" class="reveal"><g class="tide"><rect x="{x - w}" y="{y}" width="{w * 3}" height="{ah:.0f}" fill="url(#t{uid})"/></g></g>'
    return defs, body, ah


def stats_row(stats, x, y, center=None):
    """One row by content width on desktop; a centred 2×2 on mobile."""
    out = []
    anchor = '' if center is None else ' text-anchor="middle"'
    widths = [max(len(l) * 12.5 * CHAR_ASPECT, len(n) * 30 * .58) + 34 for n, l in stats]
    for i, (num, label) in enumerate(stats):
        if center is None:
            cx, cy = x + sum(widths[:i]), y + 12
        else:
            cx, cy = x + (i % 2) * center / 2 + center / 4, y + 12 + (i // 2) * 62
            if i == len(stats) - 1 and i % 2 == 0:
                cx = x + center / 2  # odd one out sits centred under the pair
        out.append(f'<text class="in num" x="{cx:.1f}" y="{cy + 18}" font-size="30" font-weight="600" letter-spacing="-.8"{anchor} style="animation-delay:{500 + i * 90}ms">{num}</text>'
                   f'<text class="mono muted in" x="{cx:.1f}" y="{cy + 40}" font-size="12.5"{anchor} style="animation-delay:{540 + i * 90}ms">{esc(label)}</text>')
    rows = 1 if center is None else -(-len(stats) // 2)
    return '\n'.join(out), y + 12 + rows * 62


def chips(theme, items, x, y, maxw, center=False):
    rows, cur = [], []
    for slug, name in items:
        pw = len(name) * 7.8 + 44
        if sum(p for _, p in cur) + 8 * len(cur) + pw > maxw:
            rows.append(cur)
            cur = []
        cur.append(((slug, name), pw))
    rows.append(cur)
    out = []
    for r, row in enumerate(rows):
        rw = sum(p for _, p in row) + 8 * (len(row) - 1)
        px = x + ((maxw - rw) / 2 if center else 0)
        for (slug, name), pw in row:
            py = y + 6 + r * 38
            out.append(f'<g class="in" style="animation-delay:{500 + len(out) * 60}ms"><rect class="pill" x="{px:.1f}" y="{py}" width="{pw:.1f}" height="28" rx="14" fill="none"/>'
                       f'{icon(slug, px + 12, py + 6.5, 15, theme)}<text class="mono muted" x="{px + pw / 2 + 10:.1f}" y="{py + 18.5}" font-size="13" text-anchor="middle">{esc(name)}</text></g>')
            px += pw + 8
    return '\n'.join(out), y + 6 + len(rows) * 38


def hero(theme, stats, scope='svg'):
    """Desktop: text left, portrait right, centred against the text column."""
    tx = 0
    s, bottom = stats_row(stats, tx, 172)
    c, bottom = chips(theme, CORE, tx, bottom + 6, 480)
    h = round(max(290, bottom + 6))
    defs, art, _ = portrait(theme, 556, (h - 290) / 2, 290, 84, 'd')
    return 846, h, f"""{css(theme, 290, scope)}
<defs>{defs}{tide_grad(theme, tx, tx + 520)}</defs>
{art}
<text class="mono accent in" x="{tx + 2}" y="78" font-size="13" letter-spacing="1.5" style="animation-delay:200ms">BEIRUT, LEBANON</text>
<text class="in" x="{tx}" y="128" font-size="52" font-weight="600" letter-spacing="-1.5" style="animation-delay:300ms">Saad Ardati</text>
<text class="muted in" x="{tx + 2}" y="160" font-size="16.5" style="animation-delay:400ms">{TAGLINE}</text>
{s}
{c}"""


def hero_mobile(theme, stats, scope='svg'):
    """Stacked and centred, swapped in by a (max-width) <source>."""
    defs, art, y = portrait(theme, 50, 0, 300, 80, 'm')
    s, bottom = stats_row(stats, 30, y + 148, center=340)
    c, bottom = chips(theme, CORE, 30, bottom + 6, 340, center=True)
    return 400, round(bottom + 18), f"""{css(theme, 300, scope)}
<defs>{defs}{tide_grad(theme, 30, 370)}</defs>
{art}
<text class="mono accent in" x="200" y="{y + 20}" font-size="14" letter-spacing="1.5" text-anchor="middle">BEIRUT, LEBANON</text>
<text class="in" x="200" y="{y + 72}" font-size="46" font-weight="600" letter-spacing="-1.2" text-anchor="middle">Saad Ardati</text>
<text class="muted in" x="200" y="{y + 104}" font-size="19" text-anchor="middle">Software Engineer · Open Source Creator</text>
<text class="muted in" x="200" y="{y + 130}" font-size="19" text-anchor="middle">Caffeine Consumer</text>
{s}
{c}"""


def stack(theme, mobile, scope='svg'):
    # Mobile gets an inner margin so it still breathes inside the auto fallback's card.
    pad = 16 if mobile else 0
    W, fs, isz = (400 - 2 * pad, 15, 20) if mobile else (846, 14, 20)
    lx = 0 if mobile else 150
    out, y = [], 0
    for gi, (group, items) in enumerate(STACK):
        if gi:
            out.append(f'<path d="M0 {y + .5} H{W}" stroke="{THEMES[theme]["faint"]}"/>')
            y += 14
        out.append(f'<text class="mono accent" x="0" y="{y + 19}" font-size="12" letter-spacing="1.5">{esc(group.upper())}</text>')
        if mobile:
            y += 30
        x, row_y = lx, y
        for slug, label in items:
            w = isz + 8 + len(label) * fs * .56
            if x + w > W:
                x, row_y = lx, row_y + 34
            out.append(f'{icon(slug, x, row_y + 4, isz, theme)}<text x="{x + isz + 8:.1f}" y="{row_y + 19}" font-size="{fs}">{esc(label)}</text>')
            x += w + 18
        y = row_y + 40
    return W + 2 * pad, round(y - 12 + 2 * pad), css(theme, scope=scope) + f'<g transform="translate({pad} {pad})">' + '\n'.join(out) + '</g>'


STACK_ALT = 'Stack: ' + ', '.join(l for _, g in STACK for _, l in g)


def auto(build, alt):
    """Fallback for clients that ignore <picture> (the GitHub mobile apps): both themes in one document, the OS
    colour scheme shows one. Each theme is a nested <svg> with its own id prefix and scoped CSS.
    Each layer sits on an opaque card in GitHub's own background colour: invisible when the scheme is detected, and
    still legible when it isn't. WebKit takes an SVG image's colour scheme from the embedding page's `color-scheme`,
    which an app's web view may not set (in the harness, GitHub's own CSS races it and the light layer wins sometimes). Nested data-URI
    <image>s would be simpler, but Chromium (so Android's WebView) never paints images inside an SVG image."""
    parts = []
    for theme in THEMES:
        w, h, body = build(theme, f'.{theme}')
        body = re.sub(r'id="', f'id="{theme[0]}-', body).replace('url(#', f'url(#{theme[0]}-')
        card = f'<rect width="{w}" height="{h}" rx="12" fill="{THEMES[theme]["bg"]}"/>'
        parts.append(f'<svg class="{theme}" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n{card}\n{body}\n</svg>')
    return svg(w, h, """<style>
.dark { display: none; }
@media (prefers-color-scheme: dark) { .light { display: none; } .dark { display: inline; } }
</style>
""" + '\n'.join(parts), alt)


# ── README ──────────────────────────────────────────────────────────────────
def themed_picture(base, alt):
    """Signed-in users with an explicit GitHub theme get <themed-picture> JS that rewrites every source mentioning
    prefers-color-scheme to "always" (matching theme) or "not all", dropping any width condition. So the desktop
    sources come first: logged-out and system-theme visitors still get width switching, explicit-theme visitors get
    the desktop asset at every width (scaled down on phones, never the stacked hero on a desktop). Apps that ignore
    <picture> get the narrow, OS-themed fallback."""
    return f'''<picture>
  <source media="(min-width: 768px) and (prefers-color-scheme: dark)" srcset="{RAW}/{base}-dark.svg">
  <source media="(min-width: 768px) and (prefers-color-scheme: light)" srcset="{RAW}/{base}-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="{RAW}/{base}-mobile-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="{RAW}/{base}-mobile-light.svg">
  <img alt="{alt}" src="{RAW}/{base}-mobile-auto.svg" width="100%">
</picture>'''


def readme():
    packages = '\n'.join(f'- [**{n}**](https://pub.dev/packages/{n}), {d}' for n, d in PACKAGES)
    writing = '| Article | Year |\n|:--|--:|\n' + '\n'.join(f'| [{a}]({u}) | {y} |' for a, u, y in ARTICLES)
    links = ' &nbsp;·&nbsp; '.join(f'<a href="{u}">{n}</a>' for n, u in LINKS)
    write('README.md', f"""<!-- Generated by scripts/build_readme.py. Edit that, not this. -->
{themed_picture('hero', LABEL)}

<br>

{BIO}

### Stack

{themed_picture('stack', STACK_ALT)}

### Open source

{packages}

### Writing

{writing}

### Stickers

<!-- width + height on purpose: GitHub's image placeholder style gives the board 6px rounded corners and a stable aspect ratio. -->
<a href="https://holopin.io/@saadardati"><img src="https://holopin.me/saadardati" alt="Saad's Holopin sticker board" width="846" height="266"></a>

<br>

<p align="center">{links}</p>
""")


if __name__ == '__main__':
    raw = load_stats()
    stats = [(up5(raw['mod_downloads'], 1e6, 'M'), 'mod downloads'),
             (up5(raw['pub_monthly_downloads'], 1e3, 'k'), 'package downloads / mo'),
             ('5', 'platforms shipped')]
    builds = {
        'hero': (lambda t, sc='svg': hero(t, stats, sc), LABEL),
        'hero-mobile': (lambda t, sc='svg': hero_mobile(t, stats, sc), LABEL),
        'stack': (lambda t, sc='svg': stack(t, False, sc), STACK_ALT),
        'stack-mobile': (lambda t, sc='svg': stack(t, True, sc), STACK_ALT),
    }
    for name, (build, alt) in builds.items():
        for theme in THEMES:
            write(f'assets/{name}-{theme}.svg', svg(*build(theme), alt))
        if name.endswith('-mobile'):  # the README's <img> fallback; see themed_picture()
            write(f'assets/{name}-auto.svg', auto(build, alt))
    readme()
