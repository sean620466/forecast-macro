# 과제 07 — 공식 발표 일정 기반 마감시각 (R5-H3)

## 목표

거래소 `endDate`를 신뢰하지 않고, BLS/Fed 공식 일정에서 계약의 `outcome_at`을 `America/New_York`으로 생성한다.
실업률 이벤트(Polymarket 964993)가 `close_time_verified=True`가 되어 가격 수집 단계로 넘어가는 것이 완료 기준이다.

## 범위

- `src/forecast_macro/release_schedule.py` 신설: 시리즈별(CPI, Employment Situation, FOMC) 발표 일시 테이블과 조회 함수
- 일정 출처: BLS 공식 일정 페이지(https://www.bls.gov/schedule/), Fed FOMC 캘린더. 출처 URL과 수집 시각을 기록
- 계약 본문에서 "scheduled to be released on October 2, 2026, at 8:30 AM ET"류 문구를 파싱해 테이블과 대조
- 거래소 `endDate`와 1시간 이상 차이 나면 blocker, 일치하면 `close_time_verified=True`
- D-009 확장 결정 제안: "거래소 타임스탬프는 참고용, 공식 일정이 기준"

## 검증

- 2026-10-02 08:30 ET == 12:30 UTC가 실업률 계약의 `outcome_at`이 되는 테스트
- 일정에 없는 날짜는 fail-closed
- DST 전환 전후(3월/11월) 케이스
