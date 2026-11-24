// End-to-end work flows as developer, CFO and a non-finance employee (todos, mail, chat, org, ghost, finance permission).
// Needs a running server (BASE_URL, default http://127.0.0.1:8888/) and Playwright browsers:  cd web && npm install && npx playwright install chromium
const { chromium } = require('playwright');
const B = (process.env.BASE_URL || 'http://127.0.0.1:8888/').replace(/\/?$/, '/'); const out = [];
// Poll instead of sleeping: a slow PC (or a busy model) must not turn a correct result into a failure. Every wait has a ceiling.
const until = (p, fn, arg, ms = 12000) => p.waitForFunction(fn, arg, { timeout: ms }).then(() => true).catch(() => false);
const has = (p, sel, re, ms = 12000) => until(p, ([q, r]) => new RegExp(r).test(document.querySelector(q)?.innerText || ''), [sel, re.source], ms);
// A briefing that does not appear must produce a readable failure (what the page said, how long we waited), not a stack trace.
const ready = async (p, who, ms = 60000) => {
  const t0 = Date.now();
  const ok = await p.waitForSelector('.todo', { timeout: ms }).then(() => true).catch(() => false);
  if (!ok) t(`${who}: briefing appears within ${ms / 1000}s`, false, 'page said: ' + (await p.locator('.main').innerText().catch(() => '(no page)')).replace(/\s+/g, ' ').slice(0, 220));
  return ok ? Date.now() - t0 : 0;
};
const t = (n, ok, ev = '') => { out.push([ok, n, ev]); console.log((ok ? 'PASS ' : 'FAIL ') + n + (ev ? '  — ' + ev : '')); };
const login = async (b, name) => { const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage(); p.errs = [];
  p.on('pageerror', e => p.errs.push(String(e).slice(0, 100))); await p.goto(B); await p.waitForSelector('.user-pick'); await p.click(`.user-pick:has-text("${name}")`); await p.waitForSelector('.nav'); return p; };
