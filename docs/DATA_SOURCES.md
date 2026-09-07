# Economic Data Sources

| 분야 | 1차 출처 | 초기 시리즈/데이터 | 사용 목적 |
|---|---|---|---|
| 물가 | BLS / FRED | CPI-U, Core CPI | CPI 결과 및 Fed 모델 |
| 고용 | BLS / FRED | Unemployment, Payrolls | 노동시장 방향 |
| 성장 | BEA / FRED | Real GDP, PCE | 성장·침체 판단 |
| 금리 | Federal Reserve / FRED | Target range, SOFR, yields | 정책·금융여건 |
| 기대 | 시장 데이터 공급자 | Fed/CPI 계약 가격 | 모델 대비 시장 확률 |

## 데이터 계약

각 레코드는 최소한 다음 필드를 보존한다.

- `series_id`
- `value`
- `observed_at`: 경제활동 기준 시점
- `released_at`: 실제 공개 시점
- `fetched_at`: 시스템 수집 시점
- `source`
- `vintage` 또는 revision 식별자

API 키는 저장소에 커밋하지 않고 환경변수로만 제공한다.
