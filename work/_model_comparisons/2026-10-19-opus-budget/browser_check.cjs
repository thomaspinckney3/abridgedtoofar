const {chromium} = require('/mnt/data/playwright-cache/node/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: '/home/tp/.cache/ms-playwright/chromium-1187/chrome-linux/chrome',
    args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto('file://' + path.join(__dirname, 'report.html'));
    const payload = await page.locator('#data').textContent().then(JSON.parse);
    assert.equal(payload.checks.words, 2376);
    assert.equal(payload.checks.protected.filter(x => x.present).length, 9);
    assert.equal(payload.notes.acceptable_changes.length, 19);
    assert.equal(await page.locator('#metrics tr').count(), 7);
    assert.equal(await page.locator('#evidence > details').count(), 6);
    assert.equal(await page.locator('#cuts li').count(), 6);
    let variantsChecked = 0;
    const normalize = s => s.trim().replace(/\s+/g, ' ');
    for (const side of ['left', 'right']) {
      for (const variant of Object.keys(payload.labels)) {
        await page.selectOption('#' + side, variant);
        const text = await page.locator('#' + side + 'Text p').allTextContents();
        const filename = variant === 'revision' ? 'revision.md' : 'inputs/' + variant + '.md';
        assert.equal(normalize(text.join('\n\n')), normalize(fs.readFileSync(path.join(__dirname, filename), 'utf8')));
        variantsChecked++;
      }
    }
    await page.selectOption('#left', 'opus_before');
    await page.selectOption('#right', 'revision');
    await page.screenshot({path: path.join(__dirname, 'report-preview.png')});
    await page.setViewportSize({width: 390, height: 844});
    await page.evaluate(() => document.querySelectorAll('details').forEach(d => d.open = true));
    const sizes = await page.evaluate(() => ({viewport: window.innerWidth, document: document.documentElement.scrollWidth}));
    assert(sizes.document <= sizes.viewport, JSON.stringify(sizes));
    const localLinks = await page.locator('a').evaluateAll(links => links.map(x => x.getAttribute('href')));
    for (const href of localLinks) assert(fs.existsSync(path.resolve(__dirname, href)), href);
    await page.goto('file://' + path.join(__dirname, 'word_diff.html'));
    assert(await page.locator('del').count() > 0);
    assert(await page.locator('ins').count() > 0);
    assert.deepEqual(errors, []);
    const result = {status: 'pass', reader_selections_checked: variantsChecked, protected_spans: 9,
      exact_paragraph_examples: payload.assessment.examples.reduce((n, x) => n + x.passages.length, 0),
      raw_change_notes: 19, local_links_checked: localLinks.length, mobile_width: sizes,
      javascript_errors: errors, diff_load: 'pass'};
    fs.writeFileSync(path.join(__dirname, 'browser_verification.json'), JSON.stringify(result, null, 2) + '\n');
    console.log(JSON.stringify(result, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
