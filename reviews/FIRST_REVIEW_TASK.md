# First Claude Review Task

## 목표

현재 Fed 및 CPI baseline 모델이 수학적으로 일관되고 향후 백테스트에 적합한 구조인지 독립 검토한다.

## 검토 대상

- `src/forecast_macro/models/fed.py`
- `src/forecast_macro/models/cpi.py`
- `src/forecast_macro/signals.py`
- `src/forecast_macro/data/fred.py`
- `tests/test_models.py`

## 요청 사항

1. 테스트와 Ruff를 실행한다.
2. Fed 모델의 각 계수 방향이 경제적으로 타당한지 검토한다.
3. CPI bucket 경계값 처리와 확률 합계를 독립 계산한다.
4. 미래정보 누출 위험과 FRED revised-data 위험을 찾는다.
5. 빠진 실패 테스트를 제안한다.
6. Critical/High/Medium/Low로 발견사항을 분류한다.
7. 코드 변경 전 리뷰 문서를 먼저 커밋한다.

## 제출물

- 브랜치: `claude/review-fed-cpi-baseline`
- 파일: `reviews/2026-09-07-fed-cpi-baseline-claude.md`
- Pull Request 제목: `Claude review: Fed and CPI baseline`

리뷰에는 PASS, PASS WITH CHANGES, FAIL 중 하나의 결론을 포함한다.
