// Slow-network regression check: opening a DM from the org chart must never flash the default channel first (the DM request is delayed 1.5s).
// Needs a running server (BASE_URL) and Playwright browsers. Exit 1 if any title other than the person's name was ever shown.
// Slow network race: the FIRST channel-list request is slow, as on a slow PC. The DM must still win and the default channel must never flash.
const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
let n = 0; await p.route('**/world/chat/dm', async (route) => { await new Promise(r => setTimeout(r, 1500)); await route.continue(); });
await p.goto(process.env.BASE_URL || 'http://127.0.0.1:8888/'); await p.waitForSelector('.user-pick'); await p.click('.user-pick:has-text("이서연")'); await p.waitForSelector('.nav');
await p.click('.nav a[href="#/org"]'); await p.fill('#q', '박준영'); await p.waitForSelector('.picker-list li button'); await p.keyboard.press('Enter'); await p.waitForSelector('[data-guide=org-person]');
await p.click('a:has-text("메시지 보내기")');
const seen = new Set(); const t0 = Date.now();
while (Date.now() - t0 < 4500) { seen.add(await p.locator('.chatbox h2').innerText().catch(() => '(loading)')); await p.waitForTimeout(100); }
console.log('titles seen over time:', JSON.stringify([...seen]));
const final = await p.locator('.chatbox h2').innerText().catch(() => '(none)'); console.log('final title:', final);
await b.close(); process.exit(seen.size === 1 && /박준영/.test(final) ? 0 : 1); })();
