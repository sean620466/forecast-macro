# ChatGPT–Claude 협업 규칙

이 저장소는 두 AI가 역할을 나눠 작업한다. **ChatGPT는 주 구현자**, **Claude는 독립 검증자**다.
사용자는 내용을 옮기지 않고 "어디에 무엇이 올라갔는지"만 전달한다.

## 원칙

1. **저장소가 유일한 채널이다.** 채팅 내용을 서로에게 복사하지 않는다. 브랜치 이름과 파일 경로만 전달한다.
2. **CI가 최종 심판이다.** 로컬 환경이 달라 결과가 갈리면 GitHub Actions `CI` 워크플로 결과를 기준으로 한다.
3. **산문보다 테스트.** 발견사항은 가능하면 실패하는 테스트로 넘긴다. 테스트 통과가 곧 수정 완료다.
4. **`main` 직접 push 금지(Claude).** Claude는 항상 `claude/<topic>` 브랜치와 Pull Request를 사용한다.
5. **결정은 `DECISIONS.md`에만.** Claude는 리뷰에 `Proposed D-0xx`로 제안하고, 채택은 별도 커밋으로 ChatGPT 또는 사용자가 기록한다.

## 파일 규약

| 목적 | 경로 | 작성자 |
| --- | --- | --- |
| 다음 검토 요청 | `reviews/tasks/NN-<topic>.md` (NN은 두 자리 번호, 가장 큰 번호가 현재 과제) | ChatGPT |
| 검토 보고서 | `reviews/YYYY-MM-DD-<topic>-claude-review-N.md` | Claude |
| 검토 재계산 스크립트 | `reviews/YYYY-MM-DD-review-N-recalc.py` (저장소 import 없이 독립 실행) | Claude |
| 검토 응답 | `reviews/YYYY-MM-DD-review-N-response-chatgpt.md` | ChatGPT |
| 발견사항 장부 | `reviews/FINDINGS.md` | 둘 다 (상태 열만 갱신) |
| 검토 프로토콜 | `reviews/CLAUDE_REVIEW_PROTOCOL.md` | 변경 시 합의 |

기존 `FIRST_REVIEW_TASK.md`, `NEXT_REVIEW_TASK.md`, `THIRD_REVIEW_TASK.md`는 이력으로 남기고 새 과제부터 `reviews/tasks/`를 사용한다.

## 발견사항 ID

`R<리뷰번호>-<등급><순번>` 형식. 예: `R5-C1`은 리뷰 5의 Critical 1번.
`reviews/FINDINGS.md`의 한 행이 한 발견이며 상태는 다음 중 하나다.

- `open` — 미반영
- `fixed` — 반영 커밋 해시 기록
- `partial` — 일부 반영, 남은 범위를 비고에 기록
- `rejected` — 반영하지 않기로 함, 이유를 비고에 기록
- `superseded` — 다른 발견이나 결정으로 대체됨

## 한 사이클

1. ChatGPT가 구현을 `main`에 커밋하고 `reviews/tasks/NN-<topic>.md`를 추가한다.
2. 사용자가 Claude에게 "과제 NN"이라고만 전달한다.
3. Claude는 `main`을 동기화하고, `ruff check .`와 `pytest -q`를 실행하고, 독립 재계산을 한 뒤
   `claude/review-N-<topic>` 브랜치에 보고서 + 재계산 스크립트 + (가능하면) 실패 테스트를 커밋한다.
   `reviews/FINDINGS.md`에 새 행을 `open`으로 추가한다.
4. 사용자가 브랜치를 push하고 PR을 연다. ChatGPT에게 "리뷰 N, 브랜치 X"라고만 전달한다.
5. ChatGPT는 보고서를 읽고 응답 파일을 작성하며, 발견별로 `FINDINGS.md`의 상태를 갱신하고 수정을 `main`에 커밋한다.
   PR은 리뷰 파일만 담고 있으므로 그대로 병합한다.
6. 다음 사이클의 Claude 리뷰는 직전 응답에서 `fixed`로 표시된 항목을 먼저 재검증한다.

## 코드 소유

- `src/`, `scripts/`, `data/`, `docs/` — ChatGPT가 소유한다. Claude가 코드를 고쳐야 하면 별도 `claude/fix-<topic>` 브랜치 PR로 제출하고 ChatGPT가 검토한다.
- `reviews/` — Claude가 소유한다. ChatGPT는 응답 파일과 `FINDINGS.md` 상태 열만 수정한다.
- `tests/` — 둘 다 추가할 수 있다. Claude가 추가한 테스트는 `tests/test_review_<N>.py`에 둔다.
- 같은 파일을 같은 사이클에 둘이 동시에 수정하지 않는다.

## 환경

- 프로젝트는 Python 3.11 이상이 필요하다. Claude가 실행되는 Mac은 uv로 Python을 설치한다:
  `curl -LsSf https://astral.sh/uv/install.sh | sh` 후 `uv venv --python 3.12 && uv pip install -e ".[dev]"`.
- 네트워크가 막힌 환경에서 검토할 경우 보고서에 "실행하지 못한 항목"을 명시하고, 수치는 독립 재구현으로 검산한다.
- 검토 중 외부 API는 **읽기 전용 GET**만 허용한다. API 키는 환경변수로만 전달하고 절대 커밋하지 않는다.

## 사용자가 할 일

- Claude 브랜치 push와 PR 생성 (인증이 필요해서 AI가 대신할 수 없다).
- 두 AI 사이의 한 줄 전달: "과제 NN", "리뷰 N 브랜치 X".
- `DECISIONS.md`의 최종 채택 승인.
