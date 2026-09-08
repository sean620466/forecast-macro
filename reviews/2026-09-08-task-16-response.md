# 과제 16 응답 — D-016 3원 결과공간 구현

작성: Claude. 브랜치 `claude/task-16-three-way`. 사용자가 2026-09-08 D-016을 승인했다.

## 구현

- `models/fed.py`: `rate_decision_probabilities` → cut/hold/hike. cut은 기존 식+ZLB 마스크 그대로, 나머지를 인상 점수(σ)로 분할
  (`split_remainder`). `rate_cut_probability`는 그 위의 이진 뷰로 유지. 3원의 cut 성분 == 이진 P(cut)을 테스트로 고정.
- `fed_model_comparison.py`: 조건부 인상 로지스틱(`fit_hike_given_no_cut`, 인하가 아닌 회의에서 hike vs hold). 보고서에
  `three_way_brier`, `three_way_climatology_brier`, `hold_brier`, `hike_brier`, `actual_hikes` 추가.
- `fed_backtest.py`: 예측 행에 hold/hike 확률과 실제 결정, 같은 3원 지표 추가.
- `live_comparison.py`: 모델·시장 3원 벡터와 결과별 edge, 시장 hold/hike의 `[bid, ask]` 범위. 모델 버전 `fed-live-0.2-three-way-uncalibrated`.
  실시간 스크립트의 학습 데이터 기본값을 2019–2026으로 변경.
- 체크인된 백테스트 JSON 8개 재생성. cut 관련 지표는 전부 불변(회귀 테스트로 확인), 3원 필드만 추가.

## 결과 (3원 Brier, 낮을수록 좋음)

| 모델 | 표본 | 3원 Brier | 3원 climatology | hike Brier | hold Brier |
| --- | --- | ---: | ---: | ---: | ---: |
| 휴리스틱 window | 2019–2026 | 0.688 | 0.532 | 0.247 | 0.357 |
| 로지스틱 WF | 2019–2024 | 0.344 | 0.556 | 0.114 | 0.161 |
| 로지스틱 WF | 2019–2026 | 0.353 | 0.525 | 0.087 | 0.168 |

휴리스틱의 인상 성분은 climatology보다 나쁘다(R16-M1). 부호를 뒤집은 대칭 가정이 틀린 것이고, 표본을 보고 고치지 않는다.
로지스틱은 인상을 잘 학습하지만 표본에 인상 사이클이 하나뿐이다(R16-L1).

## 다음 실시간 기록부터

`fed_market_comparisons/`에 모델 3원 벡터와 시장 3원 벡터(범위 포함), 결과별 edge가 함께 남는다. 9월 16일 회의 기준으로는
시장 hike 0.525 vs 모델 hike를 처음으로 나란히 볼 수 있다. `signal_eligible=false`는 그대로다.

테스트 153건 통과.
