# 과제 08 — 승인 이벤트 가격 스냅샷 수집

## 목표

`approved` 상태 계약으로 구성된 이벤트(현재: Polymarket 964993 실업률 9월)의 YES 호가를 CLOB에서 읽어
`build_event_price_snapshot`으로 정규화 확률을 만들고 `data/generated/market_price_snapshots/`에 기록한다.

## 범위

- `scripts/snapshot_market_prices.py`: review 결과 + 후보 파일 입력, 승인 이벤트만 처리, 이벤트별 orderbook 일괄 조회
- 스냅샷에 `observed_at`, 각 계약 `rules_text_hash`, 스프레드·사이즈, `outcome_at`, 정규화 전 mid 저장
- 정규화 실패(합계 5% 초과, 스프레드 10%p 초과, 시각 불일치 5초 초과)는 기록하되 확률은 비움
- 워크플로에 스냅샷 단계 추가(6시간 주기). 아티팩트가 아니라 저장소에 누적할지 결정 필요

## 완료 기준

- 실업률 이벤트의 9개 구간 확률 합 = 1인 스냅샷 1개 이상
- 모델 확률이 없는 상태에서는 비교 없이 가격만 기록 (D-012)
