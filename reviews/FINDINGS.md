# 발견사항 장부

규칙은 `docs/COLLABORATION.md` 참조. ID는 `R<리뷰>-<등급><순번>`. 상태: open / fixed / partial / rejected / superseded.
리뷰 1~3의 `fixed` 항목은 ChatGPT 응답 파일 기준이며 이 장부에는 미해결·부분해결 항목만 옮겼다.
2026-09-07부터 ChatGPT 참여가 중단되어 Claude가 구현과 검토를 모두 맡는다(`docs/COLLABORATION.md` 참조).

## 리뷰 1 — Fed/CPI baseline (`2026-09-07-fed-cpi-baseline-claude.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R1-H3 | High | 예측시장 계약별 outcome bucket 확장 | partial | `contracts.py`에 `FedOutcome` 4구간 추가됨. 모델은 여전히 cut/hold_or_hike 이진 |
| R1-H4 | High | CPI `forecast_mom` 산출(nowcast) 코드 부재 | open | CPI 모델은 외부 숫자에 정규분포를 씌우는 래퍼 상태 |
| R1-M3 | Medium | CPI 불확실성 σ를 역사적 오차로 추정 | open | σ=0.12 고정 |
| R1-M4 | Medium | YES/NO 호가·수수료 정규화 | partial | 어댑터에 bid/ask 있음. 수수료 모델 없음(R5-L2와 연결) |
| R1-X1 | Medium | 실제 발표 timestamp 테이블(ALFRED real-time date와 별개) | open | 스냅샷은 D-1 날짜 vintage만 사용(R4-M4와 연결) |

## 리뷰 2 — 백테스트 기반 (`2026-09-07-backtest-claude-review-2.md`)

응답 기준 전 항목 `fixed`. 이후 리뷰에서 재발한 항목 없음.

## 리뷰 3 — 변환·계약 (`2026-09-07-contracts-claude-review-3.md`)

응답 기준 전 항목 `fixed`. 단 timezone 규칙(D-009)은 R5-H3에서 거래소 데이터에 대해 재발.

## 리뷰 4 — 확장 백테스트 (`2026-09-07-extended-backtest-claude-review-4.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R4-C1 | Critical | ZLB 제약 부재 | fixed | `945b36f`, D-011 |
| R4-H1 | High | 확률 정확히 0/1 반환 | fixed | `945b36f`, `PROBABILITY_EPSILON` |
| R4-H2 | High | `window` 스코프(정기회의 간 창 라벨) | open | 스크립트는 아직 all/scheduled만 |
| R4-M1 | Medium | `signal_eligible` 의미 분리 | fixed | `945b36f`, D-012 |
| R4-M2 | Medium | always-hold baseline | fixed | `fed_backtest`(945b36f) 및 워크포워드(claude/fix-review-5) 모두 보고 |
| R4-M3 | Medium | 스냅샷 재현성 메타데이터(`fetched_at`, 관측월, `realtime_start`, 모델 버전) | open | `snapshots.py`에 없음 |
| R4-M4 | Medium | forecast cutoff = 시장 관측시각 정렬 규칙 | open | 결정 미등록 |
| R4-L1 | Low | CSV `source`를 결정별 보도자료 URL로 | open | 49행 중 8행만 `monetaryYYYYMMDDa.htm` |
| R4-L2 | Low | scheduled 스코프 연속성 검증 | open | |
| R4-L3 | Low | `forecast_at` 인위적 시각 문서화 | open | R5-M5와 연결 |
| R4-L4 | Low | 테스트 공백(ZLB, JSON 회귀, 확률 0/1 금지, 연속성) | partial | ZLB·0/1 테스트 추가됨. JSON 회귀·연속성 테스트 없음 |

