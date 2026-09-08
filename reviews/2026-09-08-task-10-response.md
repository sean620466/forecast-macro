# 과제 10 응답 — 리뷰 4 후속 (R4-H2, R4-L1, R4-L2, R4-L4)

작성: Claude. 브랜치 `claude/task-10-backtest-followups` (과제 08 위에 쌓임).

## 반영

| ID | 변경 | 검증 |
| --- | --- | --- |
| R4-H2 | `--event-scope window`: 직전 정기 결정 대비 변화로 라벨. 결과가 cutoff 전에 확정된 창(2020-04-29)은 점수화하지 않고 `dropped_predetermined_windows`에 기록 | `test_window_scope_attributes_emergency_cuts_to_the_next_scheduled_meeting` |
| R4-L1 | 49행 전부 `monetaryYYYYMMDDa.htm` 보도자료 URL로 교체. 49건 모두 HTTP 200 확인(2026-09-08). 로더가 회의일과 URL 일치를 강제 | `test_every_decision_cites_its_own_press_release`, `test_generic_calendar_source_is_rejected` |
| R4-L2 | `validate_continuity`. scheduled 스코프는 `--allow-rate-gaps` 없이는 2020-04-29 불연속에서 중단 | `test_scheduled_scope_script_refuses_gap_without_flag` |
| R4-L4 | all/window 체크인 JSON 재계산 회귀 테스트 | `test_checked_in_backtests_reproduce` |

## 결과 (scheduled vs window)

| Scope | OOS | Cuts | Model | Climatology | Always hold | BSS clim | BSS hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Scheduled | 39 | 3 | 0.049031 | 0.095612 | 0.076923 | +0.487 | +0.363 |
| Window | 38 | 3 | 0.050321 | 0.097596 | 0.078947 | +0.484 | +0.363 |

표본에 회의 간 긴급 조치가 2020년 3월 하나뿐이라 두 스코프 차이는 그 한 행이다. 창 라벨이 의미를 갖는 것은 다음 긴급 조치가
있을 때다. 2020-04-29를 "cut"으로 점수화하면 ZLB 마스크(p=0.005)와 충돌해 오차 0.99가 생기는데, 이는 모델 결함이 아니라
결과를 이미 아는 시점의 예측을 채점하는 문제라서 제외가 맞다.

## 잔여

- R4-M3 스냅샷 메타데이터(`fetched_at`, 관측월, `realtime_start`)와 R4-M4 cutoff 정렬은 FRED 키가 있는 환경에서 스냅샷을
  다시 빌드해야 하므로 별도 과제.
- R4-L3 `forecast_at` 규칙은 과제 05에서 `fed_model_comparison`과 통일했고 `EXTENDED_BACKTEST.md`에 명시.

테스트 123건 통과.
