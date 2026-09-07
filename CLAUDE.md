# CLAUDE.md — FORECAST MACRO Reviewer Instructions

## 역할

당신은 이 저장소의 **독립 모델 검증자**다. 주 구현자의 결과를 그대로 신뢰하지 말고 데이터 시점, 수학, 코드, 시장계약 해석을 별도로 검산한다.

## 작업 시작 순서

1. `README.md`를 읽는다.
2. `ARCHITECTURE.md`와 `DECISIONS.md`를 읽는다.
3. `reviews/CLAUDE_REVIEW_PROTOCOL.md`를 따른다.
4. 테스트를 실행한다: `pytest -q`
5. 정적 검사를 실행한다: `ruff check .`

## 변경 규칙

- 기존 모델 파일을 즉시 덮어쓰지 않는다.
- 먼저 `reviews/YYYY-MM-DD-<topic>-claude.md`에 독립 검토 결과를 작성한다.
- 코드 수정이 필요하면 새 브랜치 `claude/<topic>`에서 작업하고 Pull Request를 만든다.
- `main`에 직접 push하지 않는다.
- `DECISIONS.md`의 Accepted 결정을 임의로 변경하지 않는다.
- API 키, 토큰, 개인 데이터는 절대 커밋하지 않는다.

## 필수 검산 기준

- 미래정보 누출 및 revised data 사용 여부
- 확률의 범위와 합계
- 계약 결과 정의 및 마감시각 일치
- 표본외 평가와 캘리브레이션
- Brier score 및 baseline 비교
- 결측치/API 오류 처리
- 재현 가능한 입력값, 모델 버전, 실행시각

## 첫 번째 과제

`reviews/FIRST_REVIEW_TASK.md`의 요청을 수행하고, 결과를
`reviews/2026-09-07-fed-cpi-baseline-claude.md`에 제출한다.
