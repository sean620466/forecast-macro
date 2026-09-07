# Claude Independent Review Protocol

Claude는 구현을 수정하기 전에 독립적으로 검산하고 결과를 새 리뷰 파일에 기록한다.

## 필수 검토 항목

1. 데이터 시점: 발표 당시 알 수 없었던 값이 입력에 포함됐는가?
2. 데이터 수정: revised data와 real-time vintage data가 구분됐는가?
3. 수학 검산: 결과별 확률이 0~1이고 합계가 1인가?
4. 캘리브레이션: Brier score와 reliability curve가 보고됐는가?
5. 시장 비교: 계약 조건, 마감시각, 수수료가 동일 기준인가?
6. 재현성: 모델 버전, 입력값, 실행시각이 저장됐는가?
7. 실패 조건: 결측치, API 오류, 비정상 시장가격을 안전하게 거부하는가?

## 리뷰 파일 형식

파일명: `reviews/YYYY-MM-DD-<topic>-claude.md`

- Verdict: PASS / PASS WITH CHANGES / FAIL
- Scope
- Reproduction steps
- Findings (Critical/High/Medium/Low)
- Independent calculations
- Required changes
- Residual risks

Claude는 `DECISIONS.md`를 직접 확정하지 않는다. 제안은 리뷰에 남기고 최종 채택은 별도 커밋으로 기록한다.
