/**
 * Class 10 — stored XSS, observed in a real browser.
 *
 *   node verify_browser.js before <evidence-dir>   # stored <script> must RUN
 *   node verify_browser.js after  <evidence-dir>   # same value must be shown as text
 *   node verify_browser.js normal <evidence-dir>   # a normal comment still displays
 *
 * "before" expects an alert dialog and a script element inside the comment cell.
 * "after"  expects no dialog and the literal characters <script>…</script>.
 * "normal" expects a comment with < and & to read back exactly as written.
 *
 * curl only shows the HTML; this drives Chrome/Edge so "shown" vs "run" is observed.
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const MODE = ['before', 'after', 'normal'].includes(process.argv[2]) ? process.argv[2] : 'before';
const OUT = path.resolve(process.argv[3] || '.');
const BASE = process.env.NOTESAPP_BASE || 'http://127.0.0.1:8080';

const MODES = {
  before: {
    marker: 'XSS by Eve',
    payload: "<script>alert('XSS by Eve')</script>",
    expect: { alert: true, scriptElement: true, literal: false, entities: false },
  },
  after: {
    marker: 'XSS by Eve',
    payload: "<script>alert('XSS by Eve')</script>",
    expect: { alert: false, scriptElement: false, literal: true, entities: true },
  },
  normal: {
    marker: 'score < 10',
    payload: 'score < 10 on part 1 & 2, see me',
    expect: { alert: false, scriptElement: false, literal: true, entities: true },
  },
};

const CFG = MODES[MODE];
const BROWSERS = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
];
const EXE = BROWSERS.find((p) => fs.existsSync(p));

async function cellFor(page, marker) {
  return page.evaluate((needle) => {
    const cells = Array.from(document.querySelectorAll('td'));
    const cell = cells.find((c) => c.innerHTML.includes(needle) || c.textContent.includes(needle));
    if (!cell) return null;
    return {
      innerHTML: cell.innerHTML,
      textContent: cell.textContent,
      hasScriptElement: !!cell.querySelector('script'),
    };
  }, marker);
}

async function probePage(page, url) {
  const dialogs = [];
  page.on('dialog', async (dialog) => {
    dialogs.push({ type: dialog.type(), message: dialog.message() });
    await dialog.dismiss();
  });
  await page.goto(url);
  await page.waitForTimeout(1200); // let any stored script run before we look
  const cell = await cellFor(page, CFG.marker);
  const scriptCount = await page.evaluate(() => document.querySelectorAll('script').length);
  const name = path.basename(url) + '-' + MODE + '.png';
  const shot = path.join(OUT, name);
  await page.screenshot({ path: shot, fullPage: true });
  return { url: page.url(), dialogs, script_elements: scriptCount, comment_cell: cell, screenshot: shot };
}

async function login(page, username, password, landing) {
  await page.goto(BASE + '/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Log in' }).click();
  await page.waitForURL('**' + landing);
}

(async () => {
  if (!EXE) throw new Error('Chrome or Edge not found');
  fs.mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch({ executablePath: EXE, headless: true });
  const result = { mode: MODE, base: BASE, executable: EXE, browser_version: browser.version() };

  try {
    // alice, the victim: her own dashboard holds the stored comment (note 1)
    const aliceCtx = await browser.newContext({ viewport: { width: 1200, height: 900 } });
    const alicePage = await aliceCtx.newPage();
    await login(alicePage, 'alice', 'alicepw', '/dashboard');
    result.alice = await probePage(alicePage, BASE + '/dashboard');
    await aliceCtx.close();

    // the teacher's own list carries the same template line
    const teacherCtx = await browser.newContext({ viewport: { width: 1200, height: 1200 } });
    const teacherPage = await teacherCtx.newPage();
    await login(teacherPage, 'prof.turing', 'teach123', '/teacher');
    result.teacher = await probePage(teacherPage, BASE + '/teacher');
    await teacherCtx.close();

    const cell = result.alice.comment_cell || {};
    const tcell = result.teacher.comment_cell || {};
    result.checks = {
      alert_fired_in_alice_browser: result.alice.dialogs.some((d) => d.type === 'alert'),
      raw_script_in_alice_page: !!cell.hasScriptElement,
      alice_cell_shows_literal_payload: cell.textContent === CFG.payload,
      alice_cell_uses_html_entities:
        !!cell.innerHTML && cell.innerHTML.includes('&lt;') && (MODE !== 'normal' || cell.innerHTML.includes('&amp;')),
      teacher_page_same_state:
        MODE === 'before'
          ? !!tcell.hasScriptElement
          : !!tcell.innerHTML && !tcell.hasScriptElement && tcell.textContent === CFG.payload,
    };
    const expected = {
      alert_fired_in_alice_browser: CFG.expect.alert,
      raw_script_in_alice_page: CFG.expect.scriptElement,
      alice_cell_shows_literal_payload: CFG.expect.literal,
      alice_cell_uses_html_entities: CFG.expect.entities,
      teacher_page_same_state: true,
    };
    result.expected = expected;
    result.passed = Object.keys(expected).every((k) => result.checks[k] === expected[k]);
  } finally {
    await browser.close();
  }

  const file = path.join(OUT, 'browser-' + MODE + '.json');
  fs.writeFileSync(file, JSON.stringify(result, null, 2) + '\n', 'utf8');
  console.log(JSON.stringify(result, null, 2));
  console.log(MODE + ' browser checks: ' + (result.passed ? 'PASS' : 'FAIL') + ' -> ' + file);
  process.exit(result.passed ? 0 : 1);
})().catch((err) => {
  console.error('browser check failed:', err);
  process.exit(2);
});
