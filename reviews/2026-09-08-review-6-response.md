# 리뷰 6 응답 — 반영 내역

작성: Claude (구현자). 보고서 `2026-09-08-market-rules-claude-review-6.md`의 필수 변경 8건을 같은 브랜치에서 반영했다.

## 반영

| ID | 변경 | 검증 |
| --- | --- | --- |
| R6-H1 | `identify_contract_series`: 측정(core/headline), 주기(yoy/mom), 조정(sa/nsa) 각각 명시 근거 필요. 없으면 `None`, `validate_official_rules`는 항상 blocker | `test_underspecified_cpi_contract_is_not_matched_to_model_series` |
| R6-H2 | `official_sources.py` 신설. `review_market_candidates`가 메타데이터 출처를 같은 함수로 검사 | `test_review_rejects_metadata_with_unofficial_source_string` |
| R6-H3 | 해시 canonical = question + description + resolution_source. `rules_version`은 해시 앞 16자. `venue_updated_at`, `fetched_at` 별도 필드 | `test_rules_hash_is_stable_across_updated_at_changes` |
| R6-M1 | 시장 본문이 있으면 시장 수준 전체, 없으면 이벤트 수준 전체. `rules_source_level` 기록 | `test_market_and_event_fields_are_not_mixed` 외 2건 |
| R6-M2 | `<`, `>`, `below`, `above`는 strict 종류로 분리해 blocker. `_subject()`로 그룹 내 제목 일치 검사 | `test_strict_inequality_tails_are_blocked`, `test_mixed_*` |
| R6-M3 | `effective_resolution_source`: 필드가 비었을 때만 본문 URL 중 공식 호스트를 채택, 기원 기록. 비공식 필드는 본문으로 구제하지 않음 | `test_description_url_is_accepted_only_when_official`, `test_field_source_is_not_replaced_by_description_url` |
| R6-L1 | https 강제 | `test_official_host_requires_https_and_exact_domain` |

`scripts/verify_market_rules.py` evidence에 `resolution_source_origin`, `rules_source_level`, `contract_series`,
`expected_series`, `venue_updated_at`, `fetched_at` 추가.

## 실측 (2026-09-08, Polymarket 19건)

| 그룹 | 결과 | 남은 blocker |
| --- | --- | --- |
| Core CPI YoY 8월 (10건) | 출처: 본문 BLS URL 확보. 시리즈 `core_cpi_yoy_nsa` 식별 | 모델 시리즈 `headline_cpi_mom_sa`와 불일치 → 차단 (정상) |
| 실업률 9월 (9건) | 규칙 검증 전부 통과. 시리즈 `unemployment_rate_sa` 일치 | `close_time_verified=False` (R5-H3) |

승인 0건, `signal_eligible=false`. 테스트 100건 통과, ruff 통과.

## 다음 과제 제안

R5-H3: BLS 발표 일정에서 `America/New_York` 기준 `outcome_at`을 생성하고 거래소 `endDate`와 대조. 이것이 되면
실업률 이벤트가 가격 수집 단계(`market_pricing`)로 넘어갈 수 있다. `reviews/tasks/07-release-schedule.md` 참조.
