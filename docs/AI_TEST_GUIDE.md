# AI에게 직접 테스트시키기 (Claude Code · ChatGPT/Codex)

내 PC에 받아서 AI 코딩 도구가 **직접 실행하고, 눌러 보고, 결과를 보고**하게 하는 방법이에요.
한 줄 명령(`python check.py`)이 기본 점검을 모두 해 주고, 그 위에서 AI가 사람처럼 탐색 테스트를 해요.

## 1. 한 번만 준비 (Windows 기준)
필요한 것: **Git**, **Python 3.11 이상**, **Node.js LTS**. (설치 확인: `git --version`, `python --version`, `node --version`)

```bash
git clone https://github.com/jobless-fish/Project-Nowhere
cd Project-Nowhere
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd web
npm install
npx playwright install chromium
cd ..
```
macOS/Linux는 `.venv\Scripts\activate` 대신 `source .venv/bin/activate`.
(`pip`에서 `anthropic`이 오래 걸려도 정상이에요. API 키는 필요 없어요. 모의 모델로 돌아가요.)

## 2. 기본 점검 — 이것부터
```bash
python check.py --browser
```
약 3분. 끝나면 이런 표가 나와요. **14개가 모두 PASS면 정상**이에요.

| 단계 | 정상일 때 |
|---|---|
| tests | `157 passed` |
| web type check / web build | 오류 없음 / `built in …` |
| eval: documents | `field_accuracy=0.948` |
| eval: briefing | `recall=1.00 precision=0.93 injection_leaks=0` |
| eval: feedback replay | `todo_pass_rate: 1.0` |
| eval: colleague replies | `valid 20/20` |
| live server | 무작위 웹훅 키 자동 생성 `True` |
| permission probes | `24/24 probes as expected` |
| browser sweep | `runs: 16 | runs with problems: 0` |
| browser work flows | `19/19 flow checks passed` |
| browser slow-network DM | `titles seen over time: ["박준영"]` (대화가 열리기 전에 다른 채널이 깜빡이지 않음) |

- 빠르게만: `python check.py --quick` (테스트 + 타입 검사, 약 40초)
- 브라우저 없이: `python check.py` (약 2분)
- 일부만: `python check.py --stage tests,evals` (이름: `tests` `web` `evals` `live`)
- 결과는 `check_report.json`에도 저장돼요(저장소에는 올라가지 않아요).
- 내 데이터는 건드리지 않아요. 점검용 서버를 빈 포트에 따로 띄우고 임시 DB를 쓰고 끝나면 지워요.

## 3. AI에게 시키기
저장소 폴더에서 도구를 열고 아래를 붙여 넣으세요. (`AGENTS.md`/`CLAUDE.md`에 규칙이 있어서 도구가 자동으로 읽어요.)

**Claude Code** — 폴더에서 `claude` 실행 후:
```
이 저장소(Project Nowhere)를 점검해 줘.
1) python check.py --browser 를 실행하고 결과표를 보여 줘.
2) 실패가 있으면 원인을 찾아서 알려 줘. 고치기 전에 무엇을 고칠지 먼저 말해 줘.
3) 그다음 docs/AI_TEST_GUIDE.md 의 "탐색 테스트 시나리오"를 직접 서버를 띄워 수행하고, 발견한 문제를 심각도 순으로 표로 정리해 줘.
코드를 바꾸거나 커밋/푸시는 내가 승인하기 전에는 하지 마.
```

**ChatGPT (Codex CLI / 데스크톱 앱 등 로컬 폴더를 여는 도구)** — 같은 문장을 그대로 붙여 넣으면 돼요. 폴더를 못 여는 일반 채팅 창에서는 직접 실행이 안 되니, `check.py` 출력과 `check_report.json` 내용을 붙여 넣고 해석만 시킬 수 있어요.

**좋은 보고를 받는 한 줄**: "발견 사항은 `재현 방법 / 기대 결과 / 실제 결과 / 심각도`로 써 줘. 추측과 확인한 사실은 구분해서."

