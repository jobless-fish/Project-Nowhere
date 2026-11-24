// Browser check of the ghost guide: renders in WebGL, flies a CURVED path, rings the exact target, tours, and navigates from chat.
// Needs a fresh database (the demo user must not have clocked in yet):  PORT=8000 uvicorn server:combined &  then  node web/e2e/ghost-flight.cjs
const { chromium } = require('playwright');
const B = process.env.BASE_URL || 'http://127.0.0.1:8000/';
(async () => {
  const b = await chromium.launch(); const issues = [];
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  p.on('pageerror', e => issues.push('pageerror ' + String(e).slice(0, 160))); p.on('console', m => m.type() === 'error' && !m.text().includes('404') && issues.push('console ' + m.text().slice(0, 160)));
  await p.goto(B); await p.waitForSelector('.user-pick'); await p.click('.user-pick:has-text("김민수")'); await p.waitForSelector('.nav');
  await p.waitForSelector('.gbody canvas', { timeout: 20000 }); await p.waitForTimeout(3500);
  await p.screenshot({ path: '/tmp/g1_idle.png' });
  const rect = async () => p.evaluate(() => { const r = document.querySelector('.gbody').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; });
  console.log('idle position:', (await rect()).map(Math.round));
  await p.click('[data-guide=clock-in]'); await p.waitForSelector('text=오늘 브리핑을 같이 훑어볼까요?', { timeout: 20000 }); await p.screenshot({ path: '/tmp/g2_offer.png' });
  // flight path: sample while it travels to the first step
  await p.click('text=둘러보기');
  const pts = []; const t0 = Date.now();
  while (Date.now() - t0 < 2400) { pts.push(await rect()); await p.waitForTimeout(40); }
  const a = pts[0], z = pts[pts.length - 1]; const dx = z[0] - a[0], dy = z[1] - a[1], L = Math.hypot(dx, dy) || 1;
  const dev = Math.max(...pts.map(([x, y]) => Math.abs((x - a[0]) * dy - (y - a[1]) * dx) / L));
  const still = await rect(); await p.waitForTimeout(600); const still2 = await rect(); console.log('after landing, body drift px over 0.6s:', Math.round(Math.hypot(still2[0]-still[0], still2[1]-still[1])), '| anchor still:', await p.evaluate(() => { const a = document.querySelector('.ghost').getBoundingClientRect(); return [Math.round(a.x), Math.round(a.y)]; }));
  console.log('flight: start', a.map(Math.round), 'end', z.map(Math.round), '| path length', Math.round(L), '| max sideways deviation px:', Math.round(dev));
  const ringOk = async () => p.evaluate(() => { const ring = document.querySelector('.gring'); if (!ring) return 'no ring'; const id = document.querySelector('.gring') && window.__t; return null; });
  await p.waitForTimeout(800); await p.screenshot({ path: '/tmp/g3_step1.png' });
  // ring alignment with the real target
  const align = await p.evaluate(() => { const ring = document.querySelector('.gring').getBoundingClientRect(); const cands = [...document.querySelectorAll('[data-guide]')].map(e => ({ id: e.dataset.guide, r: e.getBoundingClientRect() })).filter(c => c.r.width > 0);
    const best = cands.map(c => ({ id: c.id, d: Math.abs(ring.x + 6 - c.r.x) + Math.abs(ring.y + 6 - c.r.y) + Math.abs(ring.width - 12 - c.r.width) + Math.abs(ring.height - 12 - c.r.height) })).sort((a, b) => a.d - b.d)[0]; return best; });
  console.log('ring matches target:', JSON.stringify(align));
  for (let i = 0; i < 6; i++) { const nxt = p.locator('.gbubble button:has-text("다음")'); if (!(await nxt.count())) break; await nxt.click(); await p.waitForTimeout(1500); if (i === 1) await p.screenshot({ path: '/tmp/g4_step3.png' }); }
  console.log('last bubble:', (await p.locator('.gbubble p').textContent()));
  // chat: ask where the org chart is
  await p.locator('.gbubble button:has-text("알겠어요"), .gbubble button:has-text("그만")').first().click().catch(() => {});
  await p.locator('.gbody').click({ force: true }); await p.waitForSelector('.gchat'); await p.fill('.gform input', '조직도는 어디서 봐요?'); await p.click('.gform button:has-text("보내기")');
  await p.waitForSelector('.gring', { timeout: 8000 }); await p.waitForTimeout(2200);
  console.log('route after chat:', await p.evaluate(() => location.hash)); await p.screenshot({ path: '/tmp/g5_chat.png' });
  console.log('issues:', JSON.stringify(issues));
  await b.close();
})();
