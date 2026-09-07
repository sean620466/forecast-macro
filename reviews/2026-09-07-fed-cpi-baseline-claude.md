## Claude 독립 검토 보고서 — Fed / CPI Baseline

**대상 저장소**: `sean620466/forecast-macro` @ `main` (pushed 2026-09-07 17:10 UTC, 21 commits)

**검토자**: Claude (독립 검증자)

**제출 경로(권장)**: `reviews/2026-09-07-fed-cpi-baseline-claude.md`

**결론**: **FAIL** — 수학은 내부적으로 일관되지만, 이번 과제의 목표인 "백테스트에 적합한 구조"는 아직 아니다. 핵심 원칙(미래정보 누출 방지, vintage 보존)이 문서에만 있고 코드에는 구현되지 않았다.

> 검토 방식 메모: 제 실행 환경은 네트워크가 꺼져 있어 `git clone`, `pytest -q`, `ruff check .`을 **실행하지 못했다**. 대신 GitHub 페이지를 브라우저로 열어 `fed.py`, `cpi.py`, `signals.py`, `fred.py`, `types.py`, `cli.py`, `tests/test_models.py`, `CLAUDE.md`, `FIRST_REVIEW_TASK.md`, `DECISIONS.md`, `ARCHITECTURE.md`, `docs/DATA_SOURCES.md`를 전문 정독했다. `README.md`, `pyproject.toml`, `CLAUDE_REVIEW_PROTOCOL.md` 후반부, `docs/CLAUDE_SETUP.md`는 읽지 못했다. 아래 수치 검산은 손으로 했다.

---

### 1. 발견사항 요약

| 등급#발견파일      |     |                                                                                              |                            |
| ------------ | --- | -------------------------------------------------------------------------------------------- | -------------------------- |
| **Critical** | C-1 | FRED 클라이언트가 최신 **수정치(revised)** 만 반환 — `realtime_start/end`(ALFRED vintage) 미사용              | `data/fred.py`             |
| **Critical** | C-2 | `released_at`이 어디에서도 채워지지 않음 → 누출 방지 원칙이 구현되지 않음                                             | `data/fred.py`, `types.py` |
| **High**     | H-1 | `observed_at`에 기준기간(reference period) 날짜를 넣어 "그 시점에 알 수 있었던 값"처럼 취급                          | `data/fred.py`             |
| **High**     | H-2 | CPI: `lower_cutoff >= upper_cutoff`일 때 예외 없이 정규화로 조용히 통과                                     | `models/cpi.py`            |
| **High**     | H-3 | Fed 결과공간이 `cut / hold_or_hike` 2분류 — 실제 계약(인상·동결·25bp·50bp+)과 불일치, 회의 날짜(`meeting_date`)도 없음 | `models/fed.py`            |
| **High**     | H-4 | FRED → 모델 특징 변환 코드(YoY, 3개월 변화)가 없음. CPI `forecast_mom`을 계산하는 모델도 없음                         | 전체                         |
| **Medium**   | M-1 | 계수 5개 전부 수기 지정, 캘리브레이션·Brier·baseline 비교 없음                                                  | `models/fed.py`            |
| **Medium**   | M-2 | `inflation_yoy` 정의 미상 (CPI vs Core PCE). Fed 목표 2.0%는 PCE 기준                                 | `models/fed.py`            |
| **Medium**   | M-3 | CPI `uncertainty=0.12` 고정 — 발표까지 남은 기간·에너지 변동성 무시, 정규분포 가정                                   | `models/cpi.py`            |
| **Medium**   | M-4 | 시장 확률에 수수료(vig) 제거 없음, YES+NO ≈ 1 검증 없음, 절대 8pp 임계값은 꼬리 확률에서 잘못 작동                           | `signals.py`, `cli.py`     |
| **Medium**   | M-5 | 출력에 모델 버전·입력 스냅샷·계산시각 없음 (ARCHITECTURE 요구)                                                   | `cli.py`                   |
| **Medium**   | M-6 | `fetched_at`, `source`, `vintage` 필드 미구현 (DATA\_SOURCES 데이터 계약 위반)                           | `types.py`                 |
| **Low**      | L-1 | `round(cut,6)` + `round(hold,6)`가 1.000001이 될 수 있음                                           | `models/fed.py`            |
| **Low**      | L-2 | `_sigmoid`가 `value < -709`에서 `OverflowError`                                                 | `models/fed.py`            |
| **Low**      | L-3 | 최신 관측이 `"."`이면 이전 값으로 후퇴하지 않고 실패                                                             | `data/fred.py`             |
| **Low**      | L-4 | 재시도·백오프 없음; API 키가 쿼리 파라미터로 전송되므로 로깅 시 마스킹 필요                                                | `data/fred.py`             |

