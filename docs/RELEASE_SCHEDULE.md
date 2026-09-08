# 공식 발표 일정 (`data/release_schedule.csv`)

계약의 `outcome_at`은 거래소 값이 아니라 이 파일에서만 나온다 (제안 D-014).

## 출처

| series | 페이지 | 시각 |
| --- | --- | --- |
| `cpi` | https://www.bls.gov/schedule/news_release/cpi.htm | 08:30 ET |
| `employment_situation` | https://www.bls.gov/schedule/news_release/empsit.htm | 08:30 ET |
| `fomc` | https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm | 14:00 ET (2일차) |

## 갱신 절차

BLS는 스크립트 요청(HTML, ICS 모두)에 403을 돌려준다. 자동 수집은 하지 않는다.

1. 브라우저로 위 페이지를 연다.
2. 표의 행을 CSV에 추가한다. `timezone`은 항상 `America/New_York`, `fetched_at`은 읽은 시각(UTC ISO).
3. `pytest tests/test_review_7.py`로 로드·중복·DST 검사를 통과시킨다.
4. FOMC는 회의 2일차 날짜를 `reference_period`와 `release_date`에 같이 쓴다. 긴급회의는 넣지 않는다.
5. 2027 FOMC 일정은 연준 페이지 기준 "직전 회의에서 확정되기 전까지 잠정"이다. 회의가 확정될 때 다시 확인한다.

BLS 일정은 예산 중단 등으로 바뀔 수 있다. 계약 본문이 진술한 시각과 CSV가 다르면 검증이 실패(fail-closed)하므로,
실패가 보이면 페이지를 다시 읽어 CSV를 고친다.
