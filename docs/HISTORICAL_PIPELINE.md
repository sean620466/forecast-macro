# Historical FOMC Pipeline

## 공식 입력

- 경제 데이터 vintage: FRED/ALFRED series observations API
- 정책금리 상단: `DFEDTARU`
- 정책금리 하단: `DFEDTARL`
- 회의일 및 성명: Federal Reserve FOMC historical materials

## 파이프라인

1. 각 FOMC 결정시각보다 앞선 forecast cutoff를 정한다.
2. cutoff 날짜를 `vintage_dates`로 사용해 당시 보이던 경제 데이터만 요청한다.
3. 각 값의 observation date, real-time period, fetch time을 보존한다.
4. 발표시각이 cutoff 이후인 feature를 거부한다.
5. `DFEDTARU`의 회의 전후 값을 비교해 cut/hold/hike 라벨을 만든다.
6. 시간순 expanding-window 백테스트로 표본외 확률을 생성한다.

## 다음 데이터 작업

- 연도별 FOMC 회의 캘린더를 정규화된 CSV로 저장
- CPI/PCE/고용 데이터의 실제 release timestamp 테이블 구축
- 2008년 이전 단일 목표금리 체계와 이후 목표범위 체계를 분리
- 원본 응답 해시와 수집 로그 저장
