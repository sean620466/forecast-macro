# 발견사항 장부

규칙은 `docs/COLLABORATION.md` 참조. ID는 `R<리뷰>-<등급><순번>`. 상태: open / fixed / partial / rejected / superseded.
리뷰 1~3의 `fixed` 항목은 ChatGPT 응답 파일 기준이며 이 장부에는 미해결·부분해결 항목만 옮겼다.
2026-09-07부터 ChatGPT 참여가 중단되어 Claude가 구현과 검토를 모두 맡는다(`docs/COLLABORATION.md` 참조).

## 리뷰 1 — Fed/CPI baseline (`2026-09-07-fed-cpi-baseline-claude.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R1-H3 | High | 예측시장 계약별 outcome bucket 확장 | fixed | D-016(과제 24·25): cut/hold/hike 3원 결과공간, 시장 사다리도 3원으로 읽음. `FedOutcome` 4구간은 미사용 |
| R1-H4 | High | CPI `forecast_mom` 산출(nowcast) 코드 부재 | fixed | 과제 42: `models/cpi.py`(외부 nowcast에 정규분포 래퍼) 삭제. CPI는 경험분포·기저효과 baseline(과제 35·41)으로 대체 |
| R1-M3 | Medium | CPI 불확실성 σ를 역사적 오차로 추정 | fixed | 과제 42: σ 고정 래퍼 삭제로 소멸. 현재 CPI baseline은 경험분포라 σ가 없음 |
| R1-M4 | Medium | YES/NO 호가·수수료 정규화 | fixed | 어댑터 bid/ask + claude/task-19 수수료 모델(`fees.py`) |
| R1-X1 | Medium | 실제 발표 timestamp 테이블(ALFRED real-time date와 별개) | partial | claude/task-27: 최초 발표 **일자**는 스냅샷에 기록. 시각(08:30 ET 등)은 `data/release_schedule.csv`의 시리즈별 규칙과 결합해야 함(R4-M4 결정 대기) |

## 리뷰 2 — 백테스트 기반 (`2026-09-07-backtest-claude-review-2.md`)

응답 기준 전 항목 `fixed`. 이후 리뷰에서 재발한 항목 없음.

## 리뷰 3 — 변환·계약 (`2026-09-07-contracts-claude-review-3.md`)

응답 기준 전 항목 `fixed`. 단 timezone 규칙(D-009)은 R5-H3에서 거래소 데이터에 대해 재발.

## 리뷰 4 — 확장 백테스트 (`2026-09-07-extended-backtest-claude-review-4.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R4-C1 | Critical | ZLB 제약 부재 | fixed | `945b36f`, D-011 |
| R4-H1 | High | 확률 정확히 0/1 반환 | fixed | `945b36f`, `PROBABILITY_EPSILON` |
| R4-H2 | High | `window` 스코프(정기회의 간 창 라벨) | fixed | claude/task-10: `window_meetings`. 2020-04-29 창은 예측 cutoff 전에 결정돼 `dropped_predetermined_windows`로 보고·제외 |
| R4-M1 | Medium | `signal_eligible` 의미 분리 | fixed | `945b36f`, D-012 |
| R4-M2 | Medium | always-hold baseline | fixed | `fed_backtest`(945b36f) 및 워크포워드(claude/fix-review-5) 모두 보고 |
| R4-M3 | Medium | 스냅샷 재현성 메타데이터(`fetched_at`, 관측월, `realtime_start`, 모델 버전) | fixed | claude/task-23: 각 스냅샷에 입력 5개의 `observed_at`·`realtime_start`·`fetched_at`·값, `builder_version`, `built_at`, `build_commit`(GITHUB_SHA). 빌드 워크플로가 2019–2026 파일을 재생성해 커밋 |
| R4-M4 | Medium | forecast cutoff = 시장 관측시각 정렬 규칙 | fixed | D-017 (2026-09-08 승인). 실시간 기록에 `same_day_release`(일정표 기준), 스냅샷에 다음 발표일 조회 기반 플래그, 채점에 clean 부분집합·같은 날 발표 집계 |
| R4-L1 | Low | CSV `source`를 결정별 보도자료 URL로 | fixed | claude/task-10: 49행 전부 교체(HTTP 200 확인), 로더가 패턴 강제 |
| R4-L2 | Low | scheduled 스코프 연속성 검증 | fixed | claude/task-10: `validate_continuity`, 스크립트는 `--allow-rate-gaps` 없이는 거부 |
| R4-L3 | Low | `forecast_at` 인위적 시각 문서화 | fixed | 과제 44: `docs/WALK_FORWARD_MODEL.md`에 `forecast_at`(vintage 날짜 23:59 UTC, 누출 검사용 인위적 시각) 문서화 |
| R4-L4 | Low | 테스트 공백(ZLB, JSON 회귀, 확률 0/1 금지, 연속성) | fixed | claude/task-10: all/window JSON 회귀, 연속성, 출처 패턴 테스트 |

