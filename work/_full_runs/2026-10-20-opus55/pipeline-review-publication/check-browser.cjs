const { chromium } = require('/mnt/data/playwright-cache/node/node_modules/playwright');
const fs = require('fs');
const root = __dirname;
(async () => {
  const browser = await chromium.launch({ headless: true,
    executablePath: '/home/tp/.cache/ms-playwright/chromium-1187/chrome-linux/chrome', args: ['--no-sandbox'] });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
    const live = process.argv.includes('--live');
    const base = live ? 'https://forage-review.fly.dev' : 'http://127.0.0.1:8773';
    if (live) {
      await context.addCookies(JSON.parse(fs.readFileSync(process.argv[3], 'utf8')));
      await context.route('**/*', route => route.request().method() === 'GET' ? route.continue() : route.abort());
    } else {
      const response = await context.request.post(base + '/api/session', { data: {token:'pipeline-preview-review', label:'Preview tester'} });
      if (!response.ok()) throw Error('Sign-in failed');
    }
    const page = await context.newPage();
    async function expand(card) {
      if (!await card.evaluate(node => node.open)) await card.locator('summary').first().click();
    }
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(base + '/b/secret_adversary?c=003');
    await page.getByRole('heading', {name:'Pipeline review', exact:true}).waitFor();
    await page.getByText(/started separately outside this website/).first().waitFor();
    const finding = page.locator('.pipeline-card').filter({hasText:"Improvised-name sentence cut"}).first();
    await finding.getByRole('button', {name:'Dismiss finding', exact:true}).waitFor();
    const findingId = await finding.getAttribute('data-review-id');
    await finding.getByText('Source and draft evidence', {exact:true}).click();
    if (!await finding.locator('blockquote').count()) throw Error('Evidence missing');
    await finding.getByRole('button', {name:'Request change with comment', exact:true}).click();
    await page.getByRole('textbox', {name:'What should change?'}).waitFor();
    await page.getByText(/Saving queues your feedback/).waitFor();
    if (!live) {
      await page.getByRole('button', {name:'Save revision request', exact:true}).click();
      await page.getByText('Describe what should change.', {exact:true}).waitFor();
    }
    await page.getByRole('button', {name:'Cancel', exact:true}).click();
    if (!live) {
      await finding.getByRole('button', {name:'Dismiss finding', exact:true}).click();
      await finding.locator('.revision-state.accepted').waitFor({state:'attached'});
      await page.reload();
      await expand(finding);
      await finding.getByRole('button', {name:'Reopen finding', exact:true}).click();
      await finding.getByRole('button', {name:'Request change with comment', exact:true}).click();
      await page.getByRole('textbox', {name:'What should change?'}).fill('Restore the improvised-name setup in the next pipeline run.');
      await page.getByRole('button', {name:'Save revision request', exact:true}).click();
      await finding.locator('.revision-state.rejected').waitFor();
      await page.reload();
      await finding.locator('.revision-state.rejected').waitFor();
      if (await finding.locator('.revision-event').count() !== 3) throw Error('Missing finding history');
    }
    const repair = page.locator('.pipeline-card').filter({hasText:'Review chapter repairs'}).first();
    await expand(repair);
    await repair.getByRole('button', {name:'Accept revision', exact:true}).waitFor();
    await repair.locator('.pipeline-pass > summary').first().click();
    if (!await repair.locator('.pipeline-patch').count()) throw Error('Missing before/after history');
    if (!live) {
      await repair.getByRole('button', {name:'Accept revision', exact:true}).click();
      await repair.locator('.revision-state.accepted').waitFor({state:'attached'});
      await expand(repair);
      await repair.getByRole('button', {name:'Reopen revision', exact:true}).click();
      await repair.locator('.revision-state.reopened').waitFor({state:'attached'});
      await expand(repair);
      await repair.getByRole('button', {name:'Reject with comment', exact:true}).click();
      await page.getByRole('textbox', {name:'What should change?'}).fill('Review the first patch again.');
      await page.getByRole('button', {name:'Save revision request', exact:true}).click();
      await repair.locator('.revision-state.rejected').waitFor({state:'attached'});
      const feed = await (await context.request.get(base + '/api/books/secret_adversary/feedback')).json();
      const requested = feed.comments.filter(n => n.revision_review?.state === 'rejected');
      if (requested.length !== 2 || !requested.some(n=>n.id === findingId)) throw Error('Requests not exported');
      fs.writeFileSync(root+'/preview-feedback.json', JSON.stringify(feed));
    }
    await page.screenshot({path:root + (live ? '/live-christie.png' : '/preview-christie.png')});
    await page.goto(base + '/b/secret_adversary?c=004');
    await page.locator('.pipeline-card[open]').first().waitFor();
    if (!await page.getByRole('button', {name:'Request change with comment',exact:true}).count()) throw Error('Second must-fix missing');
    await page.goto(base + '/b/education?c=003');
    await page.getByRole('heading', {name:'Pipeline review',exact:true}).waitFor();
    const adams = page.locator('.pipeline-card').filter({hasText:'Review chapter repairs'}).first();
    await expand(adams);
    await adams.getByRole('button', {name:'Accept revision',exact:true}).waitFor();
    await page.screenshot({path:root + (live ? '/live-adams.png' : '/preview-adams.png')});
    if (errors.length) throw Error(errors.join('\n'));
    console.log(live ? 'Live browser verified finding controls, both must-fix cards, repair evidence and external-rerun messaging. No reviewer decisions submitted.' : 'Preview browser verified dismiss, reopen, request, acceptance, rejection, persistence, history, feedback export and no JavaScript errors.');
  } finally { await browser.close(); }
})().catch(e => {console.error(e); process.exit(1);});
