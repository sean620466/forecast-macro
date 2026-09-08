# Claude 독립 검토 보고서 #5 — 워크포워드 Fed 모델 및 예측시장 파이프라인

**대상**: `main` @ `47a83e2` (2026-09-07), 리뷰 #4 이후 추가된 커밋 `945b36f`~`47a83e2`
— `models/logistic.py`, `fed_model_comparison.py`, `docs/WALK_FORWARD_MODEL.md`,
`market_discovery.py`, `market_review.py`, `market_rules.py`, `data/kalshi.py`,
`data/polymarket.py`, `scripts/{discover,review,verify}_*.py`,
`data/generated/{fed_walk_forward_logistic_2019_2024,macro_market_candidates_2026-09-07,macro_market_review_2026-09-07}.json`

**검토자**: Claude (독립 검증자)

## Verdict

**PASS WITH CHANGES.** 안전장치는 유지된다: 모든 산출물에서 `signal_eligible=false`이고 시장 계약 승인 0건이다.
그러나 (1) 워크포워드 로지스틱 모델은 사실상 학습하지 않은 상수 모델이며 문서의 "climatology를 이긴다"는 해석은
D-011(ZLB 규칙)의 효과를 모델 skill로 오인한 것이고, (2) 시장 파이프라인은 계약이 정산하는 **시리즈의 정체성**
(Core vs headline, YoY vs MoM, SA vs NSA)을 검증하지 않으며, (3) Kalshi 탐색은 페이지네이션을 무시해 열려 있는
87개 Fed 계약을 하나도 찾지 못했고, (4) Polymarket `endDate`의 시간대가 신뢰할 수 없음이 실제 API로 확인됐다.

> 검토 방식: 이 Mac에는 Python 3.9만 있어 저장소 코드(3.11 전용 `datetime.UTC`, `StrEnum`)를 직접 실행할 수 없었다.
> 대신 모델식·옵티마이저·Brier·ECE를 저장소 import 없이 3.9로 재구현해 체크인된 JSON과 대조했고(전부 일치),
> Polymarket Gamma API와 Kalshi API를 읽기 전용으로 직접 조회해 어댑터 가정을 확인했다.
> `ruff 0.16.6`으로 `ruff check .`를 실행했다(2건 오류, L-3 참조). pytest는 실행하지 못했다.

## Scope

- 리뷰 #4의 권고가 반영됐는지 확인 (C-1 ZLB, H-1 클리핑, M-1/M-2 게이트 분리·always-hold)
- 워크포워드 로지스틱의 누출 여부, 수학, 해석
- 시장 탐색→구조 검토→규칙 검증 게이트의 fail-closed 여부와 계약 의미 일치(프로토콜 5, 7항)
- 시간대(D-009), 재현성(프로토콜 6항)

## Reproduction steps

```bash
# 독립 재계산 (Python 3.9 호환, 저장소 import 없음)
python3 reviews/2026-09-07-review-5-recalc.py    # baseline all/scheduled, walk-forward: JSON과 소수점 6자리 일치
# 공개 API 확인 (읽기 전용)
curl "https://gamma-api.polymarket.com/markets/3539692"   # resolutionSource == ""
curl "https://gamma-api.polymarket.com/markets/4217153"   # endDate 08:30Z vs 본문 "8:30 AM ET"
curl "https://external-api.kalshi.com/trade-api/v2/markets?limit=1000&status=open"   # 1000건, cursor 있음, 매크로 0건
curl "https://api.elections.kalshi.com/trade-api/v2/markets?status=open&series_ticker=KXFED"  # 87건
```

## Findings

