# Third Claude Review Task

다음 구현을 최신 main에서 독립 검산한다.

- `src/forecast_macro/transforms.py`
- `src/forecast_macro/contracts.py`
- `tests/test_transforms_contracts.py`
- `docs/CONTRACT_SCHEMA.md`

## 질문

1. CPI index의 MoM/YoY 변환식과 필요한 관측 개수가 정확한가?
2. Fed 금리 변화 bucket 경계가 계약 의미와 일치하는가?
3. 다중 outcome 가격 정규화가 어떤 상황에서 부적절한가?
4. 계약시각과 시장 관측시각 검증에 빠진 timezone 문제가 있는가?
5. 수수료 모델 전에 반드시 추가할 필드는 무엇인가?

기존 파일은 수정하지 말고 완성된 Markdown 보고서로 답한다.
