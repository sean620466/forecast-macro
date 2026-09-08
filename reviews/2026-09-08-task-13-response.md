# 과제 13 응답 — 다음 FOMC에 대한 모델 확률과 시장 확률 나란히 기록

작성: Claude. 브랜치 `claude/task-13-live-comparison`.

## 구현

- `snapshots.build_feature_snapshot(client, meeting_date, vintage_date)`: 과거 백테스트(전날 vintage)와 실시간(오늘 vintage)이
  같은 코드 경로를 쓴다. vintage가 회의일 이후면 거부.
- `live_comparison.py`:
  - `next_scheduled_meeting`: `data/release_schedule.csv`의 다음 FOMC.
  - `kalshi_event_ticker`: 회의일 → `KXFED-YYMON`.
  - `market_cut_probability`: 사다리 스냅샷을 현재 상단 금리 기준으로 cut / hold / hike로 접고 `[bid, ask]` 범위도 합산.
  - `model_cut_probabilities`: 휴리스틱 baseline과 2019–2024 정기회의 전체로 학습한 로지스틱의 P(cut). ZLB 마스크 적용.
  - `build_comparison`: 기록에 특징(vintage 포함), 모델 버전, 두 모델 확률, 시장 확률·범위·관측시각·출처 파일, edge. `signal_eligible=false` 고정.
- `scripts/compare_fed_market.py`: FRED 키로 오늘 vintage 특징을 만들고 최신 가격 스냅샷과 비교해 `data/generated/fed_market_comparisons/`에 기록.
- `.github/workflows/compare-fed-market.yml`: 평일 13:40 UTC(08:30 ET 발표 이후) 실행, 봇 커밋.

## 검증

- 실제 봇 스냅샷(KXFED-26SEP 2026-09-08 02:44Z)으로 P(cut) = 0.475, 범위 [0.46, 0.52], hold 0.51, hike 0.015 재현.
- 로컬에는 FRED 키가 없어 실시간 경로는 가짜 클라이언트로만 테스트했다. 첫 실제 실행은 GitHub Actions에서 이 커밋의 push로 트리거된다.
- 테스트 138건 통과.

## 이 기록의 의미와 한계

D-007은 "시장 대비 표본외 Brier skill"을 요구한다. 이 기록은 그 평가의 **입력**이지 결과가 아니다. 회의가 끝나면 실제 결정을
라벨로 붙여 모델과 시장의 Brier를 같은 이벤트에서 비교해야 하며, 그 평가 스크립트는 다음 과제다. 그전까지 edge 값은
어떤 화면에도 신호로 표시되지 않는다(D-012).
