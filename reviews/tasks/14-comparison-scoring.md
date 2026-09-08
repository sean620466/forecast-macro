# 과제 14 — 비교 기록 채점 (D-007 평가)

## 목표

`data/generated/fed_market_comparisons/`의 기록에 실제 FOMC 결정을 라벨로 붙여, 같은 이벤트에서 모델(휴리스틱·로지스틱)과
시장의 Brier score를 누적한다. 시장 대비 BSS > 0이 30건 이상의 비-ZLB 표본에서 확인될 때만 `signal_eligible` 검토(D-007, D-013).

## 범위

- `data/fomc_meetings_2019_2024.csv`를 2025~2026으로 확장하는 절차(보도자료 URL, 결정시각). 2025년 결정은 연준 페이지에서 전사.
- 회의별 "마지막 기록"(회의 전날 cutoff)만 채점에 사용. 같은 회의의 중복 기록은 제외.
- 채점 결과를 `data/generated/fed_market_scoring.json`에 기록: n, 모델 Brier, 시장 Brier, BSS, 비-ZLB n.
- 실업률 이벤트도 같은 방식으로 채점할 수 있게 구조를 일반화(결과 라벨은 BLS 발표값 반올림).
