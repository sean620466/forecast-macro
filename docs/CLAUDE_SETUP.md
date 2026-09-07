# Connect Claude to FORECAST MACRO

## 권장 방식: Claude Code on the web

Claude Code 웹에서 GitHub 저장소를 선택하고 작업을 요청하면 Claude가 원격 환경에서 코드를 검토한 뒤 Pull Request를 만들 수 있다.

1. Claude Code 웹을 연다.
2. GitHub 계정을 연결한다.
3. `sean620466/forecast-macro` 저장소를 선택한다.
4. 저장소 접근 요청이 나오면 Claude GitHub App에 이 저장소를 허용한다.
5. 아래 프롬프트를 붙여 넣는다.
6. Claude가 만든 PR을 바로 merge하지 말고 ChatGPT 검토를 거친다.

## 읽기 전용 대안: Claude Project

Claude Project의 Project knowledge 오른쪽 위 `+`에서 GitHub를 선택하고 저장소와 필요한 파일을 추가한다. 이 방식은 분석 대화에 적합하다. 저장소 변경 후에는 Sync를 눌러 최신 파일을 다시 가져온다.

## 시작 프롬프트

```text
Open sean620466/forecast-macro and follow CLAUDE.md exactly.
Complete reviews/FIRST_REVIEW_TASK.md.

Act as an independent validator. Do not modify the existing model code first.
Run the tests and Ruff, write your findings to
reviews/2026-09-07-fed-cpi-baseline-claude.md on a new branch named
claude/review-fed-cpi-baseline, and open a pull request titled
"Claude review: Fed and CPI baseline".

Do not merge the pull request and do not modify Accepted decisions in DECISIONS.md.
```

## 협업 루프

1. ChatGPT가 `main`에 설계와 구현을 올린다.
2. Claude가 별도 브랜치에서 독립 검산 PR을 만든다.
3. 사용자가 PR 링크를 ChatGPT에 알려준다.
4. ChatGPT가 발견사항과 계산을 재검토한다.
5. 채택할 수정만 별도 커밋으로 반영한다.
6. 결론을 `DECISIONS.md`에 기록한다.
