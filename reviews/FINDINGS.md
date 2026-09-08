# 발견사항 장부

규칙은 `docs/COLLABORATION.md` 참조. ID는 `R<리뷰>-<등급><순번>`. 상태: open / fixed / partial / rejected / superseded.
리뷰 1~3의 `fixed` 항목은 ChatGPT 응답 파일 기준이며 이 장부에는 미해결·부분해결 항목만 옮겼다.

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
| R4-M2 | Medium | always-hold baseline | partial | `fed_backtest`에만 추가. 워크포워드 보고서에는 없음(R5-M6) |
| R4-M3 | Medium | 스냅샷 재현성 메타데이터(`fetched_at`, 관측월, `realtime_start`, 모델 버전) | open | `snapshots.py`에 없음 |
| R4-M4 | Medium | forecast cutoff = 시장 관측시각 정렬 규칙 | open | 결정 미등록 |
| R4-L1 | Low | CSV `source`를 결정별 보도자료 URL로 | open | 49행 중 8행만 `monetaryYYYYMMDDa.htm` |
| R4-L2 | Low | scheduled 스코프 연속성 검증 | open | |
| R4-L3 | Low | `forecast_at` 인위적 시각 문서화 | open | R5-M5와 연결 |
| R4-L4 | Low | 테스트 공백(ZLB, JSON 회귀, 확률 0/1 금지, 연속성) | partial | ZLB·0/1 테스트 추가됨. JSON 회귀·연속성 테스트 없음 |

## 리뷰 5 — 워크포워드 모델·시장 파이프라인 (`2026-09-07-walk-forward-market-pipeline-claude-review-5.md`)

| ID | 등급 | 요약 | 상태 | 비고 |
| --- | --- | --- | --- | --- |
| R5-C1 | Critical | 워크포워드 로지스틱이 사실상 절편 전용. 개선분 94%가 ZLB 규칙 | open | 문서 해석 교체 필요 |
| R5-C2 | Critical | `ridge_strength`가 평균 경사 스케일에 적용돼 λ≈n. 기본 설정 학습 테스트 없음 | open | |
| R5-H1 | High | 계약 시리즈 정체성(Core/headline, YoY/MoM, SA/NSA) 미검증 | open | |
| R5-H2 | High | Kalshi 탐색 `cursor` 무시. 열린 KXFED 87건 누락 | open | 누적 임계값 계약 매핑도 필요 |
| R5-H3 | High | Polymarket `endDate` 시간대 불신뢰(ET를 Z로 표기) | open | D-009 확장 제안 |
| R5-M1 | Medium | `resolutionSource` 빈 값으로 CPI 시장 영구 차단 | open | 본문 URL 추출 경로 필요 |
| R5-M2 | Medium | `rules_version=updatedAt`은 규칙 버전이 아님 | open | |
| R5-M3 | Medium | `review_market_candidates`가 비어있지 않은 문자열이면 승인 | open | |
| R5-M4 | Medium | 구간 정규식: 엄격 부등호, MoM/YoY, 월 미구분 | open | |
| R5-M5 | Medium | 워크포워드에 입력 검증 없음, `forecast_at` 불일치 | open | |
| R5-M6 | Medium | 워크포워드 보고서에 always-hold 없음(BSS +0.084) | open | |
| R5-L1 | Low | 인하 0건이면 always-hold BSS 0 나눗셈 | open | |
| R5-L2 | Low | `fee_schedule_id` 자리표시자, 수수료 모델 부재 | open | |
| R5-L3 | Low | ruff 버전 미고정, 0.16.6에서 2건 실패 | open | |
| R5-L4 | Low | 계수 부호 비경제적(실업률 음) | open | R5-C2 수정 후 재점검 |
