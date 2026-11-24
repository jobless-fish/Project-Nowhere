// End-to-end work flows as developer, CFO and a non-finance employee (todos, mail, chat, org, ghost, finance permission).
// Needs a running server (BASE_URL, default http://127.0.0.1:8888/) and Playwright browsers:  cd web && npm install && npx playwright install chromium
const { chromium } = require('playwright');
const B = (process.env.BASE_URL || 'http://127.0.0.1:8888/').replace(/\/?$/, '/'); const out = [];
const t = (n, ok, ev = '') => { out.push([ok, n, ev]); console.log((ok ? 'PASS ' : 'FAIL ') + n + (ev ? '  — ' + ev : '')); };
const login = async (b, name) => { const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage(); p.errs = [];
  p.on('pageerror', e => p.errs.push(String(e).slice(0, 100))); await p.goto(B); await p.waitForSelector('.user-pick'); await p.click(`.user-pick:has-text("${name}")`); await p.waitForSelector('.nav'); return p; };
(async () => { const b = await chromium.launch();
  // ---- 1) developer: clock in, todo flows, mail, chat
  let p = await login(b, '이서연'); let t0 = Date.now();
  await p.click('[data-guide=clock-in]'); await p.waitForSelector('.todo', { timeout: 25000 }); t('clock-in -> briefing appears', true, `${Date.now() - t0}ms`);
  const n0 = await p.locator('.todo').count();
  const notice = p.locator('.todo:has-text("확인했어요") button:has-text("확인했어요")').first();
  if (await notice.count()) { await notice.click(); await p.waitForSelector('[data-guide=done]'); t('notice ack moves to 처리한 일', /확인 완료/.test(await p.locator('[data-guide=done]').innerText())); }
  const st = p.locator('button:has-text("작업 시작")').first();
  if (await st.count()) { await st.click(); await p.waitForSelector('button:has-text("해결 처리")'); await p.click('button:has-text("해결 처리")'); await p.fill('input[id^=n]', '원인 수정 후 배포'); await p.click('button:has-text("처리 완료")'); await p.waitForTimeout(900);
    t('issue start -> resolve with note', /해결 처리/.test(await p.locator('[data-guide=done]').innerText())); }
  // reply draft: propose -> edit -> send
  const draft = p.locator('button:has-text("답장 초안 만들기")').first();
  if (await draft.count()) { await draft.click(); await p.waitForSelector('[data-guide=draft-panel]'); t('AI reply draft proposed (not sent)', true);
    const ext = await p.locator('text=외부 수신자에게 발송됨을 확인').count();
    if (!ext) { await p.click('button:has-text("승인하고 보내기")'); await p.waitForTimeout(1200); t('approved draft is sent and todo closes with outcome', /회신 발송/.test(await p.locator('[data-guide=done]').innerText().catch(() => ''))); } else t('draft is external: needs confirm (skipped sending)', true); }
  t('open todos decreased', (await p.locator('.todo').count()) < n0, `${n0} -> ${await p.locator('.todo').count()}`);
  // mail compose + <=3 replies
  await p.click('.nav a[href="#/mail"]'); await p.click('[data-guide=mail-new]'); await p.fill('.picker input', '배'); await p.waitForSelector('.picker-list li button'); await p.keyboard.press('Enter');
  await p.fill('#m-sub', '릴리스 체크리스트 확인 부탁'); await p.fill('#m-body', '금요일 릴리스 전에 체크리스트 확인 부탁드립니다.'); await p.click('button:has-text("보내기")'); await p.waitForTimeout(500);
  await p.click('button[role=tab]:has-text("보낸편지함")'); t('sent mail appears in 보낸편지함', /릴리스 체크리스트/.test(await p.locator('.list').innerText()));
  await p.waitForTimeout(9000); await p.click('button[role=tab]:has-text("받은편지함")'); await p.waitForTimeout(500);
  const replies = await p.locator('.list button:has-text("Re: 릴리스")').count(); t('mail reply arrives (<=3)', replies >= 1 && replies <= 3, `${replies} reply`);
  // chat
  await p.click('.nav a[href="#/chat"]'); await p.waitForSelector('#chat-in'); await p.fill('#chat-in', '이번 배포 일정 공유 부탁드려요'); await p.keyboard.press('Enter'); await p.waitForSelector('.msg.mine'); const m0 = await p.locator('.msg').count(); await p.waitForTimeout(10000);
  const got = (await p.locator('.msg').count()) - m0; t('chat replies in character, 1..3', got >= 1 && got <= 3, `${got} replies`);
  // org -> DM
  await p.click('.nav a[href="#/org"]'); await p.fill('#q', '박준영'); await p.waitForSelector('.picker-list li button'); await p.keyboard.press('Enter'); await p.waitForSelector('[data-guide=org-person]');
  t('org search -> person card with reporting line', /대표이사|최민재/.test(await p.locator('.crumbs').innerText()));
  await p.click('a:has-text("메시지 보내기")'); await p.waitForSelector('#chat-in'); t('DM opens from org card', /박준영/.test(await p.locator('.chatbox h2').innerText()));
  // guide ghost
  await p.click('.nav a[href="#/home"]'); await p.waitForTimeout(800); await p.locator('.gbody').click({ force: true }); await p.waitForSelector('.gchat');
  await p.fill('.gchat input, .gchat textarea', '택시비 한도가 얼마예요?'); await p.keyboard.press('Enter'); await p.waitForTimeout(2500);
  t('ghost answers a policy question from the wiki', /3만원/.test(await p.locator('.gchat').innerText()), '');
  t('no page errors (developer)', p.errs.length === 0, p.errs.join(';'));
  // ---- 2) CFO: signals + finance + admin
  p = await login(b, '정유라'); await p.click('[data-guide=clock-in]'); await p.waitForSelector('.todo', { timeout: 25000 });
  const titles = await p.locator('.todo .title').allTextContents();
  t('CFO sees [재무]/[예산]/[실적] signals as todos', ['[재무]', '[예산]', '[실적]'].every(k => titles.some(x => x.startsWith(k))), titles.filter(x => x.startsWith('[')).length + ' signals');
  const sig = p.locator('.todo:has-text("[예산]") button:has-text("확인했어요")').first(); await sig.click(); await p.waitForTimeout(900);
  t('acknowledging a signal records it', /확인 완료/.test(await p.locator('[data-guide=done]').innerText()));
  await p.click('.nav a[href="#/company"]'); await p.click('button[role=tab]:has-text("재무·실적")'); await p.waitForSelector('.pl'); t('finance tab visible to CFO', true);
  await p.click('.nav a[href="#/admin"]'); await p.waitForSelector('.seg'); t('admin: stage buttons present', (await p.locator('.seg button').count()) >= 10);
  t('no page errors (CFO)', p.errs.length === 0, p.errs.join(';'));
  // ---- 3) developer cannot see finance
  p = await login(b, '김민수'); await p.click('.nav a[href="#/company"]'); await p.click('button[role=tab]:has-text("재무·실적")'); await p.waitForTimeout(1000);
  t('non-finance user sees a permission note, no numbers', /권한이 없어요/.test(await p.locator('.main').innerText()) && !(await p.locator('.pl').count()));
  const bad = out.filter(o => !o[0]); console.log(`\n${out.length - bad.length}/${out.length} flow checks passed`); await b.close(); process.exit(bad.length ? 1 : 0); })();
