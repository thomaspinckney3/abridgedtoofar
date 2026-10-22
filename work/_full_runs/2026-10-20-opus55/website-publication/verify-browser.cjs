const { chromium } = require('/mnt/data/playwright-cache/node/node_modules/playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/home/tp/.cache/ms-playwright/chromium-1187/chrome-linux/chrome',
    args: ['--no-sandbox'],
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => route.request().method() === 'GET'
      ? route.continue() : route.abort());
    const results = [];
    for (const [book, chapter] of [['education', '003'], ['secret_adversary', '002']]) {
      const work = path.join(__dirname, '..', 'work', book);
      const expected = JSON.parse(fs.readFileSync(path.join(work, 'full_run_result.json'), 'utf8'));
      const alignment = JSON.parse(fs.readFileSync(path.join(work, 'alignments', `${chapter}.json`), 'utf8'));
      await page.goto(`https://forage-review.fly.dev/b/${book}?c=${chapter}`);
      await page.locator('.revision-label').waitFor();
      await page.locator('#p-0 .draft').waitFor();
      const label = await page.locator('.revision-label').textContent();
      if (!label.includes(expected.review_revision.slice(0, 12))) throw Error(`Wrong edition: ${book}`);
      if (await page.locator('.draft').count() !== alignment.draft_paragraphs.length) throw Error(`Missing paragraphs: ${book}`);
      if (book === 'secret_adversary') {
        await page.getByRole('heading', { name: 'Notes awaiting a matching passage' }).waitFor();
        if (await page.locator('.note-body').count() !== 7) throw Error('Missing preserved comments');
      }
      await page.screenshot({ path: path.join(__dirname, `${book}-live.png`) });
      results.push({ book, chapter, revision: expected.review_revision, visible_paragraphs: alignment.draft_paragraphs.length });
    }
    if (errors.length) throw Error(errors.join('\n'));
    fs.writeFileSync(path.join(__dirname, 'browser-verification.json'), JSON.stringify({ readonly: true, javascript_errors: errors, pages: results }, null, 2) + '\n');
    console.log('Browser verified both current editions, rendered paragraphs, all seven preserved earlier notes, and no JavaScript errors.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exit(1); });
