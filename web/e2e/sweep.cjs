// Every demo account x every page (light, plus dark for three): page errors, console errors, horizontal overflow, empty pages.
// Needs a running server (BASE_URL, default http://127.0.0.1:8888/) and Playwright browsers:  cd web && npm install && npx playwright install chromium
const { chromium } = require('playwright');
const B = (process.env.BASE_URL || 'http://127.0.0.1:8888/').replace(/\/?$/, '/');
(async () => {
  const b = await chromium.launch();
  const ctx0 = await b.newContext(); const pg0 = await ctx0.newPage(); await pg0.goto(B); await pg0.waitForSelector('.user-pick');
  const names = (await pg0.locator('.user-pick b, .user-pick .name').allTextContents()).map(s => s.trim()).filter(Boolean);
  const users = names.length ? names : await pg0.locator('.user-pick').allInnerTexts();
  console.log('accounts on login screen:', users.length);
  const ROUTES = ['home','news','mail','chat','org','company','admin'];
  const res = [];
  for (const [i, u] of users.entries()) {
    const nm = u.split(/\s|\n/)[0];
    for (const theme of ['light','dark']) {
      if (theme === 'dark' && i > 2) continue;              // dark on the first 3 accounts is enough
      const c = await b.newContext({ viewport: { width: 1280, height: 860 } }); const p = await c.newPage();
      const errs = [], http = [];
      p.on('pageerror', e => errs.push(String(e).slice(0, 100)));
      p.on('console', m => m.type() === 'error' && !m.text().includes('Failed to load resource') && errs.push(m.text().slice(0, 100)));
      p.on('response', r => { if (r.status() >= 400) http.push(r.status() + ' ' + r.url().replace(B, '/').split('?')[0]); });
      await p.goto(B); await p.waitForSelector('.user-pick'); await p.locator('.user-pick').nth(i).click(); await p.waitForSelector('.nav');
      if (theme === 'dark') await p.click('.theme-toggle');
      const row = { user: nm, theme, pages: {} };
      for (const r of ROUTES) {
        await p.goto(B + '#/' + r);
        // wait for the page to finish loading (a loading page shows only its title, e.g. 1 character), then give it a moment to settle
        await p.waitForFunction(() => (document.querySelector('.main')?.innerText || '').trim().length > 40, null, { timeout: 20000 }).catch(() => {});
        await p.waitForTimeout(300);
        const txt = (await p.locator('.main').innerText()).replace(/\s+/g, ' ');
        const over = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
        row.pages[r] = { len: txt.length, over, empty: txt.length < 40 };
      }
      row.errs = errs; row.http = [...new Set(http)];
      res.push(row); await c.close();
    }
  }
  const bad = res.filter(r => r.errs.length || Object.values(r.pages).some(p => p.over || p.empty));
  console.log('runs:', res.length, '| runs with problems:', bad.length);
  for (const r of bad) console.log(' !', r.user, r.theme, JSON.stringify(r.errs), JSON.stringify(Object.fromEntries(Object.entries(r.pages).filter(([, p]) => p.over || p.empty))));
  const http = {}; for (const r of res) for (const h of r.http) http[h] = (http[h] || 0) + 1;
  console.log('HTTP >=400 seen (count of runs):', JSON.stringify(http));
  await b.close();
  process.exit(bad.length ? 1 : 0);
})();