## 리뷰 5 — 워크포워드 모델·시장 파이프라인 (`2026-09-07-walk-forward-market-pipeline-claude-review-5.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R5-C1 | Critical | 워크포워드 로지스틱이 사실상 절편 전용. 개선분 94%가 ZLB 규칙 | fixed | ridge 수정 후 재검산(claude/fix-review-5). 절편 전용·비-ZLB 분해를 보고서와 문서에 추가. 비-ZLB BSS +0.06 |
| R5-C2 | Critical | `ridge_strength`가 평균 경사 스케일에 적용돼 λ≈n. 기본 설정 학습 테스트 없음 | fixed | 7937715 (ChatGPT). 수정 후 Brier 0.067791 독립 재계산 일치 |
| R5-H1 | High | 계약 시리즈 정체성(Core/headline, YoY/MoM, SA/NSA) 미검증 | fixed | 2221e32 (ChatGPT) + claude/review-6: 명시 근거 없으면 `None`, 식별 불가는 항상 blocker (R6-H1) |
| R5-H2 | High | Kalshi 탐색 `cursor` 무시. 열린 KXFED 87건 누락 | fixed | 859e5f1 (ChatGPT) 페이지네이션 + claude/task-12: 사다리 검증(`_validate_ladder`), `normalize_threshold_ladder`, Kalshi 규칙·호가 어댑터. 2026-09-08 실측 KXFED 6개 이벤트 96건 승인, 9월·10월 가격 스냅샷 성공 |
| R5-H3 | High | Polymarket `endDate` 시간대 불신뢰(ET를 Z로 표기) | fixed | 45a26f4 + claude/task-07: `release_schedule.py`가 공식 일정(BLS/Fed, `America/New_York`)에서 `outcome_at`을 만들고 거래소 마감이 발표 이후면 거부. `data/release_schedule.csv`에 출처·수집시각 기록 |
| R5-M1 | Medium | `resolutionSource` 빈 값으로 CPI 시장 영구 차단 | fixed | claude/review-6: 본문에서 공식 호스트 URL 추출, `resolution_source_origin` 기록 (R6-M3). 실측 CPI 10건 출처 확보, 시리즈 불일치로만 차단 |
| R5-M2 | Medium | `rules_version=updatedAt`은 규칙 버전이 아님 | fixed | claude/review-6: 내용 해시 기반 버전, `venue_updated_at`·`fetched_at` 분리 (R6-H3) |
| R5-M3 | Medium | `review_market_candidates`가 비어있지 않은 문자열이면 승인 | fixed | claude/review-6: `official_sources.py` 공유, 리뷰 단계에서 호스트 검사 (R6-H2) |
| R5-M4 | Medium | 구간 정규식: 엄격 부등호, MoM/YoY, 월 미구분 | fixed | claude/review-6: 엄격 부등호 blocker, 그룹 subject 일치 검사 (R6-M2) |
| R5-M5 | Medium | 워크포워드에 입력 검증 없음, `forecast_at` 불일치 | fixed | claude/fix-review-5 |
| R5-M6 | Medium | 워크포워드 보고서에 always-hold 없음(BSS +0.084) | fixed | claude/fix-review-5. 수정 후 BSS vs always-hold +0.119 |
| R5-L1 | Low | 인하 0건이면 always-hold BSS 0 나눗셈 | fixed | claude/fix-review-5. `None` 반환 |
| R5-L2 | Low | `fee_schedule_id` 자리표시자, 수수료 모델 부재 | fixed | claude/task-19: `fees.py`. Polymarket Economics 0.05·p·(1−p)(공식 문서 확인), Kalshi `quadratic_with_maker_fees` x1(시리즈 API 확인, 상수 0.07/0.0175는 미검증) |
| R5-L3 | Low | ruff 버전 미고정, 0.16.6에서 2건 실패 | fixed | 70e035a. `ruff==0.16.6` 고정 |
| R5-L4 | Low | 계수 부호 비경제적(실업률 음) | fixed | 과제 43: 원인은 ZLB 회의를 '인하 없음' 행으로 학습에 넣은 것(2020–21 실업률 14.7%에 인하 불가). 실행 가능 회의(비-ZLB)만으로 학습하면 실업률 계수가 2019–2026 −0.58→+0.52, 2015–2026 −0.46→−0.13(≈0). `fit_cut_model`, 실시간 `fed-live-0.4` |
| R5-X1 | Medium | `discover-markets` 워크플로가 GitHub 러너에서 탐색 단계 실패(로컬은 성공). 원인 로그 미확인 | fixed | 탐색 워크플로가 2026-09-08 기준 연속 성공(#20~#26). 원인은 Kalshi 429·User-Agent, 재시도 도입으로 해결 |
| R5-X2 | Medium | Kalshi 페이지네이션 후 후보 1692건 중 브라질/ECB 등 해외 및 "Fed posts on X" 같은 비통계 계약 포함 | fixed | claude/fix-discovery-ci: 해외 지역·비통계 패턴 확장, `federal funds` 인식 추가. 1576건으로 감소. 구간 정보가 제목이 아닌 ticker에 있어 Kalshi 그룹 검증은 여전히 전부 거부됨(R5-H2 잔여) |

## 리뷰 6 — 시장 규칙 검증 게이트 (`2026-09-08-market-rules-claude-review-6.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R6-H1 | High | 시리즈 식별 기본값이 모델 시리즈와 일치(fail-open) | fixed | 같은 브랜치. 근거 없으면 `None` + blocker |
| R6-H2 | High | `review_market_candidates`가 출처 호스트 미검사 | fixed | 같은 브랜치. `official_sources.is_official_source` |
| R6-H3 | High | 해시에 `updatedAt` 포함 → 규칙 불변에도 해시 변동, `fetched_at` 없음 | fixed | 같은 브랜치 |
| R6-M1 | Medium | 시장/이벤트 수준 필드 혼합 | fixed | 같은 브랜치. `rules_source_level` |
| R6-M2 | Medium | 엄격 부등호·월·시리즈 혼합 미감지 | fixed | 같은 브랜치 |
| R6-M3 | Medium | 본문 URL 미활용으로 CPI 영구 차단 | fixed | 같은 브랜치 |
| R6-L1 | Low | http 평문 출처 통과 | fixed | 같은 브랜치. https 강제 |
| R6-L2 | Low | `MODEL_SERIES["cpi"]`가 어느 모델 기준인지 불명확 | fixed | claude/task-10: 스크립트 주석으로 명시 |
| R6-X1 | Medium | 실업률 9건은 규칙 검증 전부 통과, `close_time_verified=False`만 남음 | fixed | claude/task-07: 2026-09-08 실측에서 실업률 9건 `approved`, CPI 10건은 시리즈 불일치로 차단 유지 |

## 과제 07 — 공식 발표 일정 (`reviews/tasks/07-release-schedule.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R7-H1 | High | `verify_market_rules.py`/`review_macro_markets.py`가 `signal_eligible = approved > 0`으로 기록. 계약 승인과 D-007 신호 자격을 혼동 | fixed | 같은 브랜치. `approved_contracts` 카운트로 분리, `signal_eligible`은 항상 `false` + 이유 |
| R7-M1 | Medium | BLS가 스크립트 요청(HTML·ICS 모두)을 403으로 거부해 일정 자동 갱신 불가 | partial | 브라우저로 읽어 CSV에 수동 전사(`docs/RELEASE_SCHEDULE.md`). 과제 44: 매일 워크플로 첫 단계가 시리즈별 남은 일정 45일 미만이면 실패해 이슈로 알림. 자동 수집은 여전히 불가 |
| R7-M2 | Medium | Polymarket `endDate`가 ET 벽시계인지 UTC인지 확정 불가. 현재는 "발표 이전이면 그대로 채택"(보수적) | fixed | D-014(과제 22): 결과 확정 시각을 거래소 `endDate`가 아니라 공식 발표 일정에서 생성. 거래소 값은 `venue_close_raw`로 기록만 |

## 과제 08 — 가격 스냅샷 (`reviews/tasks/08-price-snapshots.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R8-M1 | Medium | 실업률 9구간 mid 합계 1.14 (overround 14%) → D-010 허용 5% 초과로 스냅샷 거부. bid 합 0.995, ask 합 1.285. 꼬리 구간 스프레드(0.01/0.05)가 mid 합을 부풀림 | fixed | D-015 (2026-09-08 승인). `normalize_bucket_quotes`: 완전성 `Σbid ≤ 1 ≤ Σask`, 폭 ≤ 0.35, 확률을 `[bid, ask]` 범위와 함께 기록. 실측 첫 스냅샷 성공 |
| R8-L1 | Low | `fee_schedule_id`가 여전히 `polymarket-current-unknown`. Polymarket은 현재 무수수료 시장이 많으나 계약별 확인 필요 | fixed | claude/task-19: Economics 카테고리 taker 0.05 (docs.polymarket.com/…/fees, 2026-09-08). 지정학 시장만 무수수료 |
| R8-L2 | Low | 스냅샷은 워크플로 아티팩트(14일 보관)에만 남음. D-007 baseline 축적을 위해 저장소 또는 외부 저장 필요 | fixed | claude/task-11: 워크플로가 `data/generated/market_prices/`에 스냅샷을 추가 커밋(`[skip ci]`, 봇 계정). 최신 리뷰·탐색 상태도 `*_latest.json`으로 보존 |

## 과제 09 — D-015 정규화 (`reviews/tasks/09-overround-normalization.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R9-L1 | Low | `normalize_outcome_prices`(D-010 mid 규칙)는 코드에 남아 있으나 파이프라인에서 더는 쓰지 않음 | fixed | claude/task-21: docstring에 legacy 표시 |
| R9-L2 | Low | 점추정의 스프레드 비례 배분은 결정으로 고정했으나, 대안(bid 기준, 유동성 가중)과의 비교는 시장 데이터가 쌓인 뒤 가능 | open | 스냅샷에 bid·ask·mid 합을 모두 저장하므로 사후 재계산 가능 |

## 과제 12 — Kalshi 누적 임계값 사다리 (`R5-H2` 잔여)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R12-M1 | Medium | KXFED 2026-12, 2027-01/03/04 이벤트는 승인됐으나 꼬리 rung 스프레드가 0.10을 넘어 가격 거부 | fixed | claude/task-20: rung별 스프레드 거부를 없애고 `wide_rungs` 기록 + D-015 폭 게이트(Σask−Σbid ≤ 0.35)·단조성으로 판정. 단조성은 호가 범위로 판정. D-018 (2026-09-08 승인): 폭 상한을 만기까지 개월 수에 따라 최대 0.60까지 완화, 0.35 초과는 `low_liquidity` 표시 후 채점에서 분리 |
| R12-M2 | Medium | Kalshi 규칙의 출처는 URL이 아닌 문구("Federal Reserve's official website")로 기재. 정확 문구 3개만 매핑, 기원 `rules_text_reference`가 아닌 `field`로 기록됨 | fixed | claude/task-21: `resolution_source_kind=text_reference` → 기원 `rules_text_reference` |
| R12-L1 | Low | KXFEDFUNDSYEAR(연말 금리), KXEFFR(실효금리) 이벤트는 구조는 통과했으나 발표 일정이 없어 `close_time` 미검증 | fixed | claude/task-24: 연말 계약은 규칙의 "in effect at 11:59 PM ET on December 31, YYYY"를 결과 시각으로 사용(일정 불필요). EFFR은 `effective_federal_funds_rate` 시리즈로 식별돼 모델 시리즈 불일치로 차단(의도) |
| R12-L2 | Low | 봇이 커밋하던 `macro_market_review_latest.json`이 38,960줄 | fixed | 같은 브랜치: 요약과 승인 행만 커밋 |

## 과제 13 — 실시간 모델 vs 시장 기록 (`reviews/2026-09-08-task-13-response.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R13-M1 | Medium | 실시간 비교의 모델 확률은 2019–2024 전체로 학습한 로지스틱 + 휴리스틱. D-013(비-ZLB 30건) 미충족 상태의 모델이므로 기록 전용 | fixed | 과제 18·19·35·40: `score_*_comparisons.py`가 결과 확정 후 시장 대비 Brier를 누적. 학습 표본은 2015–2026(과제 39) |
| R13-M2 | Medium | 실시간 특징의 vintage는 "오늘"이며 발표 시각(08:30 ET)과 워크플로 실행 시각(13:40 UTC = 09:40 ET) 사이 관계는 ALFRED `realtime_start`에 의존 | fixed | 과제 42: 구간 비교 기록에 `inputs_current`(최신 입력 월 == 기준월−1) 추가. False면 채점의 최종 기록 후보에서 제외하고 `stale_input_records`로 집계 |
| R13-L1 | Low | 시장 P(cut)은 최신 **가격 성공** 스냅샷에서 읽음. 스냅샷이 6시간 주기라 모델 계산 시각과 최대 6시간 차이 | fixed | 과제 42: 탐색·가격 스냅샷 워크플로를 평일 13:17 UTC에도 실행해 13:40 UTC 비교가 23분 이내의 호가를 씀. 기록의 `market_observed_at`/`as_of`로 검증 가능 |

## 과제 14 — FOMC 2025–2026 확장 및 실시간 비교 첫 실행 (`reviews/tasks/14-comparison-scoring.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R14-H1 | High | 실시간 비교 첫 실행 실패: ALFRED가 `vintage_dates=2026-09-08`(UTC 날짜, 미국 시각으로는 전날 저녁)에 HTTP 500 | fixed | task-14: ET 날짜 → 재발(04:05 UTC = 23:05 CT). claude/task-25: FRED 시계는 **America/Chicago**. `latest_safe_vintage` + 500이면 하루 후퇴(`build_feature_snapshot_with_fallback`) |
| R14-H2 | High | 과제 12 응답이 Kalshi 9월 사다리를 "인하 0.47"로 해석했으나 현재 상단은 3.75%(2025-12-10 이후). 실제 의미는 동결 0.47 / 인상 0.51 | fixed | 응답 문서 정정. 코드(`market_cut_probability`)는 DFEDTARU 실측값을 쓰므로 영향 없음 |
| R14-M1 | Medium | 학습 데이터가 2024-12까지라 2025년 인하 3회와 2026년 동결 5회가 모델에 없음 | fixed | CSV 13행 + 봇 커밋 스냅샷 62건(`21852bf`). 실시간 비교와 백테스트 모두 2019–2026 사용 |
| R14-H3 | High | 2025-10 CPI·실업률이 BLS 셧다운으로 미발표(FRED `.`). 13개월 연속성 검사가 2025-11 이후 모든 스냅샷과 실시간 비교를 거부 | fixed | claude/task-14b: 변화율은 양 끝 달만 요구, 중간 미발표 달은 `data_gaps`에 기록. 2019–2024 회귀 테스트로 기존 값 불변 확인 |
| R14-M2 | Medium | 첫 실시간 비교(2026-09-08 02:57Z): 모델 P(cut) 휴리스틱 0.157 / 로지스틱 0.144 vs 시장 0.005. 시장은 인상 0.525를 보는데 모델에는 "인상" 결과가 없음(cut vs hold_or_hike 이진) | fixed | D-016으로 해소: 모델이 인상 확률을 냄(2026-09-08 로지스틱 인상 18.6% vs 시장 53.5%) |
| R14-L1 | Low | 채점 스크립트는 회의 결정 전 마지막 기록만 사용하고 미래 회의는 제외. 아직 채점 가능한 회의 0건 | fixed | `comparison_scoring.py`, 워크플로가 매일 `fed_market_scoring.json` 갱신 |

## 과제 15 — 2019–2026 백테스트 재실행

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R15-M1 | Medium | 워크포워드 비-ZLB 36건으로 D-013 표본 기준 첫 충족. 그러나 비-ZLB BSS vs climatology는 +0.026, 절편 전용 대비 +0.06 | open | 특징이 거의 기여하지 않음. 3원 결과공간(cut/hold/hike)과 추가 특징(시장 금리 기대, 임금 등)을 검토할 것. 실시간 채점과 혼동 금지 |
| R15-L1 | Low | 2026-06 CPI YoY 4.25% 등 2026 인플레이션 재가속 구간에서 휴리스틱 P(cut)이 0.09까지 하락하고 모델은 인상 가능성을 표현 못 함 | fixed | R14-M2와 함께 D-016으로 해소 |

## 과제 16 — D-016 3원 결과공간

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R16-M1 | Medium | 휴리스틱의 인상 점수(인하 점수의 부호 반전)는 3원 Brier 0.69로 3원 climatology(0.53~0.59)보다 **나쁨**. 인상 Brier 0.24~0.28 | fixed | 과제 46: 부호 반전 점수 제거. 동결·인상 분할을 과거 비인하 회의의 인상 빈도(Laplace)로 대체. 3원 Brier window 2019–2026 0.688→0.497(climatology 0.532), 2015–2026 0.659→0.545(0.509). 인하 성분 불변 |
| R16-L1 | Low | 로지스틱 조건부 인상 모델은 3원 Brier 0.34~0.35 vs climatology 0.53~0.56, 인상 Brier 0.09~0.11. 2022–2023 인상 국면이 인플레이션으로 학습됨 | open | 표본외이나 인상 사이클 1개뿐. 과대해석 금지 |
| R16-L2 | Low | 채점(`comparison_scoring`)은 아직 cut 성분만 채점 | fixed | claude/task-16b: 벡터가 있는 기록은 3원 Brier와 시장 대비 3원 skill도 채점. 벡터 없는 옛 기록은 cut만 |

## 과제 17 — 실업률 구간 baseline (경험적 1개월 변화 분포)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R17-M1 | Medium | 실업률 baseline은 "최신치 + 과거 1개월 변화의 경험분포"(1990~, ALFRED 당일 vintage). 추세·계절·고용지표를 전혀 쓰지 않는 climatology급 모델 | open | 의도된 무조정 baseline(D-005). 시장 대비 채점이 쌓인 뒤 조건부 모델 검토 |
| R17-M2 | Medium | 시장 계약은 "9월 실업률"인데 최신 발표는 8월치(9/4 발표). 예측 지평은 정확히 1개월이며, 발표일(10/2) 전 마지막 기록만 채점 대상이어야 함 | fixed | claude/task-18: `unemployment_scoring.py`. 발표일 vintage의 ALFRED 값(최초 발표치)을 라벨로, 다중 구간 Brier와 시장 대비 skill. 워크플로가 매일 갱신 |
| R17-L1 | Low | 2025-10 미발표로 그 달을 걸친 변화 2건이 분포에서 빠짐. 2020년 +10.4/−2.2 같은 극단값은 빈도대로 포함 | open | 꼬리 구간 확률에 ~0.5% 기여. 기록만 |

## 과제 19 — 수수료 모델 (D-003 net edge)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R19-M1 | Medium | Kalshi 수수료 상수(taker 0.07, maker 0.0175)는 공식 PDF(`kalshi-fee-schedule.pdf`)를 이 저장소에서 다시 읽지 못해 `verified=false` | fixed | 사용자가 2026-09-08 PDF(2026-07-07 시행)를 확인. 상수는 맞았고, 반올림은 센트가 아니라 **센티센트(0.0001달러) 올림**이어서 수정. `verified=true` |
| R19-M2 | Medium | Kalshi 사다리에서 파생된 배타 구간은 계약 두 개(인접 rung)로 만들어지므로 수수료가 두 번 든다. 현재 기록은 rung별 수수료만 | fixed | claude/task-20: `bucket_fees`에 두 leg 수수료 합 기록(9월 4.00% 구간 0.03). Kalshi 상수 미검증(R19-M1)은 그대로 |
| R19-L1 | Low | 실업률 비교 기록에 `net_edge_after_fees`(모델 확률 − ask − 수수료) 추가. 9개 구간 모두 YES 직접 계약 | fixed | 같은 브랜치 |

## 과제 23~25 — 재현성 메타데이터·연말 계약·FRED 시계

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R23-L1 | Low | 스냅샷 `inputs[*].realtime_start`는 요청한 vintage 날짜와 같게 나온다(ALFRED가 단일 `vintage_dates`로 조회하면 그 vintage 기준 real-time 시작을 돌려줌). 즉 "그 시점에 보였던 값"의 증거이지 **최초 발표일**이 아님 | fixed | claude/task-27: `AlfredClient.first_release_date`(전체 vintage 이력)로 최신 입력 3개에 `first_published_on` 기록. 빌드 워크플로 `--first-release-dates`. 데이터가 같으면 재빌드 커밋 생략 |
| R25-L1 | Low | 실시간 워크플로가 push로 미국 심야에 실행되면 FRED 시계(Chicago) 기준 "내일" vintage를 요청해 500 | fixed | `latest_safe_vintage`(Chicago 날짜) + 500 시 하루 후퇴. 정기 실행(13:40 UTC)은 영향 없음 |

## 과제 30 — D-017·D-018 구현

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R30-L1 | Low | 스냅샷의 `same_day_release`는 빌드 워크플로가 `--first-release-dates`로 다음 달 발표일을 조회해야 채워짐. 2019–2024 고정 파일에는 없음(`null`) | fixed | 재생성 완료(`5f30c0a`): 회의 당일 CPI 발표 3건(2019-12-11, 2020-06-10, 2024-06-12). 평가 구간 내 2건 제외 시 Brier 변화 0.002 이내 |
| R30-L2 | Low | D-018 완화 후에도 폭이 상한을 넘는 사다리는 여전히 거부 | fixed | 04:30Z 스냅샷: 12월 FOMC 사다리 폭 0.36 ≤ 상한 0.40으로 **첫 가격**(low_liquidity). 2027년 1/3/4월은 0.60도 초과해 거부 유지 |

## 과제 34–35 — 2015년까지 역사 확장, Core CPI 모델

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R34-L1 | Low | 2015–2018 FOMC 32건 추가(인상 9회). 보도자료 문장에서 상단 금리를 자동 추출해 대조. 2015년 1~10월은 "0 to 1/4 percent" 문구로 ZLB 확인 | fixed | `data/fomc_meetings_2015_2026.csv` (94회의). 스냅샷은 빌드 워크플로가 생성 |
| R35-M1 | Medium | Core CPI 모델은 "최신 YoY + YoY의 1개월 변화 경험분포"로, 실업률 baseline과 같은 무조정 구조. CPI YoY는 기저효과(12개월 전 지수)에 크게 좌우되므로 경험분포보다 단순한 구조가 존재함(기저효과 계산) | fixed | 과제 41 백테스트(2000–2026, 317개월): Core는 경험분포 Brier 0.803 vs 기저효과 0.841(기저효과 skill −4.8%), 헤드라인은 0.889 vs 0.813(+8.5%). Core는 그대로, 헤드라인은 기저효과 모델로 교체 |
| R35-L1 | Low | 규칙 검증의 모델 시리즈가 토픽당 여러 개(`core_cpi_yoy_nsa`, `headline_cpi_mom_sa`). 계약이 그중 하나면 통과 | fixed | Polymarket 838712 (Core CPI YoY 8월) 10건 승인 예상 |
| R37-M1 | Medium | 94회의 스냅샷 빌드(#12)가 11분 뒤 유효한 과거 vintage(2022-01-25)에 대한 FRED 일시적 500 한 번으로 중단. ALFRED 클라이언트는 429만 재시도했음 | fixed | 5xx·전송 오류(타임아웃)도 지수 백오프로 재시도(마지막 시도의 응답은 그대로 반환해 "내일 vintage" 500 폴백 유지). 빌드 스크립트는 회의마다 체크포인트 저장, `--resume` 지원 |
| R38-L1 | Low | 워크플로 실패나 첫 채점 결과를 사람이 알 방법이 없었음(Actions 페이지를 직접 봐야 함) | fixed | `alerts.yml`: 예약 워크플로 실패 시 `workflow-failure` 이슈 생성·갱신, 재성공 시 자동 닫힘. `scripts/scoring_alerts.py`: 커밋된 채점 파일 대비 새로 채점된 회의·발표가 있으면 `scoring` 이슈 1건(수치 포함). 이슈는 알림일 뿐 `signal_eligible`과 무관 |
| R39-H1 | High | 2019–2026에서 보고한 로지스틱 skill(climatology 대비 BSS +0.17, 비-ZLB +0.03)이 2015–2026(94회의)로 표본을 늘리면 +0.02 / +0.007로 사라짐. 같은 2020–2026 회의 52건에서도 2015년부터 학습한 모델이 더 나쁨(인하 Brier 0.1032 vs 0.0981, 3원 0.421 vs 0.353). 휴리스틱은 climatology보다 못함(BSS −0.12, 게이트 실패) | open | 실시간 학습은 94회의로 전환(`fed-live-0.3`; 결과를 보고 표본을 고르지 않음). 워크포워드 보고서에 회의별 `predictions` 추가. D-013은 숫자상 통과하나 여유가 없음. 다음: 특징 재검토(기저효과·금리 수준 상호작용)는 채점 데이터가 쌓인 뒤 별도 과제로 |
| R40-L1 | Low | D-019 구현 후 실측(2026-09-08 17:03 UTC 스냅샷 재계산): KXU3-26SEP(평균 0.036/최대 0.07), KXCPIYOY-26AUG(0.015/0.07), KXFED 9·10·12월은 통과. KXCPICOREYOY-26AUG는 평균 0.034로 좁지만 꼬리 rung 하나가 0.15라 최대 한도 0.12에 걸려 거부. KXU3-26OCT는 평균 0.052로 0.002 초과 | open | 꼬리 rung(mid ≤ 0.02 또는 ≥ 0.98)을 최대 스프레드 판정에서 제외할지는 별도 제안(D-020 후보). 현재는 승인된 규칙 그대로 적용 |
| R40-L2 | Low | 실업률·CPI 비교가 Polymarket 한 곳만 기록했음. 채점 키가 기준월뿐이라 두 장소를 넣으면 한쪽이 덮어써졌음 | fixed | 장소별 비교 파일(`*_kalshi.json`)과 (기준월, 장소) 키 채점, 알림도 장소별. 헤드라인 CPI YoY(CPIAUCNS)는 Kalshi KXCPIYOY 대상으로 같은 machinery로 추가 |
| R41-L1 | Low | R35-M1 후속: 기저효과를 명시한 CPI YoY baseline(`models/cpi_base_effect.py`: 알려진 L[t]/L[t-11] × (1+다음 달 MoM), MoM은 달력월 평균 + 전체 잔차 풀링 또는 같은 달만)과 경험분포 baseline을 2000년 이후 공표 지수로 연구 백테스트(`scripts/backtest_cpi_baselines.py`, 워크플로 `cpi-baselines.yml`) | fixed | `data/generated/cpi_baseline_backtest.json` (vintage 2026-09-08). 헤드라인 실시간 모델 `headline-cpi-yoy-base-effect-pooled-mom-0.1`, Core는 `core-cpi-yoy-empirical-change-0.1` 유지. 연도별로는 Core 2021·2011·2012, 헤드라인 2003·2008·2012·2015만 반대 |
| R43-M1 | Medium | 인하 모델 학습에 ZLB 회의가 '인하 없음'으로 들어가 있었음. D-011은 예측에서만 ZLB를 가렸고 학습은 그대로였음. 2019–2026 60회의 중 16건, 2015–2026 92회의 중 24건이 ZLB | fixed | 과제 43: 비-ZLB 회의만으로 인하 모델 학습(4건 미만이면 전체로 폴백). 워크포워드 2015–2026: BSS +0.020→+0.028, 비-ZLB +0.007→+0.015, ECE 0.081→0.061. 2019–2026은 +0.172→+0.149로 약간 나빠짐. 구조적 근거로 채택, 결론("skill 거의 없음")은 불변 |
