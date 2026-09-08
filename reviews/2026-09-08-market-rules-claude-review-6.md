# Claude 독립 검토 보고서 #6 — 시장 규칙 검증 게이트

**대상**: `main` @ `67d6a64` (2026-09-08) — `market_review.py`, `market_rules.py`, `data/polymarket.py`,
`scripts/review_macro_markets.py`, `scripts/verify_market_rules.py`, `.github/workflows/discover-markets.yml`,
`tests/test_market_review.py`, `tests/test_market_rules.py`. 과제: `reviews/FIFTH_REVIEW_TASK.md`.

**검토자**: Claude. 이번 사이클부터 구현도 Claude가 맡으므로 이 보고서 뒤에 같은 브랜치에서 수정을 커밋한다.

## Verdict

**PASS WITH CHANGES.** 게이트는 현재 데이터에 대해 fail-closed로 동작한다: 19건 전부 미승인이고, 거래소 오류·빈 규칙·
비공식 출처는 승인을 열지 못한다. 그러나 (1) 시리즈 식별이 키워드가 없으면 모델 시리즈와 같은 값을 **기본값**으로 내놓아
fail-open이고, (2) 규칙 해시에 `updatedAt`이 포함돼 규칙이 안 바뀌어도 매일 해시가 바뀌며, (3) 시장 수준과 이벤트 수준
규칙 필드가 섞일 수 있고, (4) `review_market_candidates`는 출처 호스트를 검사하지 않아 직접 호출 시 임의 문자열로
승인된다. 실제 시장 가격이 게이트를 통과하기 전에 고쳐야 한다.

## Scope

과제의 8개 확인 항목을 순서대로 검토하고, 리뷰 5의 미반영 시장 항목(R5-M1~M4, H-1 잔여)을 함께 다룬다.

## Reproduction steps

```bash
.venv/bin/ruff check .      # All checks passed
.venv/bin/pytest -q         # 85 passed
# 호스트 검사·수준 혼합·시리즈 기본값 프로브
.venv/bin/python - <<'EOF'
from forecast_macro.market_rules import parse_polymarket_rules, identify_contract_series
d = parse_polymarket_rules({"id":"x","question":"Will CPI be 0.3%?",
    "description":"Resolves per BLS CPI report.","resolutionSource":"https://www.bls.gov/cpi/","updatedAt":"2026-09-08"})
print(identify_contract_series(d, topic="cpi"))   # headline_cpi_mom_sa  <- 근거 없이 모델 시리즈와 일치
EOF
```

## 과제 항목별 결과

| # | 확인 항목 | 결과 |
| --- | --- | --- |
| 1 | pytest / ruff | 통과 (85 / 0) |
| 2 | 불완전·비연속 구간 그룹 승인 불가 | ✓ `_validate_group` blocker가 있으면 `REJECTED`. 단 엄격 부등호(`<`, `>`)를 포함 부등호로 취급하고, 같은 이벤트에 다른 달·다른 시리즈가 섞여도 감지 못함 (M-2) |
| 3 | 규칙 본문·버전·비공식 출처로 해제 불가 | ✓ `validate_official_rules`. 단 `review_market_candidates` 단독 호출 시 우회 (H-2) |
| 4 | 호스트 접미사 속임수 | ✓ `bls.gov.example.com`, `bls.gov@evil.com`, `www.bls.gov.evil.com`, 쿼리 내 URL 모두 차단. `http://` 평문은 통과 (L-1) |
| 5 | 거래소/API 실패 시 fail-closed | ✓ `verify_market_rules.py`가 예외를 blocker로 기록, `signal_eligible = approved > 0`. 탐색 스크립트도 R5-X1로 fail-soft |
| 6 | 시장/이벤트 수준 규칙 혼합 | ✗ `description`, `resolutionSource`, `updatedAt`이 **필드별로** 독립 fallback → 시장 본문 + 이벤트 출처 + 이벤트 버전이 섞인 문서가 만들어짐 (M-1) |
| 7 | `updatedAt`의 버전 적합성 | ✗ 유동성·가격 갱신에도 바뀜(실측 09-07→09-08). 해시 canonical에 포함돼 해시도 같이 바뀜. 불변 스냅샷 시각(`fetched_at`)과 내용 해시 기반 버전 필요 (H-3) |
| 8 | 19건 아티팩트 미승인 유지 | ✓ 전부 `structure_valid_rules_required`. CPI 10건은 `resolutionSource == ""`로 영구 차단(R5-M1), 실업률 9건은 `close_time_verified=False`로 차단 |