---

### 2. Fed 모델 — 계수 방향 검토 (`models/fed.py`)

```
score = -0.9·(inflation_yoy − 2.0)
      + 1.2·unemployment_change_3m
      + 0.35·(unemployment_rate − 4.0)
      + 0.25·(policy_rate − neutral_rate[2.75])
      − 0.5
P(cut) = σ(score)
```

| 항부호경제적 타당성판정 |   |                             |                                  |
| ------------ | - | --------------------------- | -------------------------------- |
| 인플레이션 − 2.0  | − | 물가↑ → 인하↓                   | ✅                                |
| 실업률 3개월 변화   | + | 실업 상승 → 인하↑ (Sahm 규칙 방향)    | ✅                                |
| 실업률 − 4.0    | + | 실업 수준↑ → 인하↑                | ✅                                |
| 정책금리 − 중립금리  | + | 제약적일수록 인하 여지↑               | ✅ 방향은 타당, 단 "여지"와 "의지"를 혼동할 수 있음 |
| 절편 −0.5      | — | 중립 상태 기본 인하확률 σ(−0.5)=37.8% | 근거 없음, 캘리브레이션 필요                 |

**검산**: 테스트 입력 (2.5, 4.2, 0.2, 4.5) → score = −0.45 + 0.24 + 0.07 + 0.4375 − 0.5 = **−0.2025** → P(cut) = **0.4496**, P(hold) = 0.5504. 합 = 1.0000 ✅.

두 번째 테스트 (2.0, 4.5, 0.5, 5.0) → score = 0 + 0.6 + 0.175 + 0.5625 − 0.5 = **0.8375** → P(cut) = **0.698**. 시장 0.10 대비 edge +0.598 → 표시됨 ✅ (테스트 통과 예상).

**문제**

- **H-3**: Kalshi Fed 계약은 회의별·결과별(인상 / 동결 / 25bp 인하 / 50bp+ 인하)로 갈린다. `hold_or_hike`로 인상을 동결에 합치면 계약 정의와 불일치하며, 인상 확률이 유의미한 국면에서 신호가 왜곡된다. `meeting_date`와 `as_of` 없이는 "어느 회의의 인하인가"가 정의되지 않는다.
- **M-1**: 계수는 전부 수기. docstring이 이를 인정하지만, 이 상태에서 `signals.py`가 시장 대비 edge를 계산해 "표시"까지 하는 것은 위험하다. 캘리브레이션 전에는 신호 게이트를 강제 비활성화하거나 `model_version="uncalibrated"`를 출력에 박아야 한다.
- **M-2**: `inflation_yoy`가 CPI인지 Core PCE인지 미정의. 2.0 목표는 PCE 기준이며 CPI는 구조적으로 0.3\~0.5pp 높다. 입력을 CPI로 넣으면 인하확률이 체계적으로 낮아진다.
- **L-1**: `round()`를 독립 적용하면 합이 1e-6 어긋날 수 있다. `hold = round(1 − cut_rounded, 6)`로 고치거나 반올림을 제거.
- **L-2**: 극단 입력에서 `math.exp` 오버플로. `score`를 ±500으로 클램프.

---

### 3. CPI 모델 — 경계값·합계 독립 계산 (`models/cpi.py`)

```
below = Φ(lower; μ, σ)
upper_cdf = Φ(upper; μ, σ)
middle = max(0, upper_cdf − below)
above = max(0, 1 − upper_cdf)
→ total로 정규화
```

**독립 계산 (기본값 μ=0.25, σ=0.12, lower=0.15, upper=0.35)**

- z\_low = (0.15−0.25)/0.12 = −0.8333 → Φ = **0.2023**
- z\_up = (0.35−0.25)/0.12 = +0.8333 → Φ = **0.7977**
- below = 0.2023, in\_range = 0.5953, above = 0.2023, **합 = 1.0000** ✅ (대칭 케이스이므로 양 꼬리가 같아야 하며, 같다)

