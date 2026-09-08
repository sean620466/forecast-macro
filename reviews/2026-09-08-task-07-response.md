# 과제 07 응답 — 공식 발표 일정 기반 마감시각

작성: Claude. 브랜치 `claude/task-07-release-schedule` (리뷰 6 브랜치 위에 쌓임).

## 구현

- `data/release_schedule.csv`: BLS CPI·Employment Situation(2025-11~2026-11 기준월), FOMC 2026 정기회의 8회.
  각 행에 `source_url`, `fetched_at`. BLS는 스크립트 요청을 403으로 거부하므로 브라우저로 공식 페이지를 읽어 전사했다.
- `release_schedule.py`: CSV 로더(`America/New_York` 강제, https 출처 강제, 중복 금지), 계약 본문의
  "October 2, 2026, at 8:30 AM ET"·"Sep 16, 2026 meeting" 파서, `verify_close_time`.
- `verify_close_time` 규칙: 본문이 진술한 발표 시각이 공식 일정에 **정확히** 있어야 `outcome_at`. 거래소 마감이
  `outcome_at` 이후면 거부(결과를 알고 거래 가능). 이전이면 그대로 `closes_at`으로 채택(보수적). 2일 이상 앞서면 거부.
- 탐색 결과에 `venue_close_raw` 보존. `verify_market_rules.py`가 계약별로 검증해 `close_time_verified`, `outcome_at`,
  `closes_at`을 채우고 evidence에 기록.
- R7-H1: 스크립트의 `signal_eligible`을 `approved_contracts`로 분리. `signal_eligible`은 항상 `false`.

## 실측 (2026-09-08)

| 그룹 | close_time | 상태 |
| --- | --- | --- |
| Core CPI 8월 (10건) | 검증됨: outcome 09-11 08:30 ET, 거래소 마감 09-11 03:59Z(이전) | `rules_required` — 시리즈 불일치 유지 |
| 실업률 9월 (9건) | 검증됨: outcome 10-02 08:30 ET (=12:30Z), 거래소 마감 10-02 08:30Z(이전) | **`approved`** 9건 |

`approved_contracts: 9`, `signal_eligible: false`. 테스트 110건 통과.

## 제안 결정 (D-014, Proposed)

거래소가 보고하는 마감·정산 시각은 참고용이다. `outcome_at`은 공식 발표 일정(`data/release_schedule.csv`)에서만 생성하고,
거래소 마감이 공식 발표 이후이면 계약을 거부한다. 일정 CSV의 각 행은 출처 URL과 수집 시각을 보존한다.

## 다음 과제 (08)

승인된 이벤트의 YES 호가를 수집해 `market_pricing.build_event_price_snapshot`으로 확률 스냅샷을 기록한다.
이것이 D-007이 요구하는 "시장 baseline"의 첫 데이터다.
