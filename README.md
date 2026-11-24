# DocFlow — LLM 기반 업무 문서 자동 처리 서비스

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

## 현재 한계 (솔직하게)
- 평가 정확도 1.0은 **mock(규칙 기반) 기준**이며 12건의 작은 데이터셋입니다. 실제 Claude 수치는 API 키로 `eval.run_eval`을 돌려 README에 갱신해야 합니다.
- UI는 정적 HTML 1장입니다(React 미적용). DB는 SQLite, 인증은 단일 API 키 수준입니다.
- 입력은 텍스트만 지원합니다(PDF/엑셀/메일 수집은 다음 단계).