## 리뷰 5 — 워크포워드 모델·시장 파이프라인 (`2026-09-07-walk-forward-market-pipeline-claude-review-5.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R5-C1 | Critical | 워크포워드 로지스틱이 사실상 절편 전용. 개선분 94%가 ZLB 규칙 | fixed | ridge 수정 후 재검산(claude/fix-review-5). 절편 전용·비-ZLB 분해를 보고서와 문서에 추가. 비-ZLB BSS +0.06 |
| R5-C2 | Critical | `ridge_strength`가 평균 경사 스케일에 적용돼 λ≈n. 기본 설정 학습 테스트 없음 | fixed | 7937715 (ChatGPT). 수정 후 Brier 0.067791 독립 재계산 일치 |
| R5-H1 | High | 계약 시리즈 정체성(Core/headline, YoY/MoM, SA/NSA) 미검증 | fixed | 2221e32 (ChatGPT) + claude/review-6: 명시 근거 없으면 `None`, 식별 불가는 항상 blocker (R6-H1) |
| R5-H2 | High | Kalshi 탐색 `cursor` 무시. 열린 KXFED 87건 누락 | partial | 859e5f1 (ChatGPT) 페이지네이션 추가. 누적 임계값("above X%") 계약을 구간 확률로 바꾸는 매핑은 미구현 |
| R5-H3 | High | Polymarket `endDate` 시간대 불신뢰(ET를 Z로 표기) | fixed | 45a26f4 + claude/task-07: `release_schedule.py`가 공식 일정(BLS/Fed, `America/New_York`)에서 `outcome_at`을 만들고 거래소 마감이 발표 이후면 거부. `data/release_schedule.csv`에 출처·수집시각 기록 |
| R5-M1 | Medium | `resolutionSource` 빈 값으로 CPI 시장 영구 차단 | fixed | claude/review-6: 본문에서 공식 호스트 URL 추출, `resolution_source_origin` 기록 (R6-M3). 실측 CPI 10건 출처 확보, 시리즈 불일치로만 차단 |
| R5-M2 | Medium | `rules_version=updatedAt`은 규칙 버전이 아님 | fixed | claude/review-6: 내용 해시 기반 버전, `venue_updated_at`·`fetched_at` 분리 (R6-H3) |
| R5-M3 | Medium | `review_market_candidates`가 비어있지 않은 문자열이면 승인 | fixed | claude/review-6: `official_sources.py` 공유, 리뷰 단계에서 호스트 검사 (R6-H2) |
| R5-M4 | Medium | 구간 정규식: 엄격 부등호, MoM/YoY, 월 미구분 | fixed | claude/review-6: 엄격 부등호 blocker, 그룹 subject 일치 검사 (R6-M2) |
| R5-M5 | Medium | 워크포워드에 입력 검증 없음, `forecast_at` 불일치 | fixed | claude/fix-review-5 |
| R5-M6 | Medium | 워크포워드 보고서에 always-hold 없음(BSS +0.084) | fixed | claude/fix-review-5. 수정 후 BSS vs always-hold +0.119 |
| R5-L1 | Low | 인하 0건이면 always-hold BSS 0 나눗셈 | fixed | claude/fix-review-5. `None` 반환 |
| R5-L2 | Low | `fee_schedule_id` 자리표시자, 수수료 모델 부재 | open | |
| R5-L3 | Low | ruff 버전 미고정, 0.16.6에서 2건 실패 | fixed | 70e035a. `ruff==0.16.6` 고정 |
| R5-L4 | Low | 계수 부호 비경제적(실업률 음) | open | R5-C2 수정 후에도 실업률 계수 음수(약 −0.8 표준화). 문서에 명시. 표본 확장 후 재점검 |
| R5-X1 | Medium | `discover-markets` 워크플로가 GitHub 러너에서 탐색 단계 실패(로컬은 성공). 원인 로그 미확인 | partial | claude/fix-discovery-ci: 거래소별 오류를 `.status.json`에 기록하고 계속 진행, User-Agent 명시. 러너 IP 차단이면 self-hosted 또는 프록시 필요 |
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
| R6-L2 | Low | `MODEL_SERIES["cpi"]`가 어느 모델 기준인지 불명확 | open | CPI 구간 모델(MoM SA) 기준. Fed 특징(YoY NSA)과 다름을 문서화 필요 |
| R6-X1 | Medium | 실업률 9건은 규칙 검증 전부 통과, `close_time_verified=False`만 남음 | fixed | claude/task-07: 2026-09-08 실측에서 실업률 9건 `approved`, CPI 10건은 시리즈 불일치로 차단 유지 |

## 과제 07 — 공식 발표 일정 (`reviews/tasks/07-release-schedule.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R7-H1 | High | `verify_market_rules.py`/`review_macro_markets.py`가 `signal_eligible = approved > 0`으로 기록. 계약 승인과 D-007 신호 자격을 혼동 | fixed | 같은 브랜치. `approved_contracts` 카운트로 분리, `signal_eligible`은 항상 `false` + 이유 |
| R7-M1 | Medium | BLS가 스크립트 요청(HTML·ICS 모두)을 403으로 거부해 일정 자동 갱신 불가 | open | 브라우저로 읽어 CSV에 수동 전사. 갱신 절차를 `docs/RELEASE_SCHEDULE.md`에 기록. 2027 FOMC 일정 미수록 |
| R7-M2 | Medium | Polymarket `endDate`가 ET 벽시계인지 UTC인지 확정 불가. 현재는 "발표 이전이면 그대로 채택"(보수적) | open | 거래소 문서 확인 또는 실제 마감 관측으로 확정 필요 |
