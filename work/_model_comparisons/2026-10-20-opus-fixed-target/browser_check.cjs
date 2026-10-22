const {chromium}=require('/mnt/data/playwright-cache/node/node_modules/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/home/tp/.cache/ms-playwright/chromium-1187/chrome-linux/chrome',args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('file://'+path.join(__dirname,'report.html'));
  const d=JSON.parse(await page.locator('#data').textContent());
  assert.equal(d.chapters.length,4);assert.equal(await page.locator('#results tr').count(),4);
  let selections=0,links=0;
  const flat=s=>s.trim().replace(/\s+/g,' ');
  for(const c of d.chapters){
   await page.selectOption('#chapter',c.key);
   assert((await page.locator('#chapterTitle').textContent()).includes(c.title));
   assert(c.texts.draft,'Missing draft '+c.key);
   for(const side of ['left','right'])for(const variant of Object.keys(c.texts)){
    await page.selectOption('#'+side,variant);
    const actual=flat((await page.locator('#'+side+'Text p').allTextContents()).join('\n\n'));
    assert.equal(actual,flat(fs.readFileSync(path.join(__dirname,c.key,variant+'.md'),'utf8')));
    selections++;
   }
   for(const href of await page.locator('a').evaluateAll(nodes=>nodes.map(x=>x.getAttribute('href')))){
    assert(fs.existsSync(path.resolve(__dirname,href)),href);links++;
   }
  }
  await page.selectOption('#chapter',d.chapters[0].key);
  await page.screenshot({path:path.join(__dirname,'report-preview.png')});
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.querySelectorAll('details').forEach(x=>x.open=true));
  const width=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
  assert(width.document<=width.viewport,JSON.stringify(width));assert.deepEqual(errors,[]);
  const result={status:'pass',chapters:4,reader_selections:selections,local_links_checked:links,mobile_width:width,javascript_errors:errors};
  fs.writeFileSync(path.join(__dirname,'browser_verification.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
