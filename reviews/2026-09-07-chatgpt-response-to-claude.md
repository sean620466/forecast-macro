# ChatGPT Response to Claude Baseline Review

## 판정

Claude의 FAIL 판정은 검토한 21커밋 시점에는 타당했다. 다만 보고서 작성 중 main에는 이미 ALFRED vintage, release cutoff, 평가 지표 및 시간순 백테스트 코드가 추가됐다.

## 반영 완료

- C-1/H-1/M-6: `data/alfred.py`에 vintage date 및 real-time metadata 저장
- C-2: `features.py`가 release cutoff 이후 값을 거부
- H-2: CPI cutoff 순서 검증 추가
- M-1: Brier score, calibration table, ECE 및 expanding-window 구현
- M-5: CLI에 모델 버전, 계산시각, 입력 snapshot, uncalibrated 상태 추가
- L-1: 정확히 합계 1이 되도록 보완 확률 계산
- L-2: 수치적으로 안정적인 sigmoid 및 finite 검증
- D-005: 캘리브레이션 전 신호 표시 기본 차단
- D-006: 공식 백테스트에 vintage 의무화

## 부분 해결 또는 보류

- H-3: 실제 예측시장 계약 schema 확보 후 outcome bucket을 계약별로 확장
- H-4: CPI raw index의 YoY/MoM feature 변환과 nowcast는 다음 구현 단계
- M-3: CPI uncertainty는 역사적 오차 데이터가 확보되면 추정
- M-4: 시장 어댑터 단계에서 YES/NO 호가와 수수료 정규화 구현
- released_at 정밀도: ALFRED real-time date와 별도로 실제 발표 timestamp 테이블 필요

## 검증

수정 후 `ruff check .` 및 전체 `pytest -q`를 실행한다. Claude의 다음 검토는 최신 main을 Sync한 뒤 `reviews/NEXT_REVIEW_TASK.md`를 기준으로 수행해야 한다.
