const { chromium } = require('playwright');
const B = process.env.BASE_URL || 'http://127.0.0.1:8888/', SHOT = process.env.SHOT || '/tmp';
(async () => {
  const b = await chromium.launch(); const issues = [];
  const page = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  page.on('pageerror', e => issues.push('pageerror ' + String(e).slice(0, 150)));
  page.on('console', m => m.type() === 'error' && !m.text().includes('404') && issues.push('console ' + m.text().slice(0, 150)));
  await page.goto(B); await page.waitForSelector('.user-pick'); await page.click('.user-pick:has-text("이서연")'); await page.waitForSelector('.nav');
  await page.click('.nav a[href="#/company"]'); await page.waitForSelector('.timeline'); await page.screenshot({ path: SHOT + '/c1_home.png', fullPage: true });
  await page.click('button[role=tab]:has-text("고객·거래처")'); await page.waitForSelector('.list button'); await page.click('.list button >> nth=0'); await page.waitForSelector('.facts');
  console.log('customer card:', (await page.locator('.facts').innerText()).replace(/\s+/g, ' ').slice(0, 120));
  await page.click('button[role=tab]:has-text("위키")'); await page.fill('#wq', '택시'); await page.waitForTimeout(500); console.log('wiki hits:', await page.locator('.list button').count());
  await page.click('button[role=tab]:has-text("용어집")'); console.log('terms:', await page.locator('.gloss > div').count());
  await page.click('button[role=tab]:has-text("달력")'); console.log('calendar rows:', await page.locator('.card .row .grow').count());
  // dark
  await page.click('.theme-toggle'); await page.waitForTimeout(300); await page.click('button[role=tab]:has-text("고객·거래처")'); await page.waitForSelector('.list button'); await page.click('.list button >> nth=1');
  console.log('theme:', await page.evaluate(() => document.documentElement.dataset.theme)); await page.screenshot({ path: SHOT + '/c2_dark_parties.png' });
  await page.click('.nav a[href="#/home"]'); await page.waitForTimeout(800); await page.screenshot({ path: SHOT + '/c3_dark_home.png' });
  await page.click('.nav a[href="#/chat"]'); await page.waitForTimeout(800); await page.screenshot({ path: SHOT + '/c4_dark_chat.png' });
  const m = await b.newPage({ viewport: { width: 390, height: 844 } }); await m.goto(B); await m.waitForSelector('.user-pick'); await m.click('.user-pick:has-text("이서연")'); await m.waitForSelector('.nav'); await m.goto(B + '#/company'); await m.waitForTimeout(900);
  console.log('mobile overflow:', await m.evaluate(() => document.documentElement.scrollWidth > innerWidth));
  console.log('issues:', JSON.stringify(issues)); await b.close();
})();
