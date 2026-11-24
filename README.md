# Project Nowhere (프로젝트 노웨어)
> 가상 기업 **노웨어**를 위한 LLM 업무 자동화 플랫폼: 출근 브리핑 비서 · 문서 자동 처리 · 단계적 자동화 · 평가/운영 체계

구성: `app/`(비서·문서 처리 서비스) · `world/`(노웨어 사내 시스템: SSO·메일·메신저·이슈·포털·근태) · `eval/`(평가) · `tests/`

## 실행 (화면 포함)
```bash
pip install -r requirements.txt && (cd web && npm install)
DEFAULT_MODE=shadow ./run_demo.sh          # 사내 시스템(:9000) + 비서(:8000)
cd web && npm run dev                      # http://localhost:5173  (직원 앱 + 관리자 콘솔)
```
`web/`은 React + TypeScript(Vite) 앱입니다. 디자인 토큰(`src/styles.css`)과 공용 컴포넌트(`src/ui.tsx`)로 라이트/다크, 모바일 하단 내비를 지원합니다.
출근하기 → 근태 시스템 → 서명된 웹훅 → 비서 브리핑 생성 흐름이 화면에서 그대로 동작합니다.

## 문서 자동 처리 (DocFlow 모듈)

메일·문서 텍스트를 받아 **LLM이 분류·추출**하고, **업무 규칙(가드레일)** 을 통과하면 **ERP/HR/구매/CS 시스템에 API로 자동 연계**합니다.
애매하거나 위험한 건은 **사람 검수 큐**로 보내고, 모든 처리는 **감사 로그**와 **비용·지연 메트릭**으로 남습니다.

> 핵심 메시지: 자동화(연계)는 기본이고, **LLM 결과의 품질·안전·비용을 운영 관점에서 책임지는 구조**.

## 흐름
```
문서 → LLM 추출(JSON, 스키마 검증, 1회 재시도) → 가드레일(신뢰도/금액/필수값)
     ├─ 통과 → ERP 연계(processed)
     └─ 보류 → 사람 검수(승인/수정/반려) → ERP 연계(approved)
모든 단계: audit 로그 · llm_calls(토큰/지연/비용) 기록
```

## 가상 기업 "노웨어(Nowhere)" — 핀테크·인슈어테크 스타트업
실제 회사처럼 **자체 시스템들이 따로 있는 환경**(`world/`)을 만들고, AI 비서가 그 시스템에 API로 연동되게 했습니다.
| 시스템 | 내용 |
|---|---|
| SSO | 사내 계정·토큰 발급(데모용 HMAC 토큰. 실제는 OIDC/SAML) |
| 사내 메일 서버 | 받은편지함(페이지네이션), 메일 조회, 발송. 당사자가 아니면 403 |
| 사내 메신저 | 공개/비공개 채널. 비멤버는 목록에도, 메시지 조회에도 접근 불가 |
| 이슈 트래커 | 담당자·팀·임원 에스컬레이션 기준 가시성 |
| 포털 | 공지·게시판(대상 부서 제한) |
| 근태 | 출근 시 비서에 **HMAC 서명 웹훅** 전송 |
- 권한은 **각 시스템이 사용자 본인 토큰으로 강제**합니다. 비서는 사용자가 직접 열 수 있는 것 이상을 볼 수 없습니다.
- 임직원 13명, 임원 전용 채널, 인젝션 메일, 광고, 규제 관련 메일 등 실무형 함정을 시드 데이터에 심어 두었습니다.
```bash
./run_demo.sh                 # world(:9000) + assistant(:8000) 두 프로세스
python -m eval.briefing_eval --world
```

## AI 업무 비서 (출근 브리핑 · 사내 소식 요약)  → `/assistant-ui`
출근 도장을 찍으면 밤새 도착한 메일·이슈를 정리해 **오늘의 할일**을 보고하고, 별도 탭에서 Slack·공지·게시물을 요약합니다. 사원과 임원은 같은 구조에서 **역할별로 다른 브리핑**(사원=실행할 일, 임원=결정·승인·리스크)을 받습니다.
| 안전장치 | 구현 |
|---|---|
| 출처 강제(환각 차단) | 모든 할일은 실제 원본 `source_ids`를 인용해야 함. 없는 출처를 인용한 항목은 코드에서 제거 |
| 권한 필터 | 사용자·역할·팀 기준으로 원본 단계에서 걸러냄(임원 전용 채널은 사원에게 아예 전달 안 됨) |
| 프롬프트 인젝션 | 메일·채팅 본문은 신뢰하지 않는 데이터. 지시문 의심 항목은 할일에서 제외하고 "보안 확인 필요"로 격리 |
| 장애 대응 | LLM 실패 시 규칙 기반 요약으로 자동 대체(`degraded` 표시) |
| 재출근 | 같은 날 다시 찍어도 브리핑을 재생성하지 않음(비용·할일 목록 일관성) |
| 피드백 | 완료/관련 없음 기록 → 이후 평가셋·프롬프트 개선에 사용 |
평가: `python -m eval.briefing_eval` (필수 처리 항목 재현율·정밀도, 인젝션 유출 0건).
**데모는 샘플 데이터**(`app/assistant/demo_data.json`)입니다. 실제 연동은 `Source` 인터페이스(메일·Slack·Jira·그룹웨어)를 구현하고, 출근 이벤트는 근태 시스템 웹훅이 `POST /assistant/clock-in`을 호출하도록 연결합니다. 사용자 식별은 SSO로 교체해야 합니다.

