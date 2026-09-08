# 과제 17 응답 — 실업률 구간 baseline과 시장 비교 기록

작성: Claude. 브랜치 `claude/task-17-unemployment-baseline`.

## 모델 (`models/unemployment.py`)

- 다음 발표치 = 최신 발표치 + Δ, Δ ~ 과거 연속 두 달 변화의 경험분포(0.1 단위 반올림). 1990년 이후, ALFRED 당일 vintage.
- 계약 구간(≤3.8, 3.9, …, ≥4.6)은 계약 제목에서 읽고 연속성을 검증한 뒤, 반올림된 값이 속하는 구간에 확률을 쌓는다. 합은 정확히 1.
- 조정 파라미터 없음. FRED 공개 데이터 기준 1990–2026 1개월 변화 437건: 0이 27%, ±0.1이 45%, ±0.2가 18%, 그 밖 10%.

## 비교 (`unemployment_comparison.py`, `scripts/compare_unemployment_market.py`)

- 다음 Employment Situation 발표(공식 일정)에 정산되는 Polymarket 이벤트의 최신 가격 스냅샷을 찾아, 같은 구간 키로 모델·시장·edge를 기록.
- 기록에 최신치·기준월·history 시작·vintage·변화분포·모델 버전·시장 관측시각·출처 파일 포함. `signal_eligible=false`.
- 평일 워크플로에 단계 추가. 정산 대상 시장이 없으면 기록하지 않고 종료.

## 검증

가짜 history(결측 달 포함)와 실제 계약 제목으로 테스트 4건. 테스트 158건 통과. 첫 실제 기록은 이 커밋의 push로 생성된다.