| 등급 | # | 발견 | 파일 |
| --- | --- | --- | --- |
| **Critical** | C-1 | 워크포워드 로지스틱은 사실상 절편 전용 모델. 표준화 계수 절대값 전부 < 0.14. "절편+ZLB 마스크"만으로 Brier 0.0716 vs 전체 모델 0.0705. climatology 대비 개선분의 **94%가 ZLB 16행**에서 발생. 비-ZLB 23행에서 BSS는 +0.02. 실제 인하 3건 모두에서 모델 확률이 climatology보다 **낮았다**(2024-09-18: 0.070 vs 0.087). 문서의 "beats sequential climatology"는 D-011의 효과이지 학습된 skill이 아님 | `models/logistic.py`, `fed_model_comparison.py`, `docs/WALK_FORWARD_MODEL.md` |
| **Critical** | C-2 | 원인: `ridge_strength=1.0`이 **평균** 경사(`/sample_count`)에 더해지므로 합계 기준으로는 λ≈n(8~46). 단위분산 특징에 대해 계수를 0으로 강하게 수축시킴. 기본 설정에서 모델이 신호를 학습하는지 확인하는 테스트가 없음(`test_logistic_learns_ordered_signal`은 `ridge_strength=0.1`로만 검증) | `models/logistic.py`, `tests/test_logistic_model.py` |
| **High** | H-1 | 계약 시리즈 정체성 미검증. Polymarket 838712는 **Core CPI-U, NSA, 12개월, 소수 첫째자리 반올림**(BLS 본문 확인)이나 `TOPIC_TERMS["cpi"]`는 "cpi" 단어만 확인. 모델 특징은 headline `CPIAUCNS` YoY, CPI 모델은 headline MoM 구간. 이 상태에서 규칙이 통과되면 다른 시리즈를 비교하게 됨(프로토콜 5항 위반) | `market_rules.py`, `market_review.py` |
| **High** | H-2 | Kalshi 탐색이 첫 페이지 1000건만 읽고 `cursor`를 무시. 실측: 첫 페이지는 전부 스포츠, 매크로 0건. `series_ticker=KXFED`로 조회하면 열린 Fed 계약 87건. 결과적으로 체크인된 후보 파일에 Kalshi 0행 — 조용한 불완전성. 또한 KXFED는 "above X%" **누적 임계값** 계약이라 현재의 상호배타 구간 검증기(`_validate_group`)와 구조가 다름 | `data/kalshi.py`, `market_discovery.py`, `data/generated/macro_market_candidates_2026-09-07.json` |
| **High** | H-3 | 거래소 `endDate` 시간대 불신뢰. 4217153 `endDate="2026-10-02T08:30:00Z"`이나 본문은 "October 2, 2026, at 8:30 AM ET"(=12:30Z). ET 벽시계를 Z로 저장한 것. CPI 이벤트는 `03:59Z`(=전날 23:59 ET). `_timestamp`는 이를 UTC로 신뢰. D-009 위반이며 `PredictionContract.closes_at`/`observed_at` 검증이 4시간 어긋남 | `market_discovery.py`, `contracts.py` |
| **Medium** | M-1 | CPI 시장 10건 모두 `resolutionSource == ""` (실측). 본문에 BLS URL이 있으나 검증기는 필드만 봄 → 영구 차단. fail-closed는 맞지만 복구 경로가 없음 | `market_rules.py` |
| **Medium** | M-2 | `rules_version = updatedAt`은 규칙 버전이 아님. 두 시장 모두 탐색일(09-07) 다음날인 09-08로 갱신됨(유동성/가격 갱신에도 변함). 실제 버전은 `rules_text_hash`. 이름 변경 또는 문서화 필요 | `market_rules.py` |
| **Medium** | M-3 | `review_market_candidates`는 비어 있지 않은 문자열이면 승인(`test_complete_rules_allow_approval`은 `"BLS CPI release"`로 승인). 공식 호스트 검사는 `market_rules`에만 있어 직접 호출 시 우회 가능 | `market_review.py` |
| **Medium** | M-4 | 구간 정규식: `<2.0%`/`>2.9%`(엄격 부등호)를 `or less`/`or more`(포함)와 동일 취급. MoM/YoY/Core 구분 없음. 월(月)이 키에 없어 같은 이벤트에 두 달이 섞이면 "duplicate bucket"으로 잘못 거부. `between X and Y`는 미인식(그룹 전체 거부 — fail-closed라 허용) | `market_review.py` |
| **Medium** | M-5 | `run_walk_forward_logistic`에 `fed_backtest`에 있는 `policy_rate == upper_before` 검사와 누락 스냅샷 검사가 없음(KeyError로 실패). `forecast_at`이 회의일 00:00 ET로 `fed_backtest`의 D-1 23:59 UTC와 불일치 | `fed_model_comparison.py` |
| **Medium** | M-6 | 워크포워드 보고서에 리뷰 #4 M-2로 채택된 always-hold baseline이 없음. 계산 시 BSS vs always-hold = **+0.084**(climatology 대비 +0.263과 대비됨) | `fed_model_comparison.py`, `docs/WALK_FORWARD_MODEL.md` |
| **Low** | L-1 | 평가 구간에 인하가 0건이면 `1 - model/always_hold_brier`가 ZeroDivisionError | `fed_backtest.py` |
| **Low** | L-2 | `fee_schedule_id`가 `*-current-unknown` 자리표시자. D-003 8%p 임계값은 수수료 모델 없이는 재검토 불가 | `data/kalshi.py`, `data/polymarket.py` |
| **Low** | L-3 | `ruff>=0.6,<1` 미고정. ruff 0.16.6에서 `BLE001`(scripts/verify_market_rules.py:40), `UP035`(market_review.py:7) 2건 실패. CI가 ruff 버전에 따라 깨질 수 있음 | `pyproject.toml` |
| **Low** | L-4 | 계수 부호: 실업률 계수가 음(높은 실업률 → 낮은 인하 확률), CPI 계수도 음. 크기가 작아 영향은 없으나 C-2 수정 후 반드시 재점검 | `fed_model_comparison.py` |

## Independent calculations

### 재현 (JSON과 전부 일치)

