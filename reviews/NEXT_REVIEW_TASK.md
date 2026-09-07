# Next Claude Review Task

ChatGPT가 백테스트 기반을 추가했다. 다음 파일을 독립 검산한다.

- `src/forecast_macro/evaluation.py`
- `src/forecast_macro/backtest.py`
- `tests/test_evaluation.py`
- `docs/BACKTEST_PLAN.md`

## 확인 사항

1. Brier score 계산이 정확한가?
2. 확률 1.0이 마지막 calibration bin에 포함되는가?
3. expanding-window split에 미래 데이터가 섞일 수 있는가?
4. 발표시각 cutoff가 누출을 차단하는가?
5. ECE 구현과 가중치가 올바른가?
6. 추가해야 할 경계조건 테스트는 무엇인가?

완성된 Markdown 리뷰 보고서로 답하고 기존 코드는 직접 수정하지 않는다.
