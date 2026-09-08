# 과제 15 응답 — 2019–2026 백테스트 재실행

작성: Claude. 브랜치 `claude/task-15-backtest-2026`. 입력: 봇이 커밋한 62회의 스냅샷(`21852bf`).

## 결과

| 모델 | 스코프 | OOS | 비-ZLB | 인하 | Brier | climatology | always-hold | BSS clim | BSS hold |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 휴리스틱 | all | 54 | 38 | 8 | 0.1021 | 0.1409 | 0.1481 | +0.276 | +0.311 |
| 휴리스틱 | window | 51 | 36 | 6 | 0.0835 | 0.1203 | 0.1176 | +0.306 | +0.290 |
| 로지스틱 WF | scheduled | 52 | 36 | 6 | 0.0981 | 0.1184 | 0.1154 | +0.172 | +0.150 |

로지스틱 비-ZLB 36건: 모델 0.1417 vs climatology 0.1456 (BSS +0.026). 절편 전용 대비 +0.060. ECE 0.064.

- D-013(비-ZLB 30건)은 처음 충족됐다. `climatology_gate_passed=true`.
- D-007은 미충족. `market_baseline_available=false`, `signal_eligible=false`.
- 2025년 인하 3회에 휴리스틱은 0.31~0.36(climatology 0.13~0.16)을 줬고, 2026년 동결 5회에는 0.09~0.35를 줬다.
- 2019–2024 대비 skill 하락(+0.29 → +0.17). 2026년 인플레이션 재가속(CPI YoY 3~4%)과 장기 동결을 4개 특징으로 읽기 어렵고,
  인상은 결과공간에 없다.

## 검증

- 2019–2024 스냅샷 49건이 새 파일의 앞 49건과 동일함을 확인(결측 처리 변경이 기존 값에 영향 없음).
- `test_checked_in_2019_2026_backtests_reproduce`, `test_walk_forward_2019_2026_matches_checked_in_report_and_passes_sample_gate` 추가. 테스트 146건 통과.

## 다음

R14-M2/R15-M1: 결과공간을 cut/hold/hike 3원으로 확장하고(다항 로지스틱 또는 두 이진 모델), 실시간 비교에도 hike 확률을 기록.
그 뒤에야 Kalshi 사다리(hike 0.525)와 정면 비교가 된다.