(async () => { const b = await chromium.launch();
  // ---- 1) developer: clock in, todo flows, mail, chat
  let p = await login(b, '이서연'); let t0 = Date.now();
  await p.click('[data-guide=clock-in]'); const ms1 = await ready(p, 'developer'); if (!ms1) return finish(b); t('clock-in -> briefing appears', true, `${Date.now() - t0}ms`);
  const n0 = await p.locator('.todo').count();
  const notice = p.locator('.todo:has-text("확인했어요") button:has-text("확인했어요")').first();
  if (await notice.count()) { await notice.click(); await p.waitForSelector('[data-guide=done]'); t('notice ack moves to 처리한 일', /확인 완료/.test(await p.locator('[data-guide=done]').innerText())); }
  const st = p.locator('button:has-text("작업 시작")').first();
  if (await st.count()) { await st.click(); await p.waitForSelector('button:has-text("해결 처리")'); await p.click('button:has-text("해결 처리")'); await p.fill('input[id^=n]', '원인 수정 후 배포'); await p.click('button:has-text("처리 완료")'); 
    t('issue start -> resolve with note', await has(p, '[data-guide=done]', /해결 처리/)); }
  // reply draft: propose -> edit -> send
  const draft = p.locator('button:has-text("답장 초안 만들기")').first();
  if (await draft.count()) { await draft.click(); await p.waitForSelector('[data-guide=draft-panel]'); t('AI reply draft proposed (not sent)', true);
    const ext = await p.locator('text=외부 수신자에게 발송됨을 확인').count();
    if (!ext) { await p.click('button:has-text("승인하고 보내기")'); t('approved draft is sent and todo closes with outcome', await has(p, '[data-guide=done]', /회신 발송/)); } else t('draft is external: needs confirm (skipped sending)', true); }
  t('open todos decreased', (await p.locator('.todo').count()) < n0, `${n0} -> ${await p.locator('.todo').count()}`);
  // mail compose + <=3 replies
  await p.click('.nav a[href="#/mail"]'); await p.click('[data-guide=mail-new]'); await p.fill('.picker input', '배'); await p.waitForSelector('.picker-list li button'); await p.keyboard.press('Enter');
  await p.fill('#m-sub', '릴리스 체크리스트 확인 부탁'); await p.fill('#m-body', '금요일 릴리스 전에 체크리스트 확인 부탁드립니다.'); await p.click('button:has-text("보내기")'); await p.waitForTimeout(500);
  await p.click('button[role=tab]:has-text("보낸편지함")'); t('sent mail appears in 보낸편지함', await has(p, '.list', /릴리스 체크리스트/));
  await p.click('button[role=tab]:has-text("받은편지함")');
  await until(p, () => [...document.querySelectorAll('.list button')].some((x) => x.innerText.includes('Re: 릴리스')), null, 30000); await p.waitForTimeout(4000);   // first reply, then a moment for any others (the cap is checked below)
  const replies = await p.locator('.list button:has-text("Re: 릴리스")').count(); t('mail reply arrives (<=3)', replies >= 1 && replies <= 3, `${replies} reply`);
  // chat
  await p.click('.nav a[href="#/chat"]'); await p.waitForSelector('#chat-in'); await p.fill('#chat-in', '이번 배포 일정 공유 부탁드려요'); await p.keyboard.press('Enter'); await p.waitForSelector('.msg.mine'); const m0 = await p.locator('.msg').count();
  await until(p, (n) => document.querySelectorAll('.msg').length > n, m0, 30000); await p.waitForTimeout(5000);   // first reply, then a moment for any others
  const got = (await p.locator('.msg').count()) - m0; t('chat replies in character, 1..3', got >= 1 && got <= 3, `${got} replies`);
  // org -> DM
  await p.click('.nav a[href="#/org"]'); await p.fill('#q', '박준영'); await p.waitForSelector('.picker-list li button'); await p.keyboard.press('Enter'); await p.waitForSelector('[data-guide=org-person]');
  t('org search -> person card with reporting line', /대표이사|최민재/.test(await p.locator('.crumbs').innerText()));
  await p.click('a:has-text("메시지 보내기")');
  // the conversation title must BECOME the person's name (polled, not read once: slower machines render the page before the channel list arrives)
  const dmOk = await p.waitForFunction(() => /박준영/.test(document.querySelector('.chatbox h2')?.textContent || ''), null, { timeout: 10000 }).then(() => true).catch(() => false);
  t('DM opens from org card', dmOk, dmOk ? '' : 'title was: ' + (await p.locator('.chatbox h2').innerText().catch(() => '(none)')));
  // guide ghost
  await p.click('.nav a[href="#/home"]'); await p.waitForTimeout(800); await p.locator('.gbody').click({ force: true }); await p.waitForSelector('.gchat');
  await p.fill('.gchat input, .gchat textarea', '택시비 한도가 얼마예요?'); await p.keyboard.press('Enter');
  t('ghost answers a policy question from the wiki', await has(p, '.gchat', /3만원/, 15000), '');
  t('no page errors (developer)', p.errs.length === 0, p.errs.join(';'));
  // ---- 2) CFO: signals + finance + admin
  p = await login(b, '정유라'); t0 = Date.now(); await p.click('[data-guide=clock-in]'); if (!(await ready(p, 'CFO'))) return finish(b); t('CFO clock-in -> briefing appears', true, `${Date.now() - t0}ms`);
  const titles = await p.locator('.todo .title').allTextContents();
  t('CFO sees [재무]/[예산]/[실적] signals as todos', ['[재무]', '[예산]', '[실적]'].every(k => titles.some(x => x.startsWith(k))), titles.filter(x => x.startsWith('[')).length + ' signals');
  const sig = p.locator('.todo:has-text("[예산]") button:has-text("확인했어요")').first(); await sig.click();
  t('acknowledging a signal records it', await has(p, '[data-guide=done]', /확인 완료/));
  await p.click('.nav a[href="#/company"]'); await p.click('button[role=tab]:has-text("재무·실적")'); await p.waitForSelector('.pl'); t('finance tab visible to CFO', true);
  await p.click('.nav a[href="#/admin"]'); await p.waitForSelector('.seg'); t('admin: stage buttons present', (await p.locator('.seg button').count()) >= 10);
  t('no page errors (CFO)', p.errs.length === 0, p.errs.join(';'));
  // ---- 3) developer cannot see finance
  p = await login(b, '김민수'); await p.click('.nav a[href="#/company"]'); await p.click('button[role=tab]:has-text("재무·실적")');
  t('non-finance user sees a permission note, no numbers', (await has(p, '.main', /권한이 없어요/)) && !(await p.locator('.pl').count()));
  return finish(b); })();
async function finish(b) { const bad = out.filter(o => !o[0]); console.log(`\n${out.length - bad.length}/${out.length} flow checks passed`); await b.close(); process.exit(bad.length ? 1 : 0); }