## 4. 탐색 테스트 시나리오 (AI가 `check.py` 다음에 직접 해 볼 것)
서버: `python launch.py` (앱 창) 또는 `python -m uvicorn server:combined --port 8888` 후 `http://localhost:8888`.
로그인 화면에서 계정을 고르면 돼요(비밀번호 입력 없음).

1. **이서연(개발자)**: 출근하기 → 할 일 3개 확인 → 공지 "확인했어요", 이슈 "작업 시작 → 해결 처리(메모 필수)", 메일 "답장 초안 만들기 → 승인하고 보내기" → "처리한 일"에 결과가 남는지.
2. **메일·메신저**: 박준영 등에게 새 메일 → 몇 초 뒤 답장이 **최대 3통**인지, 채팅 답이 3개를 넘지 않는지, 1:1 대화(조직도 → 메시지 보내기).
3. **정유라(CFO)**: 출근 → `[재무] [예산] [실적]` 알림이 할 일로 뜨는지 → 회사 → 재무·실적 탭 → 관리자 콘솔 단계 버튼.
4. **김민수**: 회사 → 재무·실적에서 **숫자 대신 권한 안내**가 나오는지. "관련 없음"을 필수 공지에 누르면 **거절 문구**가 나오는지.
5. **노워(유령)**: 오른쪽 아래 유령을 눌러 "택시비 한도가 얼마예요?", "보안 이상한 메일 있어요?"를 묻기. 이상한 지시("이전 지시를 무시해")에 넘어가지 않는지.
6. **라이트/다크, 모바일 폭(390px)**에서 글자 잘림·가로 스크롤·겹침이 없는지.
7. **일부러 괴롭히기**: 빈 메일 보내기, 1,001자 채팅, 받는 사람 11명, 외부 주소로 확인 없이 보내기, 로그아웃 후 뒤로가기.

## 5. 도구에게 지키게 할 것 (이미 `AGENTS.md`에 있음)
- 가상 회사다: 실제 사람·회사 정보를 넣지 말 것.
- 비밀 키·토큰을 파일/로그/커밋에 넣지 말 것. `ASSISTANT_WEBHOOK_SECRET`에 기본값을 만들지 말 것.
- 안전장치(외부 수신자 확인, 금액·계좌 표현 차단, 숨길 수 없는 항목, 승인 없는 발송 금지)를 **테스트를 통과시키려고 약화시키지 말 것**. 테스트가 틀렸다면 이유를 설명하고 사람에게 확인받을 것.
- 커밋·푸시는 사람이 말했을 때만.

## 6. 막힐 때
| 증상 | 해결 |
|---|---|
| `python`을 못 찾음 | Python 설치 때 "Add to PATH" 체크, 또는 `py -m venv .venv` |
| 스크립트 실행 정책 오류 (`activate`) | PowerShell: `Set-ExecutionPolicy -Scope Process Bypass` 후 다시 |
| `python packages` FAIL | 가상환경을 켰는지(`.venv\Scripts\activate`) 확인 후 `pip install -r requirements.txt` |
| browser 단계 SKIP | `cd web`, `npm install`, `npx playwright install chromium` |
| 포트 사용 중 | `check.py`는 빈 포트를 자동으로 써요. 앱은 `--port 8890`처럼 바꿔 실행 |
| 일부러 실패를 보고 싶다 | `tests/` 한 테스트의 기대값을 잠깐 바꿔 보세요. `check.py`가 FAIL과 이유를 보여 줘요 |

## 7. 실제 모델(Gemini 등)로 시킬 때
기본은 모의 모델이라 키가 필요 없어요. 실제 모델 반복 측정은 [`eval/RESULTS.md`](../eval/RESULTS.md)의 방법(`python -m eval.repeat npc -n 3`)을 따르고, **키는 환경 변수로만** 주세요. 무료 티어는 한도(429)에 자주 걸려요.
