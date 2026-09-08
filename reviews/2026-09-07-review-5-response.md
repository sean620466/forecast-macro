# 리뷰 5 응답 — 반영 내역

작성: Claude (2026-09-07부터 구현자 겸 검증자). ChatGPT는 리뷰 5 전달 직후 커밋 6개(`7937715`~`e449914`)를
`main`에 올린 뒤 참여를 중단했다. 이 문서는 그 커밋과 `claude/fix-review-5` 브랜치의 반영분을 함께 정리한다.
발견별 상태는 `reviews/FINDINGS.md`가 기준이다.

## 반영 완료

| ID | 반영 | 검증 |
| --- | --- | --- |
| R5-C2 | ridge 페널티를 데이터 경사와 함께 `n`으로 나눔 (`7937715`, ChatGPT) | 수정식을 독립 재구현해 Brier 0.067791 소수점 6자리 일치. 계수 절대값 최대 1.2 (수정 전 0.14) |
| R5-C1 | 워크포워드 보고서에 always-hold, 절편 전용 ablation, 비-ZLB 부분표본 지표 추가. `docs/WALK_FORWARD_MODEL.md` 해석 교체 | `tests/test_review_5.py`가 체크인 JSON을 재계산해 대조 |
| R5-M5 | `run_walk_forward_logistic`에 누락 스냅샷·정책금리 불일치 검사 추가. `forecast_at`을 `fed_backtest`와 같은 D-1 23:59 UTC로 통일 | `test_walk_forward_rejects_*` |
| R5-M6 | 위 C-1과 동일 커밋 | BSS vs always-hold +0.119, vs 절편 전용 +0.070 |
| R5-L1 | 인하 0건이면 `brier_skill_vs_always_hold=None` (`fed_backtest`, `fed_model_comparison`) | `test_always_hold_skill_is_none_without_cuts` (2022–2023 16회의) |
| R5-L3 | `ruff==0.16.6` 고정, 오류 4건 수정 (`70e035a`) | `ruff check .` 통과, CI 녹색 조건 |

## 부분 반영 (남은 범위)

| ID | 반영됨 | 남음 |
| --- | --- | --- |
| R5-H1 | `identify_contract_series`가 Core/YoY/NSA 키워드로 시리즈를 식별하고 모델 시리즈와 불일치 시 차단 (`2221e32`) | 키워드가 없으면 `headline`/`mom`/`sa`로 **기본값** 처리된다. 명시 키워드가 없는 계약은 `None`을 반환해 차단해야 fail-closed가 된다 |
| R5-H2 | Kalshi `cursor` 페이지네이션, 반복 커서 감지 (`859e5f1`) | KXFED "above X%" 누적 임계값 계약을 상호배타 구간 확률로 바꾸는 매핑. 현재 `_validate_group`은 이런 그룹을 거부한다 |
| R5-H3 | Polymarket `closes_at=None`, `close_time_verified=False` blocker (`45a26f4`) | BLS/Fed 공식 발표 일정(`America/New_York`)에서 `outcome_at`을 만드는 경로. 거래소 값과의 차이 검사 |

## 미반영

R5-M1 (본문 URL 추출), R5-M2 (`rules_version` 의미), R5-M3 (`review_market_candidates` 호스트 검사 우회),
R5-M4 (구간 정규식), R5-L2 (수수료 모델), R5-L4 (실업률 계수 부호). 다음 과제(`reviews/FIFTH_REVIEW_TASK.md`,
시장 규칙 검증)와 범위가 겹치므로 그 사이클에서 함께 다룬다.

## 수정 후 워크포워드 지표 (scheduled, n=39)

| 지표 | 값 |
| --- | ---: |
| 모델 Brier | 0.067791 |
| climatology / always-hold / 절편 전용 | 0.095612 / 0.076923 / 0.072898 |
| BSS vs climatology / always-hold / 절편 전용 | +0.291 / +0.119 / +0.070 |
| 비-ZLB 23건: 모델 / climatology / always-hold | 0.114932 / 0.122169 / 0.130435 |
| 비-ZLB BSS vs climatology | +0.059 |

`signal_eligible`은 여전히 `false`다. D-013(비-ZLB 30건)과 D-007(시장 baseline)은 충족되지 않았다.
