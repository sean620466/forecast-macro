# Connect Claude to FORECAST MACRO

## 권장 방식: 일반 Claude Chat + GitHub

유료 Claude Code 없이 일반 Claude Chat을 독립 검산자로 사용한다.

### 최초 한 번만 설정

1. Claude에서 FORECAST MACRO 전용 Project를 만든다.
2. Project knowledge 오른쪽 위 `+`를 누른다.
3. GitHub를 선택하고 `sean620466/forecast-macro`를 연결한다.
4. 주요 파일 또는 저장소 전체를 선택한다.

### 매번 작업이 끝난 뒤

1. Claude Project에서 GitHub **Sync**를 누른다.
2. 아래 짧은 프롬프트를 보낸다.
3. Claude의 검토 답변 전체를 복사해 ChatGPT 대화에 붙여 넣는다.
4. ChatGPT가 검토 내용을 재검산하고 채택할 수정만 GitHub에 반영한다.

## Claude Chat 시작 프롬프트

```text
ChatGPT가 FORECAST MACRO 작업을 완료했어.
GitHub를 최신 상태로 Sync하고 CLAUDE.md와
reviews/FIRST_REVIEW_TASK.md를 읽어줘.

너는 독립 검증자야. 기존 코드가 맞다고 가정하지 말고
데이터 시점, 수학, 확률 합계, 미래정보 누출, 테스트 누락을 검토해줘.
직접 파일을 수정하려 하지 말고, ChatGPT에 전달할 완성된 Markdown
리뷰 보고서만 작성해줘.
```

Claude의 답변을 이 ChatGPT 대화에 그대로 붙이면 된다. 사용자가 변경사항을 설명하거나 파일을 옮길 필요는 없다.

## 첫 검토 대상

- `CLAUDE.md`
- `reviews/FIRST_REVIEW_TASK.md`
- `src/forecast_macro/models/fed.py`
- `src/forecast_macro/models/cpi.py`
- `src/forecast_macro/signals.py`
- `tests/test_models.py`

## 선택 사항: Claude Code

Claude Code를 사용하는 경우 Claude가 별도 브랜치와 Pull Request를 직접 만들 수 있다. 현재 단계에서는 필수 사항이 아니다.

## Buzz는 언제 사용할까?

Buzz는 여러 인간과 AI 에이전트가 같은 방에서 협업하는 무료 오픈소스 플랫폼이다. 그러나 실제 코딩 에이전트를 연결하고 운영할 환경이 필요하므로, 작업량과 에이전트 수가 늘어난 뒤 도입을 재검토한다.

## 현재 협업 루프

1. ChatGPT가 `main`에 설계와 구현을 올린다.
2. 사용자가 Claude Chat에 완료 프롬프트를 보낸다.
3. Claude가 Markdown 검토 보고서를 답변한다.
4. 사용자가 Claude 답변을 ChatGPT에 붙여 넣는다.
5. ChatGPT가 독립 검산 후 리뷰와 수정사항을 GitHub에 반영한다.
6. 최종 결론을 `DECISIONS.md`에 기록한다.
