# 다이어그램

[diagram-design](https://github.com/cathrynlavery/diagram-design) 규칙(직교 커넥터, 마스크 라벨, 4px 격자, 그림자 없음)으로 그리고, 노웨어 색(크림 종이 + 파란 포인트)을 입혔어요. 브라우저로 `.html`을 바로 열면 돼요.

| 파일 | 보여주는 것 |
|---|---|
| [org-chart.html](org-chart.html) | 217명·9개 본부·실 조직도 (숫자는 실제 로스터에서 계산) |
| [architecture.html](architecture.html) | 한 프로세스 안의 HTTP 경계, 외부 LLM, 평가·CI |
| [sequence.html](sequence.html) | 출근 도장 → 브리핑 → 사람 승인 → 발송 |
| [feedback-loop.html](feedback-loop.html) | 피드백이 평가 사례가 되어 배포를 지키는 순환 |

다시 만들기: `python docs/diagrams/build.py` (`dd.py`가 스타일 도우미, `loop.py`가 루프 기하).

점검: 접근성·단일 파일 검사(`self_check.py`)는 4장 모두 통과. 연결선 검사(`verify_geometry.py`)는 3장이 통과했고, 루프는 중심으로 향하는 점선 2개가 대각선이라고 표시돼요. 루프 유형의 문서가 정한 예외(방사형 점선)라 그대로 뒀어요.
