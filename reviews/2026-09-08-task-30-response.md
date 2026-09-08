# 과제 30 응답 — D-017(예측 cutoff 정렬), D-018(먼 만기 사다리 폭)

작성: Claude. 사용자가 2026-09-08 두 결정을 승인했다.

## D-017

- 실시간: `build_comparison(schedule=...)`이 회의일에 CPI/고용보고서 발표가 있으면 `same_day_release=true`, 시리즈 목록 기록.
- 백테스트: 스냅샷 빌드(`--first-release-dates`)가 최신 입력의 **다음 달** 발표일을 ALFRED에서 조회해 회의일과 같으면 플래그.
  `fed_backtest` 보고서에 `same_day_release_meetings`, 제외 Brier 추가(플래그 없는 파일은 `null`).
- 채점: `comparison_scoring`이 같은 날 발표·저유동성 기록을 집계에서 분리하고 `clean_*` 지표를 D-007의 헤드라인으로 둔다.

## D-018

- `ladder_width_limit(as_of, outcome_at) = min(0.60, 0.35 + 0.05·max(0, 개월−2))`. 사다리 가격에 적용, `completeness`에
  `width`, `width_limit`, `low_liquidity` 기록. 시장 baseline 기록(`MarketCutProbability.low_liquidity`)으로 전파.

테스트 177건 통과. 8개 백테스트 JSON 재생성(값 불변, 필드 추가).
