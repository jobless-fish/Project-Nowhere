// Real-browser check of the live work flow: todo actions, mail compose + replies (<=3), chat + typing, org chart UX.
const { chromium } = require('playwright');
const B = process.env.BASE_URL || 'http://127.0.0.1:8888/';
const SHOT = process.env.SHOT || '/tmp';
(async () => {
  const b = await chromium.launch(); const issues = [];
  const page = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  page.on('pageerror', e => issues.push('pageerror ' + String(e).slice(0, 160)));
  page.on('console', m => m.type() === 'error' && !m.text().includes('404') && issues.push('console ' + m.text().slice(0, 160)));
  await page.goto(B); await page.waitForSelector('.user-pick'); await page.click('.user-pick:has-text("이서연")'); await page.waitForSelector('.nav');
  // --- todos
  await page.click('[data-guide=clock-in]'); await page.waitForSelector('.todo', { timeout: 20000 });
  const before = await page.locator('.todo').count();
  console.log('todos:', before, '| checkbox present:', await page.locator('[role=checkbox]').count());
  const kinds = await page.locator('.todo .badge:not(.urgent)').allTextContents(); console.log('kinds shown:', kinds.slice(0, 6).join(','));
  await page.screenshot({ path: SHOT + '/f1_home.png' });
  const notice = page.locator('.todo:has-text("확인했어요") button:has-text("확인했어요")').first();
  if (await notice.count()) { await notice.click(); await page.waitForSelector('text=처리한 일'); console.log('notice acked -> 처리한 일 section:', await page.locator('[data-guide=done]').innerText().then(t => t.replace(/\s+/g, ' ').slice(0, 120))); }
  const start = page.locator('button:has-text("작업 시작")').first();
  if (await start.count()) { await start.click(); await page.waitForSelector('button:has-text("해결 처리")'); console.log('issue started: 진행 중 badge', await page.locator('.badge:has-text("진행 중")').count());
    await page.click('button:has-text("해결 처리")'); await page.fill('input[id^=n]', '원인 수정 후 배포했어요'); await page.click('button:has-text("처리 완료")'); await page.waitForTimeout(800);
    console.log('issue resolved outcome:', await page.locator('[data-guide=done]').innerText().then(t => /해결 처리/.test(t))); }
  const noreply = page.locator('button:has-text("답장 없이 처리")').first();
  if (await noreply.count()) { await noreply.click(); await page.fill('input[id^=n]', '참고용 안내라 회신 불필요'); await page.keyboard.press('Enter'); await page.waitForTimeout(800); console.log('mail closed without reply ->', await page.locator('[data-guide=done]').innerText().then(t => /답장 없이 처리/.test(t))); }
  console.log('open todos now:', await page.locator('.todo').count(), '(was', before + ')');
  await page.screenshot({ path: SHOT + '/f2_home_done.png', fullPage: true });
  // --- mail compose
  await page.click('.nav a[href="#/mail"]'); await page.waitForSelector('[data-guide=mail-new]'); await page.click('[data-guide=mail-new]');
  await page.fill('.picker input', '박'); await page.waitForSelector('.picker-list li button'); await page.keyboard.press('Enter');
  await page.fill('#m-sub', '배포 일정 확인 부탁드려요'); await page.fill('#m-body', '이번 주 배포 일정 공유 부탁드립니다. 금요일 오전까지 가능할까요?');
  await page.screenshot({ path: SHOT + '/f3_compose.png' });
  await page.click('button:has-text("보내기")'); await page.waitForSelector('.toast');
  console.log('mail sent toast:', await page.locator('.toast').first().innerText());
  await page.click('button[role=tab]:has-text("보낸편지함")'); await page.waitForTimeout(500);
  console.log('sent folder first:', (await page.locator('.list button').first().innerText()).replace(/\s+/g, ' '));
  await page.click('button[role=tab]:has-text("받은편지함")'); await page.waitForTimeout(6000);
  console.log('inbox badge/nav count:', await page.locator('.nav a[href="#/mail"] .count').textContent().catch(() => 'none'));
  await page.screenshot({ path: SHOT + '/f4_mail.png' });
  // --- chat
  await page.click('.nav a[href="#/chat"]'); await page.waitForSelector('#chat-in'); await page.fill('#chat-in', '이번 주 배포 일정 공유 부탁드려요'); await page.keyboard.press('Enter');
  await page.waitForSelector('.msg.mine'); const t0 = await page.locator('.msg').count(); await page.waitForTimeout(9000);
  const t1 = await page.locator('.msg').count(); console.log('chat replies arrived:', t1 - t0 - 0, '(<=3 expected, own msg counted before)');
  await page.screenshot({ path: SHOT + '/f5_chat.png' });
  // --- org
  await page.click('.nav a[href="#/org"]'); await page.waitForSelector('.orghead'); await page.screenshot({ path: SHOT + '/f6_org.png' });
  await page.fill('#q', '백엔드'); await page.waitForSelector('.picker-list li button'); await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
  await page.waitForSelector('[data-guide=org-person]'); console.log('org person card crumbs:', (await page.locator('.crumbs').innerText()).replace(/\s+/g, ' '));
  await page.screenshot({ path: SHOT + '/f7_org_person.png' });
  await page.click('a:has-text("메시지 보내기")'); await page.waitForSelector('#chat-in'); console.log('DM opened from org:', await page.locator('.chatbox h2').innerText());
  // mobile
  const m = await b.newPage({ viewport: { width: 390, height: 844 } }); await m.goto(B); await m.waitForSelector('.user-pick'); await m.click('.user-pick:has-text("이서연")'); await m.waitForSelector('.nav');
  for (const r of ['mail', 'chat', 'org']) { await m.goto(B + '#/' + r); await m.waitForTimeout(900); console.log('mobile', r, 'overflow:', await m.evaluate(() => document.documentElement.scrollWidth > innerWidth)); }
  await m.screenshot({ path: SHOT + '/f8_mobile_org.png' });
  console.log('issues:', JSON.stringify(issues)); await b.close();
})();
