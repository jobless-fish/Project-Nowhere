// Accessibility checks of the ghost guide: reduced motion, keyboard-only use, hide/summon persistence, mobile layout.
// Needs a fresh database:  PORT=8000 uvicorn server:combined &  then  node web/e2e/ghost-a11y.cjs
const { chromium } = require('playwright');
const B = process.env.BASE_URL || 'http://127.0.0.1:8000/';
(async () => {
  const b = await chromium.launch(); const issues = [];
  const login = async (page, name) => { await page.goto(B); await page.waitForSelector('.user-pick'); await page.click(`.user-pick:has-text("${name}")`); await page.waitForSelector('.nav'); };
  const watch = (page, tag) => { page.on('pageerror', e => issues.push(tag + ' pageerror ' + String(e).slice(0, 140))); page.on('console', m => m.type() === 'error' && !m.text().includes('404') && issues.push(tag + ' console ' + m.text().slice(0, 140))); };
  // 1) reduced motion: no flight, no drift, ring still shows, content still readable
  const ctxR = await b.newContext({ viewport: { width: 1280, height: 860 }, reducedMotion: 'reduce' }); const r = await ctxR.newPage(); watch(r, 'reduced');
  await login(r, '이서연'); await r.waitForSelector('.gbody'); await r.waitForTimeout(800);
  await r.click('[data-guide=clock-in]'); await r.waitForSelector('text=오늘 브리핑을 같이 훑어볼까요?', { timeout: 20000 }); await r.click('text=둘러보기'); await r.waitForTimeout(500);
  const samples = []; for (let i = 0; i < 6; i++) { samples.push(await r.evaluate(() => { const q = document.querySelector('.gbody').getBoundingClientRect(); return [Math.round(q.x), Math.round(q.y)]; })); await r.waitForTimeout(150); }
  console.log('reduced motion: ghost positions over 0.9s (should be constant):', JSON.stringify(samples.map(String).filter((v, i, a) => a.indexOf(v) === i)));
  console.log('reduced motion: ring visible:', await r.locator('.gring').count() === 1, '| ring animation:', await r.evaluate(() => getComputedStyle(document.querySelector('.gring')).animationName));
  // 2) keyboard: tab to the ghost, open chat with Enter, Escape closes, focus returns usable
  await r.keyboard.press('Escape'); await r.focus('.gbody'); await r.keyboard.press('Enter'); await r.waitForSelector('.gchat'); console.log('keyboard: chat opened with Enter, input focused:', await r.evaluate(() => document.activeElement && document.activeElement.getAttribute('aria-label')));
  await r.keyboard.type('보안 이상한 메일 있어요?'); await r.keyboard.press('Enter'); await r.waitForSelector('.gmsg.bot >> nth=1', { timeout: 8000 }); await r.waitForTimeout(1600);
  console.log('keyboard: answered ->', (await r.locator('.gmsg.bot').nth(1).textContent()).slice(0, 60), '| ring target present:', await r.locator('.gring').count());
  await r.keyboard.press('Escape'); console.log('Escape closes chat:', await r.locator('.gchat').count() === 0);
  // 3) hide and summon back
  await r.keyboard.press('Enter').catch(() => {}); await r.locator('.gbody').click({ force: true }); await r.waitForSelector('.gchat'); await r.click('button:has-text("숨기기")'); await r.waitForSelector('.gsummon');
  console.log('hidden: ghost gone:', await r.locator('.gbody').count() === 0, '| summon button:', await r.locator('.gsummon').count());
  await r.reload(); await r.waitForSelector('.nav'); await r.waitForTimeout(600); console.log('hidden persists after reload:', await r.locator('.gsummon').count() === 1);
  await r.click('.gsummon'); await r.waitForSelector('.gbody canvas'); console.log('summoned back with WebGL canvas:', await r.locator('.gbody canvas').count());
  // 4) mobile with chat open
  const m = await b.newPage({ viewport: { width: 390, height: 844 } }); watch(m, 'mobile'); await login(m, '김민수'); await m.waitForSelector('.gbody canvas'); await m.waitForTimeout(2500);
  await m.locator('.gbody').click({ force: true }); await m.waitForSelector('.gchat'); await m.waitForTimeout(1800); await m.screenshot({ path: '/tmp/g6_mobile_chat.png' });
  console.log('mobile overflow:', await m.evaluate(() => document.documentElement.scrollWidth > innerWidth));
  const box = await m.evaluate(() => { const c = document.querySelector('.gchat').getBoundingClientRect(), g = document.querySelector('.gbody').getBoundingClientRect(); return { chat: [Math.round(c.top), Math.round(c.bottom)], ghost: [Math.round(g.top), Math.round(g.bottom)], vh: innerHeight }; });
  console.log('mobile layout:', JSON.stringify(box));
  console.log('issues:', JSON.stringify(issues)); await b.close();
})();