**수학적 판정**: 클램프가 발동하지 않는 정상 입력에서 `below + middle + above = Φ(l) + (Φ(u) − Φ(l)) + (1 − Φ(u)) = 1`이 항등식이라 정규화는 사실상 무해하다. 문제는 그 정규화가 **버그를 숨긴다**는 점이다.

**H-2**: `lower_cutoff > upper_cutoff`를 넣으면 `middle`이 0으로 클램프되고 `total = Φ(l) + 1 − Φ(u) > 1`이 되어 조용히 재정규화된다. 예외를 던져야 한다. 현재 테스트는 이 경로를 전혀 건드리지 않는다.

**경계 의미론 (Medium, 문서화 필요)**: BLS는 MoM을 0.1pp로 반올림해 발표한다. 따라서 `[0.15, 0.35)`는 "발표치가 0.2% 또는 0.3%"에 대응하고, 0.15/0.35 컷오프 선택은 이 해석 아래서만 옳다. 이 매핑을 코드 주석과 테스트로 고정해야 한다. 엄밀히는 반올림이 지수 수준(소수 3자리)에서 일어나 경계가 정확히 0.15가 아니지만 영향은 미미하다.

**M-3**: σ=0.12는 역사적 컨센서스 오차와 비슷한 크기라 출발점으로는 무리 없으나, 발표까지 남은 일수·에너지 가격 변동에 따라 달라져야 하고, CPI MoM은 꼬리가 두껍다. 최소한 σ를 입력 데이터로 추정하는 경로가 필요하다.

**H-4**: `forecast_mom`을 산출하는 코드가 없다. 현재 CPI "모델"은 외부에서 주어진 숫자에 정규분포를 씌우는 래퍼이며 `cli.py`에도 연결되지 않았다.

---

### 4. 미래정보 누출 및 FRED 수정치 위험 (`data/fred.py`, `types.py`)

이 항목이 FAIL의 근거다.

**C-1 — 수정치만 반환**: `FredClient.latest()`는 `/fred/series/observations`에 `sort_order=desc, limit=1`만 보낸다. `realtime_start`/`realtime_end`(또는 `vintage_dates`)를 지정하지 않으면 FRED는 **현재 vintage**, 즉 모든 사후 수정이 반영된 값을 돌려준다. 실업률·고용·CPI 계절조정계수는 모두 수정된다. 이 클라이언트로 과거 시점 입력을 만들면 백테스트가 자동으로 미래를 본다.

→ 수정: `as_of: date` 파라미터를 받아 `realtime_start = realtime_end = as_of`로 요청하고, 응답의 `realtime_start`를 `vintage`로 저장.

**C-2 —** **`released_at`** **미구현**: `Observation.released_at`은 선택 필드이고 `fred.py`는 채우지 않는다. ARCHITECTURE의 "모든 입력에 `observed_at`과 `released_at`을 기록"이 실행되지 않는다. 백테스트 모드에서는 `released_at`이 None인 관측을 **거부**해야 한다.

→ 수정: FRED `/fred/release/dates` 또는 ALFRED `realtime_start`로 공개시점을 얻어 채움.

**H-1 —** **`observed_at`** **의미 오류**: `row["date"]`는 기준기간(예: 8월 CPI = `2026-08-01`)이다. 실제 공개는 9월 중순이다. 이를 UTC 자정 시각으로 저장하면 하류에서 "8월 1일에 알 수 있었던 값"으로 오해할 구조다.

**M-6**: `fetched_at`, `source`, `vintage`가 타입에 없다. DATA\_SOURCES.md의 데이터 계약을 코드가 충족하지 못한다.

**L-3**: 최신 행이 `"."`이면 예외. 실제로 FRED에는 미발표 기간 placeholder가 흔하므로 유효 행까지 순회해야 한다.

---

### 5. 신호 레이어 (`signals.py`, `cli.py`)

- 로직 자체(`edge = model − market`, 키 존재·범위 검증)는 정확하다.
- **M-4**: 시장 확률을 호가 그대로 쓴다. Kalshi YES+NO 합은 1이 아니며 수수료가 있다. `cli.py`는 `hold = 1 − market_cut`으로 보완을 가정한다. 최소한 (a) YES/NO 합 검증, (b) 수수료 조정 edge, (c) 절대 8pp 대신 로그오즈 또는 수수료 대비 상대 기준을 검토해야 한다. D-003이 Provisional인 것은 적절하다.
- **M-5**: 출력 JSON에 입력값·모델 버전·계산시각·데이터 vintage가 없다. 재현성 요구 미충족.

