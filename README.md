# FORECAST MACRO

경제 데이터를 시점별(vintage)로 수집하고, 주요 거시 이벤트에 대한 자체 확률을 예측시장 가격과 같은 결과공간에서 나란히 기록·채점하는
시스템입니다. 신호를 보여주는 것이 아니라 **"모델이 시장보다 나은가"를 정직하게 측정하는 것**이 1차 목표입니다(D-001, D-007, D-012).

## 지금 상태 한눈에

- **STATUS.md** — 매일 자동 갱신되는 요약(모델 vs 시장 확률, 게이트, 백테스트). 협업자나 다른 AI가 읽기 좋은 형식.
- **docs/dashboard/index.html** — 같은 내용의 대시보드. GitHub Pages(`main` 브랜치 `/docs`)를 켜면 웹 주소로 열림.

## 현재 동작하는 것 (2026-09-08)

| 파이프라인 | 주기 | 산출물 |
| --- | --- | --- |
| 시장 탐색 → 규칙·일정 검증 → 가격 스냅샷 | 6시간 | `data/generated/market_prices/*.json` (Kalshi Fed·실업률·CPI 사다리, Polymarket 실업률·Core CPI 구간) |
| Fed 모델(cut/hold/hike) vs 시장 | 평일 09:40 ET | `data/generated/fed_market_comparisons/`, `fed_market_scoring.json` |
| 실업률 baseline vs 시장 | 평일 09:40 ET | `data/generated/unemployment_market_comparisons/`, `unemployment_market_scoring.json` |
| Core CPI YoY baseline vs 시장 | 평일 09:40 ET | `data/generated/core_cpi_market_comparisons/`, `core_cpi_market_scoring.json` (Polymarket + Kalshi, 장소별 파일) |
| 헤드라인 CPI YoY baseline vs 시장 (Kalshi) | 평일 09:40 ET | `data/generated/headline_cpi_market_comparisons/`, `headline_cpi_market_scoring.json` (기저효과 모델) |
| CPI baseline 연구 백테스트 | 변경 시 | `data/generated/cpi_baseline_backtest.json` (경험분포 vs 기저효과, 2000년 이후 317개월; `docs/CPI_BASELINES.md`) |
| 시점별 특징 스냅샷(ALFRED) | 수동/변경 시 | `data/generated/fomc_feature_snapshots_2015_2026.json` (94회의; 2019–2026 파일은 회귀 테스트 고정값) |
| 알림 | 워크플로 완료 시 / 채점 직후 | GitHub 이슈: `workflow-failure`(실패 시 열고 재성공 시 자동 닫힘), `scoring`(결과가 확정되어 채점된 회의·발표마다 1건) |

모든 산출물은 GitHub Actions의 봇 계정이 저장소에 커밋합니다. `signal_eligible`은 코드 전체에서 `false`이며, 결정(D-0xx) 없이는 바뀌지 않습니다.

## 게이트 (fail-closed)

- 계약 규칙: 공식 기관 호스트(BLS·연준·BEA)만 출처로 인정, 시리즈 정체성(Core/headline, YoY/MoM, SA/NSA) 명시 근거 필요
- 결과 확정 시각: 거래소 값이 아니라 공식 발표 일정(`data/release_schedule.csv`)에서 생성(D-014)
- 가격: 구간 시장은 `Σbid ≤ 1 ≤ Σask`·폭 ≤ 0.35(D-015), 사다리는 연속성·호가 범위 단조성·rung 스프레드 게이트(D-019: 평균 ≤ 0.05, 최대 ≤ 0.12)
- 모델: ZLB에서 인하 확률 고정(D-011), 비-ZLB 30건 미만이면 연구 게이트도 통과 불가(D-013)

## Quick start

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
.venv/bin/pytest -q
.venv/bin/ruff check .
```

백테스트 재현:

```bash
python scripts/run_fed_backtest.py --meetings data/fomc_meetings_2015_2026.csv \
  --snapshots data/generated/fomc_feature_snapshots_2015_2026.json --event-scope window \
  --output /tmp/window.json
python scripts/run_fed_model_comparison.py --meetings data/fomc_meetings_2015_2026.csv \
  --snapshots data/generated/fomc_feature_snapshots_2015_2026.json --output /tmp/wf.json
```

실시간 스크립트(`scripts/compare_*.py`, `scripts/build_fomc_snapshots.py`)는 `FRED_API_KEY` 환경변수가 필요하며 저장소에는 GitHub secret으로만 존재합니다.

## Repository map

- `DECISIONS.md` — 확정된 결정 D-001~D-019
- `reviews/FINDINGS.md` — 모든 검토 발견사항과 상태 (open/partial/fixed)
- `reviews/` — 검토 보고서, 응답, `tasks/`
- `docs/COLLABORATION.md` — 운영 규칙(현재 Claude 단독, CI 초록이면 직접 병합)
- `docs/EXTENDED_BACKTEST.md`, `docs/WALK_FORWARD_MODEL.md` — 백테스트 결과와 해석
- `docs/CONTRACT_SCHEMA.md`, `docs/RELEASE_SCHEDULE.md` — 계약·일정 처리 규칙
- `src/forecast_macro/models/` — `fed.py`(휴리스틱 3원), `logistic.py`, `unemployment.py`, `cpi.py`
- `src/forecast_macro/market_*.py`, `official_sources.py`, `release_schedule.py` — 시장 게이트
- `src/forecast_macro/live_comparison.py`, `unemployment_comparison.py`, `*_scoring.py` — D-007 루프
- `tests/` — 213개, 체크인된 JSON 재현 회귀 테스트 포함

## 현재 판정

- Fed 워크포워드 로지스틱: 표본을 2015–2026(94회의, 인상 사이클 2개)으로 늘리면 climatology 대비 BSS가 +0.15(2019–2026)에서 +0.03으로 줄고 비-ZLB 68건에서는 +0.015(인하 모델은 비-ZLB 회의만으로 학습, 과제 43). 같은 2020–2026 회의에서 2015년부터 학습한 모델이 2019년부터 학습한 모델보다 나쁘다. 휴리스틱은 2015–2026에서 climatology보다 못하다(BSS −0.12).
- 시장 baseline 대비 채점: 첫 Core CPI 발표 2026-09-11, 첫 회의 2026-09-16, 첫 실업률 발표 2026-10-02. 30건까지 수년.
- 결론: 아직 아무 신호도 자격이 없다. 그것이 이 저장소가 지금까지 확인한 사실이다.