| 항목 | n | 모델 Brier | climatology | ECE | 예측별 불일치 |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline all | 41 | 0.077271 | 0.127604 | 0.022014 | 0/41 |
| baseline scheduled | 39 | 0.049031 | 0.095612 | 0.038468 | 0/39 |
| walk-forward scheduled | 39 | 0.070480 | 0.095612 | 0.028364 | — |

### C-1 분해 (walk-forward, scheduled, n=39)

| 비교 | Brier | BSS |
| --- | ---: | ---: |
| 전체 모델 | 0.070480 | vs clim +0.263 / vs always-hold **+0.084** |
| 절편 전용 + ZLB 마스크 | 0.071593 | vs clim +0.251 |
| always-hold (p=0) | 0.076923 | — |
| **비-ZLB 23행만**: 모델 / clim / always-hold | 0.1195 / 0.1222 / 0.1304 | vs clim **+0.022** |
| ZLB 16행 오차제곱합: 모델 / clim | 0.0004 / 0.9190 | 개선분 0.98 중 0.92 = **94%** |

인하 3건에서의 모델 확률: 0.070, 0.095, 0.117 (climatology 0.087, 0.106, 0.125). 세 번 모두 모델이 baseline보다 낮았다.

### H-2 실측

`external-api.kalshi.com/.../markets?limit=1000&status=open` → 1000건, `cursor` 비어있지 않음, 매크로 키워드 0건.
`series_ticker=KXFED` → 87건(예: `KXFED-27APR-T4.25`, close 2027-04-28T17:55Z). 탐색기가 두 번째 페이지를 요청하지 않는다.

## Required changes (우선순위순)

1. **(C-1, C-2, M-6)** `docs/WALK_FORWARD_MODEL.md`의 해석을 "절편 전용 모델과 구별 불가; 개선분은 D-011"로 교체. 보고서에
   `always_hold_brier`, `brier_skill_vs_always_hold`, `intercept_only_brier`(ablation), 비-ZLB 부분표본 Brier를 추가.
   `ridge_strength`를 표본당 스케일(예: `λ/n`) 또는 별도 개발 구간(2008 이전 등)의 중첩 검증으로 결정.
   기본 설정에서 알려진 계수를 복원하는 테스트 추가.
2. **(H-1)** `ContractRuleMetadata`에 `series_id`(예: `CPILFENS`), `transform`(yoy/mom), `seasonal_adjustment`, `rounding`을
   추가하고 이벤트별 매핑 테이블을 **승인 전제조건**으로 둠. 규칙 본문에서 "excluding food and energy", "before seasonal adjustment"
   같은 문구를 파싱해 매핑과 대조.
3. **(H-3)** 거래소 `endDate`를 신뢰하지 않고 BLS/Fed 공식 발표 일정(`America/New_York`)에서 `outcome_at`을 생성.
   거래소 값과 1시간 이상 차이 나면 blocker. D-009에 "거래소 타임스탬프는 참고용" 항목 추가 제안.
4. **(H-2)** Kalshi 탐색에 `cursor` 페이지네이션 추가, 또는 `series_ticker`(KXFED, KXCPI 등) 명시 조회. 누적 임계값 계약을
   구간 확률로 변환하는 별도 매핑(인접 임계값 차분) 구현. 후보 파일에 거래소별 페이지 수·총 건수 메타데이터 기록.
5. **(M-1)** 본문에서 허용 호스트 URL을 추출하는 경로 추가(해시에 포함). 여전히 fail-closed.
6. **(M-3)** 공식 호스트 검증을 `review_market_candidates` 안으로 이동하거나 `ContractRuleMetadata` 생성을 `verified_rule_metadata`로만 허용.
7. **(M-4)** 엄격/포함 부등호 구분, 월·시리즈를 그룹 키에 포함, "between" 패턴 지원.
8. **(M-5, L-1)** `fed_model_comparison`에 `fed_backtest`와 동일한 입력 검증 추가, `forecast_at` 규칙 통일, 0 나눗셈 방어.
9. **(L-3)** `ruff==0.x.y`로 고정하거나 `[tool.ruff.lint]`에서 규칙 집합을 명시.

## Residual risks

- pytest를 이 환경에서 실행하지 못했다. CI(`python 3.11`)의 최신 실행 결과를 별도로 확인해야 한다.
- 시장 파이프라인은 아직 **가격을 한 번도 가져오지 않았다**. D-007이 요구하는 시장 baseline 대비 성능은 여전히 계산 불가.
- 2019–2024 표본에서 실제 인하는 정기회의 기준 3건(모두 2024년)뿐이다. 어떤 옵티마이저 설정을 쓰더라도 이 표본으로
  "인하 예측 skill"을 주장할 수 없다. 표본 확장(2008년 이전 단일 목표금리 체계 분리 포함)이 모델 개선보다 선행돼야 한다.
- Polymarket Gamma의 `resolutionSource`, `endDate` 의미는 문서화되어 있지 않다. 이번 실측은 2026-09-07 시점의 두 시장에 한정된다.
