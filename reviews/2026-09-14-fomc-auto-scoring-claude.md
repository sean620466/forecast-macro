# 2026-09-16 결정 후 첫 D-007 채점 점검 — Claude (과제 48)

작성 2026-09-14. 기준 `main` 8e0a2c5. 로컬 `pytest -q` 218건 통과, `ruff check .` 통과(수정 전).

## 결론

**그대로 두면 채점되지 않는다.** 워크플로 단계와 `comparison_scoring`은 정상이지만, 채점기가 결과 라벨을 읽는
`data/fomc_meetings_2019_2026.csv`는 마지막 행이 2026-07-29이고 사람이 전사해야만 늘어난다. 09-17 실행은
`final_record_per_meeting`에서 2026-09-16이 `decision_at`에 없어 기록을 건너뛰고 `scored_meetings: 0`을 다시 쓴다.
이슈도 열리지 않는다(새로 채점된 행이 없으므로).

## 점검 내역

| 항목 | 결과 |
| --- | --- |
| 워크플로 단계 순서 (비교 기록 → 채점 → 대시보드 → 알림 → persist) | 정상. `scoring_alerts.py --ref HEAD`는 커밋 전 HEAD와 비교하므로 새 행을 잡는다 |
| Core CPI 첫 채점(2026-09-11) | 실제로 돌았다: `core_cpi_market_scoring.json` `scored_releases: 1`. 발표값을 ALFRED에서 직접 받는 토픽은 자동이다 |
| `final_record_per_meeting` 마감 규칙 | `as_of < decision_at(14:00 ET)`. 09-16 13:47 UTC 기록이 마지막 채점 대상이 된다. 정상 |
| Fed 결과 라벨 출처 | `load_fomc_history(fomc_meetings_2019_2026.csv)` 한 곳. 자동 갱신 경로 없음 → **불충족** |
| 회의 CSV를 워크플로가 직접 늘리는 방안 | 불가. (1) `fit_cut_model`은 스냅샷 없는 학습 행에서 KeyError, 봇 푸시는 `build-snapshots.yml`을 못 깨운다. (2) 두 CSV(2015·2019)는 회귀 테스트가 길이 94·62와 체크인 백테스트 JSON에 고정 |
| DFEDTARU로 라벨 대체 | 부적합. D-002는 결정별 보도자료 인용을 요구하고 `load_fomc_history`가 URL 형식을 검사한다. 결정 다음 날 아침 FRED 반영 시각도 보장 없음 |

## 수정 (커밋 b030bae)

- `src/forecast_macro/fomc_decisions.py`: 결정 보도자료(`monetary<YYYYMMDD>a.htm`, D-002 출처)를 읽어 **결정 문장**
  ("the Committee decided to maintain/lower/raise the target range … X to Y percent")에서 목표범위를 파싱한다.
  반대표 문장("preferred to maintain … at")은 무시하고, 동사(유지/인하/인상)와 직전 상단 금리의 변화가 일치해야 한다.
  U+2011 비분리 하이픈 정규화. 2009–2015 문구("current 0 to 1/4 percent target range … remains appropriate")도 지원.
- 라벨은 봇 소유 파일 `data/generated/fomc_decisions.csv`(회의 CSV와 같은 스키마)에 추가한다. 추가 전 `load_fomc_history`로
  검증(연속성·라벨·출처 URL)하고 실패 시 파일을 건드리지 않는다. `score_fed_comparisons.py`가 이 파일을 이력에 병합한다
  (이력과 겹치는 행은 완전히 일치해야 함). 학습 데이터(`fomc_meetings_2015_2026.csv`, 스냅샷)는 그대로다.
- 워크플로: 채점 직전에 `record_fomc_decisions.py` 실행(`continue-on-error`), persist 경로에 CSV 추가, 실패 시 마지막
  단계에서 실행을 빨갛게 만들어 `alerts.yml`이 `workflow-failure` 이슈를 연다. 결정 후 6시간 안에는 보도자료가 없어도
  조용히 다음 실행을 기다리고, 그 뒤에는 실패한다.
- 수동 대체: `python scripts/record_fomc_decisions.py --statement-file <저장한 보도자료.htm>` 후 CSV 커밋
  (`docs/FOMC_DATASET.md`). 러너 자체 점검: `workflow_dispatch` 입력 `verify_statement_fetch=true`가 마지막 라벨 회의
  (2026-07-29)의 보도자료를 받아 파싱 결과를 이력 행과 대조한다.
- 테스트 `tests/test_review_48.py` 14건: 문구별 파싱, 결정 전/후 대기 회의 판정, 검증 실패 시 파일 불변, 이력 병합,
  **저장소에 커밋된 실제 09-16 비교 기록이 hold 라벨로 1건 채점되고 알림 본문이 만들어짐**, 스크립트 end-to-end,
  유예 시간 전후 종료 코드, 워크플로 단계 순서.

## 실행하지 못한 항목

- 이 샌드박스는 federalreserve.gov 접속이 막혀(proxy 403) 실제 보도자료로 파서를 돌리지 못했다. 파서 고정값은 연준 성명서
  표준 문구를 옮긴 것이다. 병합 뒤 `verify_statement_fetch=true`로 워크플로를 수동 실행해 러너에서 확인한다.
- 09-17 실제 실행 결과(이슈 `[채점] FOMC 금리 결정 2026-09-16 …`)는 그날 확인해야 한다.

## 남는 것 (별도 과제 제안, 결정 변경 없음)

- 학습 이력(`fomc_meetings_2015_2026.csv`)과 스냅샷은 여전히 수동으로 늘린다. 실시간 모델의 학습 표본은 94회의에 머문다.
  결정이 몇 건 쌓이면 스냅샷 빌드와 함께 한 번에 확장하는 절차를 과제로 올린다.
