# 과제 12 응답 — Kalshi 누적 임계값 사다리 → 구간 확률

작성: Claude. 브랜치 `claude/task-12-kalshi-ladder`.

## 구현

- `contracts.normalize_threshold_ladder`: YES = P(상단 > F)인 rung들을 0.25 간격 연속성·단조성 검사 후 배타 구간으로 변환.
  `P(≤F1) = 1 − Y1`, `P(= Fk+0.25) = Yk − Yk+1`, `P(> Fn) = Yn`. 범위는 인접 rung의 bid/ask 차이. mid 기준 합은 정확히 1.
- 탐색: Kalshi 행에 `strike`, `strike_type` 보존. 검토: `strike_type == "greater"` 그룹은 사다리 검증(`_validate_ladder`).
- 규칙: `parse_kalshi_rules` — `rules_primary`/`rules_secondary`를 본문으로, "Federal Reserve's official website" 등 정확 문구만
  공식 URL로 매핑. 회의일은 "Sep 16, 2026 meeting" 문구를 파싱해 공식 일정과 대조.
- 가격: `price_ladder_event` — 이벤트의 `/markets` 응답에서 top-of-book YES 호가를 한 번에 읽어 정규화.
- `verify_market_rules.py`: 구조 검토를 먼저 돌려 거부된 그룹은 규칙을 조회하지 않음(1,797건 중 조회 대상 ~320건, 68초).

## 실측 (2026-09-08 02:41 UTC)

| 이벤트 | 결과 |
| --- | --- |
| KXFED-26SEP (9월 16일 FOMC) | 가격 성공. 상단 3.75% 0.470, 4.00% 0.510, 4.25% 0.010. Σbid 0.96, Σask 1.11. **정정(2026-09-08)**: 현재 목표범위 상단이 3.75%(2025-12-10 이후)이므로 이는 **동결 0.47 / 25bp 인상 0.51 / 인하 0.005**다. 처음 보고서의 "인하 0.47" 해석은 현재 금리를 4.00으로 잘못 가정한 것 |
| KXFED-26OCT (10월 28일) | 가격 성공. 3.75% 0.328, 4.00% 0.562, 4.25% 0.065 |
| KXFED-26DEC, 27JAN, 27MAR, 27APR | 승인됐으나 꼬리 rung 스프레드 > 0.10으로 거부 (R12-M1) |
| Polymarket 964993 실업률 | 가격 성공 (D-015) |

승인 96건, `signal_eligible=false`. 테스트 133건 통과.

## 의미

Fed 모델이 예측하는 "다음 회의 인하 확률"에 대해 시장 확률(9월: 인하 0.005, 동결 0.47, 인상 0.51)을 처음으로 같은 결과공간에서 얻었다. 사다리를 cut/hold/hike로 접을 때는 반드시 실제 현재 상단(DFEDTARU)을 기준으로 해야 하며, `live_comparison.market_cut_probability`가 그렇게 한다.
D-007이 요구하는 시장 baseline이 Fed 결정에 대해서도 축적되기 시작한다. 모델 쪽은 아직 실시간 특징(최신 CPI·실업률·정책금리 vintage)을
만드는 경로가 없으므로 비교는 다음 과제다.
