# 과제 08 응답 — 승인 이벤트 가격 스냅샷

작성: Claude. 브랜치 `claude/task-08-price-snapshots` (과제 07 위에 쌓임).

## 구현

- `price_snapshots.py`: 후보·리뷰 JSON에서 **모든 계약이 `approved`인 이벤트만** 선택(`approved_events`), 이벤트별로
  `build_event_price_snapshot`을 호출해 성공하면 정규화 확률, 실패하면 거부 사유를 기록(`price_event`). 두 경우 모두
  원시 호가·규칙 해시·`outcome_at`·북 갱신 시각을 보존한다. `signal_eligible`은 항상 `false` (D-012).
- `data/polymarket.py`: `/books` 일괄 조회에서 관측 시각을 **한 번의 수집 시각**으로 통일(`raw_orderbooks`,
  `parse_polymarket_orderbooks(observed_at=)`). 북 자체의 `timestamp`는 마지막 변경 시각이라 조용한 구간에서 수십 초
  차이가 나며, 이를 관측 시각으로 쓰면 5초 skew 검사가 정상 북을 거부한다. 변경 시각은 `book_updated_at`으로 따로 기록.
- `scripts/snapshot_market_prices.py`: 워크플로 단계로 추가. 이벤트별 파일 `artifacts/prices/market_prices_<UTC>.json`.

## 실측 (2026-09-08 01:50 UTC, Polymarket 964993 실업률 9월)

파이프라인은 끝까지 돌았고 게이트가 **거부**했다: "outcome prices are too far from a complete market".

| 구간 | bid | ask | mid |
| --- | ---: | ---: | ---: |
| ≤3.8% | 0.022 | 0.059 | 0.041 |
| 3.9% | 0.02 | 0.07 | 0.045 |
| 4.0% | 0.17 | 0.21 | 0.190 |
| 4.1% | 0.34 | 0.36 | 0.350 |
| 4.2% | 0.28 | 0.30 | 0.290 |
| 4.3% | 0.11 | 0.12 | 0.115 |
| 4.4% | 0.03 | 0.07 | 0.050 |
| 4.5% | 0.012 | 0.048 | 0.030 |
| ≥4.6% | 0.011 | 0.048 | 0.030 |
| **합계** | **0.995** | **1.285** | **1.141** |

mid 합 1.14는 D-010 허용치(±5%)를 넘는다. 원인은 꼬리 구간의 넓은 스프레드다. 이건 게이트 결함이 아니라 시장 구조이며,
fail-closed가 의도대로 작동한 것이다. 다만 이 상태로는 실업률 이벤트에서 시장 baseline을 영영 얻지 못한다.

## 제안 (D-010 재검토, Proposed)

- bid 합(0.995)과 ask 합(1.285)을 각각 확률의 하한·상한 근거로 기록한다. bid 합이 1에 가깝다는 것은 시장이 완전함을 뜻한다.
- 정규화 확률은 mid 대신 스프레드 역수 가중 또는 bid·ask 중 보수적 값으로 계산하고, 각 구간에 `[bid, ask]` 구간을 함께 저장한다.
- 허용치 검사는 mid 합이 아니라 "bid 합 ≤ 1 ≤ ask 합"과 "ask 합 − bid 합 ≤ 상한(예: 0.35)"으로 바꾼다.
- 어떤 방식이든 결정으로 등록한 뒤 구현한다. 지금 코드는 기존 D-010을 그대로 따른다.

테스트 115건 통과.
