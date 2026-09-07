# FORECAST MACRO

경제 데이터를 사람이 이해하기 쉽게 정리하고, AI가 현재 경제 상황을 분석하여 주요 거시경제 이벤트의 자체 확률을 계산하는 시스템입니다.

## MVP capabilities

- FRED 최신 관측값 수집
- Fed 금리 인하 확률 baseline
- CPI 결과 구간별 확률분포
- 모델 확률과 예측시장 가격 비교
- 기본 8%p edge 이상만 신호 표시
- Claude 독립 검산 프로토콜

> 현재 모델 계수는 제품 구조를 검증하기 위한 baseline입니다. 실제 의사결정에 사용하기 전에 vintage data 백테스트와 캘리브레이션이 필요합니다.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

예시:

```bash
forecast-macro \
  --inflation 2.6 \
  --unemployment 4.3 \
  --unemployment-change-3m 0.2 \
  --policy-rate 4.5 \
  --market-cut 0.35
```

## Repository map

- `ARCHITECTURE.md` — 전체 데이터 및 모델 흐름
- `DECISIONS.md` — 확정된 의사결정
- `docs/DATA_SOURCES.md` — 공식 경제 데이터 설계
- `src/forecast_macro/data/` — 데이터 수집
- `src/forecast_macro/models/` — 확률 모델
- `src/forecast_macro/signals.py` — 시장가격 비교
- `tests/` — 자동 테스트
- `reviews/` — Claude 검산 결과

## Collaboration

- 설계, 코드, 가설은 저장소에서 관리합니다.
- Claude는 코드를 바로 덮어쓰지 않고 먼저 `reviews/`에 독립 검산 결과를 기록합니다.
- 최종 의사결정은 `DECISIONS.md`에 남깁니다.