## Findings

| 등급 | # | 발견 | 위치 |
| --- | --- | --- | --- |
| **High** | H-1 | `identify_contract_series`가 키워드 부재 시 `headline`/`mom`/`sa`를 기본값으로 반환. "Will CPI be 0.3%?"처럼 정보가 없는 계약이 모델 시리즈 `headline_cpi_mom_sa`와 **일치**로 판정됨. 명시 근거가 없으면 `None`을 반환하고 차단해야 함 | `market_rules.py:identify_contract_series` |
| **High** | H-2 | `review_market_candidates`가 `ContractRuleMetadata`의 세 문자열이 비어있지 않으면 승인. `test_complete_rules_allow_approval`은 `"BLS CPI release"`로 승인됨. 호스트 검사는 `market_rules`에만 있어 두 모듈의 순환 import 때문에 공유되지 않음 | `market_review.py:review_market_candidates` |
| **High** | H-3 | `rules_text_hash`의 canonical JSON에 `rules_version(=updatedAt)` 포함 → 규칙 불변에도 해시 변동. 해시가 버전 역할을 못 함. `fetched_at` 미기록(프로토콜 6항) | `market_rules.py:parse_polymarket_rules` |
| **Medium** | M-1 | 시장/이벤트 수준 필드 혼합 (과제 6항). 한 수준을 통째로 선택하고 `rules_source_level`을 기록해야 함 | `market_rules.py:parse_polymarket_rules` |
| **Medium** | M-2 | 구간 정규식: `<X%`/`>X%`를 `or less`/`or more`와 동일 취급. 그룹 키에 기준 월·시리즈가 없어 "2.1% in August"와 "2.1% in September"가 "duplicate bucket"으로 오진되고, Core CPI와 headline CPI가 한 그룹에 섞여도 통과 | `market_review.py:_bucket, _validate_group` |
| **Medium** | M-3 | `resolutionSource` 빈 값(CPI 10건 실측)이면 본문에 BLS URL이 있어도 영구 차단. 본문 URL을 공식 호스트 allowlist로 추출하는 경로와 출처 기원(`field`/`description`) 기록 필요 | `market_rules.py:validate_official_rules` |
| **Low** | L-1 | `http://www.bls.gov` 평문 URL 통과. https 강제 | `market_rules.py` |
| **Low** | L-2 | `verify_market_rules.py`의 `MODEL_SERIES["cpi"] = "headline_cpi_mom_sa"`는 CPI 모델(MoM 구간)의 시리즈이지만 Fed 모델 특징은 `CPIAUCNS` YoY NSA. 어느 모델과 비교하는지 계약별로 명시 필요 | `scripts/verify_market_rules.py` |

## Required changes (이 브랜치에서 반영)

1. (H-1) 시리즈 식별을 명시 근거 기반으로 바꾸고, 식별 불가 시 항상 blocker.
2. (H-2) 공식 출처 판정을 `official_sources.py`로 분리해 `market_review`와 `market_rules`가 공유. `review_market_candidates`가 호스트를 직접 검사.
3. (H-3) 해시 canonical에서 `updatedAt` 제거. `rules_version`을 내용 해시 기반으로, `venue_updated_at`과 `fetched_at`을 별도 보존.
4. (M-1) 수준 선택 일원화 + `rules_source_level`.
5. (M-2) 엄격 부등호 blocker, 그룹 내 subject(숫자·연산자 제거한 제목) 일치 검사.
6. (M-3) 본문 URL 추출 fallback + `resolution_source_origin`.
7. (L-1) https 강제.
8. `tests/test_review_6.py`로 위 전부 회귀 테스트.

## Residual risks

- 시리즈 식별은 여전히 자연어 키워드 기반이다. 거래소가 표현을 바꾸면 차단(fail-closed)되지만 승인되진 않는다.
- Polymarket 실업률 9건은 R5-H3(공식 발표 일정 기반 마감시각)가 구현되기 전까지 `close_time_verified=False`로 남는다. 다음 사이클.
- Kalshi 1500여 건은 구간 정보가 ticker에만 있어 제목 기반 그룹 검증에서 전부 거부된다. ticker 파싱과 누적 임계값 매핑(R5-H2 잔여)이 필요하다.
- 규칙 문서 원문은 해시만 저장하고 본문은 저장하지 않는다. 분쟁 시 재현을 위해 본문 스냅샷 보관을 검토해야 한다.
