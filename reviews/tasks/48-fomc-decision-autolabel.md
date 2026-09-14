# 과제 48 — 결정 후 첫 채점(D-007)이 사람 없이 돌아가게 하기

사용자 지시(2026-09-14): "2026-09-16 FOMC 결정 후 첫 채점(D-007)이 자동으로 돌아가는지 워크플로와 comparison_scoring을 점검하고, 안 되면 고쳐서 main에 반영해."

## 목표

2026-09-16 14:00 ET 결정 다음 평일 실행(09-17 13:40 UTC)에서 `fed_market_scoring.json`의 `scored_meetings`가 0에서 1이 되고
`scoring` 이슈가 열려야 한다. 사람이 CSV를 편집하는 단계가 그 사이에 있으면 안 된다.

## 검토 대상

- `.github/workflows/compare-fed-market.yml`의 단계 순서와 persist 경로
- `src/forecast_macro/comparison_scoring.py`의 라벨 출처(`meetings`)
- `scripts/score_fed_comparisons.py`가 읽는 회의 CSV와 그 CSV가 갱신되는 경로
- `scripts/scoring_alerts.py` / `alerts.py`의 fed 토픽 경로

## 확인 질문

1. 결정 라벨은 어디서 오는가? 그 출처가 결정 다음 날 아침에 자동으로 갱신되는가?
2. 회의 CSV를 자동으로 늘리면 무엇이 깨지는가(학습 스냅샷, 회귀 테스트)?
3. 결정 문장 파싱은 어떤 문구를 지원해야 하는가(유지·인하·인상·ZLB·반대표)?
4. 보도자료를 못 받으면 워크플로는 어떻게 실패하고 사람은 무엇을 해야 하는가?

## 제출물

- `reviews/2026-09-14-fomc-auto-scoring-claude.md`
- 코드: `src/forecast_macro/fomc_decisions.py`, `scripts/record_fomc_decisions.py`, 워크플로 단계, `tests/test_review_48.py`
- `reviews/FINDINGS.md` 행 R48-H1