## 점진적 자동화 (Shadow → Assisted → Auto)
문서 유형별로 AI에게 자율권을 단계적으로 부여합니다. 승격은 **사람과의 일치율**로만 결정합니다.
| 단계 | 동작 | 다음 단계 조건(기본값) |
|---|---|---|
| shadow | AI는 제안만 기록, 사람이 평소대로 처리 후 결과를 입력해 비교 | 표본 20건 이상 & 일치율 **95% 신뢰구간 하한** ≥ 0.85 |
| assisted | AI가 채운 값을 사람이 모두 승인/수정 | 표본 30건 이상 & 하한 ≥ 0.95 |
| auto | 가드레일 통과 건 자동 연계 + 10% 감사 샘플 사람 확인 | 최근 결과 하한 < 0.90 이면 **자동 강등** |
- Wilson 하한을 써서 "5건 중 5건 일치" 같은 작은 표본이 완벽해 보이는 착시를 막습니다.
- 승격은 추천만 하고 담당자가 승인, 강등은 즉시 자동 적용합니다.
- 기본값은 안전하게 shadow입니다(`DEFAULT_MODE`).

## LLMOps 요소
| 요소 | 구현 |
|---|---|
| 프롬프트 버전 관리 | `app/llm/prompts.py`, `PROMPT_VERSION` 환경변수 |
| 평가셋 + 회귀 게이트 | `eval/dataset.jsonl`, `python -m eval.run_eval --min-acc 0.9` (CI에서 실행) |
| 비용·지연·성공률 | `llm_calls` 테이블, `GET /metrics`, 대시보드 |
| 출력 검증/장애 대응 | pydantic 스키마, JSON 파싱 허용, 재시도, 실패 시 `failed`로 안전 종료 |
| 안전장치 | 신뢰도 임계값, 금액 한도, 프롬프트 인젝션 방어는 **코드 규칙**으로(모델에 의존 안 함) |
| 사람 개입 | `POST /documents/{id}/review` (승인/수정/반려, 담당자 기록) |
| 보안 | 선택적 `X-API-Key`, 문서는 `<document>` 태그로 격리 후 "지시 무시" 규칙 |

## 실행
```bash
pip install -r requirements.txt
LLM_PROVIDER=mock uvicorn app.main:app      # API 키 없이 데모 (규칙 기반 모의 LLM)
export ANTHROPIC_API_KEY=...                # 설정하면 자동으로 Claude 사용
uvicorn app.main:app                        # http://localhost:8000  (UI) / /docs (API)
docker compose up --build
python -m pytest -q
python -m eval.run_eval                     # 평가
```
주요 환경변수: `LLM_PROVIDER(auto|claude|mock)`, `CLAUDE_MODEL`, `CONFIDENCE_THRESHOLD`, `PRICE_IN_PER_MTOK/PRICE_OUT_PER_MTOK`, `ERP_URL`(미설정 시 내장 모의 ERP), `DOCFLOW_API_KEY`.

## 무료/로컬 모델로 실행 (OpenAI 호환)
```bash
# Ollama (무료, 키 불필요)
ollama pull qwen2.5:7b
LLM_PROVIDER=openai LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=qwen2.5:7b python -m eval.run_eval --prompt v2
# Gemini 무료 티어 / Groq / OpenRouter: LLM_BASE_URL, LLM_MODEL, LLM_API_KEY만 바꿉니다.
```

## 현재 한계 (솔직하게)
- 평가 정확도 1.0은 **mock(규칙 기반) 기준**이며 12건의 작은 데이터셋입니다. 실제 Claude 수치는 API 키로 `eval.run_eval`을 돌려 README에 갱신해야 합니다.
- UI는 정적 HTML 1장입니다(React 미적용). DB는 SQLite, 인증은 단일 API 키 수준입니다.
- 입력은 텍스트만 지원합니다(PDF/엑셀/메일 수집은 다음 단계).