---

### 6. 빠진 테스트 (제안)

현재 3개 테스트는 전부 정상 경로다. 추가 제안:

**Fed**

1. 단조성: 다른 입력 고정 시 `inflation_yoy`↑ → P(cut)↓, `unemployment_change_3m`↑ → P(cut)↑, `unemployment_rate`↑ → ↑, `policy_rate`↑ → ↑
2. 극단 입력(±1e3, ±1e6)에서 예외 없이 [0,1] 반환 (L-2 회귀 테스트)
3. `cut + hold == 1.0` **정확히** (또는 허용오차 명시) — L-1
4. NaN 입력 시 `ValueError` (types.py 검증 경로 확인)

**CPI**

5\. `lower_cutoff >= upper_cutoff` → `ValueError` (H-2)

6\. `uncertainty <= 0` → `ValueError` (코드에 있으나 미테스트)

7\. 대칭 케이스 양 꼬리 동일 (0.2023 ≈ 0.2023)

8\. 극단: `forecast_mom = −5` → below ≈ 1; `= +5` → above ≈ 1

9\. 경계 해석 고정: 발표 반올림 0.2/0.3 ↔ `[0.15, 0.35)` 문서화 테스트

**signals**

10\. 시장 키 누락 → `KeyError`; 범위 밖 → `ValueError`

11\. `threshold=0` → 전부 표시; edge 부호 검증

12\. YES+NO 합이 1에서 크게 벗어날 때 경고/예외 (M-4 구현 후)

**fred (httpx 모킹)**

13\. `"."` 처리, 빈 `observations`, 4xx/5xx

14\. **요청에** **`realtime_start`****/****`realtime_end`****가 포함되는지 단언** (C-1 회귀 테스트)

15\. ALFRED vintage 픽스처로 "as\_of 시점에 알려진 값"이 반환되는지 — 누출 방지의 핵심 테스트

16\. `released_at`이 None인 관측을 백테스트 모드가 거부하는지 (C-2)

---

### 7. 결론과 다음 단계

**FAIL** — 근거: C-1, C-2, H-1. 수식과 확률 합계는 통과했고(위 검산), 계수 방향도 모두 타당하다. 그러나 저장소의 1번 원칙인 누출 방지가 코드에 존재하지 않으며, 현재 데이터 클라이언트로는 어떤 백테스트도 신뢰할 수 없다. 이 상태로 `signals.py`가 "표시" 판정을 내리는 것은 위험하다.

**ChatGPT에 요청할 작업 순서**

1. `FredClient`에 `as_of` + ALFRED realtime 파라미터, `released_at`·`fetched_at`·`vintage` 채우기 (C-1, C-2, H-1, M-6)
2. `cpi_bucket_probabilities`에 `lower < upper` 검증 (H-2)
3. Fed 결과공간을 계약 정의에 맞게 확장하고 `meeting_date`/`as_of` 추가 (H-3)
4. FRED → 특징(YoY, 3m 변화) 변환 모듈과 CPI `forecast_mom` 산출 경로 (H-4)
5. 출력에 `model_version`, 입력 스냅샷, `computed_at`, 데이터 vintage (M-5)
6. 위 16개 테스트 추가; 캘리브레이션 전까지 `signals` 표시를 `dry_run` 기본값으로

**DECISIONS.md 제안**: D-005 "캘리브레이션 완료 전 신호 표시 금지" (Accepted), D-006 "모든 백테스트 입력은 ALFRED vintage 필수" (Accepted).

---

*참고: 이 검토는 클론·테스트 실행 없이 소스 정독과 수기 검산으로 수행했다. ChatGPT가 수정 후* *`pytest -q`**와* *`ruff check .`* *결과를 첨부하면 다음 사이클에서 검산한다. 브라우저 탭(github.com)이 열린 채로 남아 있으니 닫아주시면 된다.*

[image](/images/install-hub/claude_code_desktop-icon.svg)[image](/images/install-hub/claude_code_desktop-icon-dark.svg)Claude Code에서 계속하기

Claude가 이번 차례의 도구 사용 한도에 도달했습니다.

svg