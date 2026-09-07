## Claude 독립 검토 보고서 #4 — 확장 Fed 백테스트 (2019–2024) 및 point-in-time 파이프라인

**대상**: `forecast-macro-main.zip` (main 스냅샷, 2026-09-07) — `src/forecast_macro/fed_backtest.py`, `snapshots.py`, `datasets.py`, `fomc.py`, `scripts/*.py`, `data/fomc_meetings_2019_2024.csv`, `data/generated/*.json`, `docs/EXTENDED_BACKTEST.md`

**검토자**: Claude (독립 검증자)

**제출 경로(권장)**: `reviews/2026-09-07-extended-backtest-claude-review-4.md`

**결론**: **PASS WITH CHANGES** — 파이프라인·데이터·수치는 정확하게 재현된다(미래정보 누출 0건, 49개 FOMC 행 전부 실제 결정과 일치, Brier/BSS 소수점 6자리까지 일치). 그러나 `EXTENDED_BACKTEST.md`의 **해석**은 틀렸다. 모델이 climatology에 진 이유는 "단순 고정형 모델의 skill 부족"이 아니라, **모델이 제로금리 하한(ZLB)을 모른다**는 구조적 결함 하나 때문이다. 표본외 41건 중 16건이 상단 0.25% 상태였고, 이 16건에서 모델 오차 제곱합 2.644가 전체 5.811의 **45%** 를 차지한다. 이 결함을 고치지 않고 다음 모델링을 진행하면 방향을 잘못 잡게 된다.

> 검토 방식 메모: 이번에는 저장소를 로컬에 풀어 **`ruff check .`** **→ All checks passed,** **`pytest -q`** **→ 54 passed**를 직접 실행했다. 단, 샌드박스에서 PyPI 접근이 막혀 `httpx`를 설치할 수 없어 `tests/test_historical_pipeline.py`의 monkeypatch가 요구하는 최소 인터페이스(`Request`, `Response`, `get`)만 가진 오프라인 shim으로 대체했다. 네트워크 호출 코드(`alfred.py`, `fred.py`)의 실제 HTTP 동작은 검증 대상에서 제외한다. 모든 수치는 저장소의 JSON에서 독립 스크립트로 재계산했다.

---

### 1. 발견사항 요약

| 등급 # 발견 파일   |     |                                                                                                                                                                                |                                                   |
| ------------ | --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------- |
| **Critical** | C-1 | 모델에 ZLB 제약이 없음. 상단 0.25%에서 `P(cut)=1.0`(2020-06, 2020-07) 등 16건의 불가능한 예측이 Brier 손실의 45%를 만들고, 문서의 "모델 skill 없음" 결론을 왜곡함                                                        | `models/fed.py`, `docs/EXTENDED_BACKTEST.md`      |
| **High**     | H-1 | `round(sigmoid, 6)`이 정확히 `1.0`/`0.0`을 반환 → log loss가 정의되지 않음(BACKTEST\_PLAN이 요구하는 지표). 실제 데이터에서 2건 발생                                                                          | `models/fed.py`                                   |
| **High**     | H-2 | 이벤트 정의가 예측시장 계약과 불일치. `all` 스코프는 "긴급회의가 열릴 것"을 사후에 아는 선택편향(긴급회의 = 거의 항상 행동), `scheduled` 스코프는 2020년 3월 −150bp를 조용히 증발시킴. 계약은 "회의일 이후 상단 금리"로 정산되므로 **정기회의 간 창(window) 라벨**이 필요 | `datasets.py`, `fed_backtest.py`                  |
| **Medium**   | M-1 | `signal_eligible`이 climatology 대비로만 계산됨. D-007은 **시장가격 baseline** 대비 BSS>0을 요구하므로 이름이 오해를 부름                                                                                   | `fed_backtest.py`                                 |
| **Medium**   | M-2 | "always hold(p=0)" baseline이 없음. 이 naive baseline(all 0.1220 / scheduled 0.0769)이 climatology와 모델 둘 다 이김 — 저빈도 이벤트에서 Brier 해석에 필수                                              | `fed_backtest.py`                                 |
| **Medium**   | M-3 | 스냅샷에 재현성 메타데이터 부재: `fetched_at`, 각 입력의 관측월(`observation month`)·`realtime_start`, 응답 해시, 모델 버전 없음 (프로토콜 6항)                                                                    | `snapshots.py`, `scripts/build_fomc_snapshots.py` |
| **Medium**   | M-4 | 전일(vintage = D−1) cutoff는 누출은 막지만 **결정 당일 08:30 ET 발표**(예: 2024-06-12 CPI)를 배제 → 시장은 그 정보를 가진 채 가격을 매기므로 시장 비교 시 불공정. 시점 정렬 규칙 필요                                              | `snapshots.py`, `fed_backtest.py`                 |
| **Low**      | L-1 | `source` 열 41/49행이 범용 페이지(`fomccalendars.htm` 34행, `fomchistorical2019.htm` 7행) — 결정별 보도자료 URL(`monetaryYYYYMMDDa.htm`)이 아니면 추적성 원칙(D-002) 미충족. 검증기는 접두사만 확인                   | `data/fomc_meetings_2019_2024.csv`, `datasets.py` |
| **Low**      | L-2 | `scheduled` 스코프에서 필터링 후 연속성(`upper_after == 다음 upper_before`) 검증이 없음. 현재는 `policy_rate == upper_before` 검사가 우연히 막아줌                                                            | `scripts/run_fed_backtest.py`                     |
| **Low**      | L-3 | `ForecastRecord.forecast_at = vintage_date 23:59 UTC`는 실제 정보 cutoff(vintage일 종료, ET)와 다른 인위적 시각. 문서화 필요                                                                        | `fed_backtest.py`                                 |
| **Low**      | L-4 | 테스트 공백: ZLB 케이스, 생성 JSON 회귀 테스트(재계산 일치), 확률 0/1 금지, `scheduled` 스코프 연속성                                                                                                        | `tests/`                                          |

---

### 2. 재현 단계

```bash
unzip forecast-macro-main.zip && cd forecast-macro-main
ruff check .          # All checks passed!
pytest -q             # 54 passed (httpx 오프라인 shim 사용)

```

독립 재계산(모델식·Laplace baseline·Brier·BSS를 처음부터 다시 구현):

| 스코프 n 모델 Brier climatology BSS 문서/JSON 값 예측별 불일치  |    |          |          |           |    |        |
| ------------------------------------------------- | -- | -------- | -------- | --------- | -- | ------ |
| all                                               | 41 | 0.141745 | 0.127604 | −0.110820 | 동일 | 0 / 41 |
| scheduled                                         | 39 | 0.116812 | 0.095612 | −0.221731 | 동일 | 0 / 39 |

JSON에 기록된 `probability_cut`, `baseline_probability_cut`, `actual_cut` 전부 소수점 9자리까지 일치. `constant_50_brier = 0.25`도 일치.

---

### 3. 데이터 시점·누출 검토 (프로토콜 1, 2, 7항)

**FOMC 데이터셋 (49행)** — 2019-01-30 \~ 2024-12-18의 모든 결정(정기 47 + 긴급 2)을 실제 결정과 대조했다. 인하 8건(2019-07/09/10, 2020-03-03 −50, 2020-03-15 −100, 2024-09 −50, 2024-11/12 −25), 인상 11건(2022-03 \~ 2023-07), 취소된 2020-03-18 정기회의는 올바르게 없음, 긴급 결정 시각(10:00 / 17:00 ET)도 정확. **오류 0건.**

**Point-in-time 스냅샷 (49건)** — 표본 검증:

| vintage 입력 스냅샷 값 당시 실제 발표치 판정  |                                  |             |                                   |                  |
| ------------------------------ | -------------------------------- | ----------- | --------------------------------- | ---------------- |
| 2020-04-28                     | UNRATE 2020-03                   | 4.4         | 첫 발표 4.4                          | ✓                |
| 2020-06-09                     | UNRATE 2020-05 / CPI YoY 2020-04 | 13.3 / 0.33 | 13.3 / 0.3 (5월 CPI는 6/10 발표 → 제외) | ✓ 누출 없음          |
| 2021-12-14                     | UNRATE 2021-11                   | 4.2         | 첫 발표 4.2 (이후 개정)                  | ✓ vintage 보존     |
| 2022-07-26                     | CPI YoY 2022-06                  | 9.06        | 9.1                               | ✓                |
| 2024-06-11                     | CPI YoY 2024-04                  | 3.36        | 3.4 (5월 CPI는 회의 당일 08:30 발표 → 제외) | ✓ 누출 없음 (M-4 참고) |
| 2024-12-17                     | UNRATE 2024-11 / 3m Δ            | 4.2 / 0.0   | 4.2 / 4.2−4.2                     | ✓                |

`policy_rate_upper == upper_before`는 49/49 일치(백테스트가 런타임에 강제). 미래정보 누출 **0건**.

---

### 4. C-1 상세 — ZLB 결함이 결과를 지배한다

모델식은 `policy_rate`를 선형항(+0.25·(r − 2.75))으로만 쓴다. 2020-06-10 스냅샷(실업률 13.3, 3개월 변화 +9.8)에서 score ≈ +12.6 → `P(cut)=1.000000`. 그러나 상단이 0.25%이면 인하는 정책상 불가능(연준은 마이너스 금리를 배제)했고, 시장 계약에서도 "cut" 결과는 사실상 0에 거래됐다.

| 스코프 원 모델 ZLB 마스크 모델\* climatology always-hold BSS(원) BSS(마스크, vs clim) BSS(마스크, vs always-hold)  |        |        |        |        |        |            |        |
| ------------------------------------------------------------------------------------------------ | ------ | ------ | ------ | ------ | ------ | ---------- | ------ |
| all (n=41)                                                                                       | 0.1417 | 0.0773 | 0.1276 | 0.1220 | −0.111 | **+0.394** | +0.366 |
| scheduled (n=39)                                                                                 | 0.1168 | 0.0490 | 0.0956 | 0.0769 | −0.222 | **+0.487** | +0.363 |

\* 상단 ≤ 0.25%일 때 `P(cut)=0.005`로 대체한 것 외에는 동일.

**주의 — 이 표는 채택 근거가 아니라 진단이다.** 테스트 표본을 본 뒤 규칙을 추가하는 것은 사후 조정(look-ahead)이다. 올바른 절차는:

1. ZLB 제약을 **데이터와 무관한 구조적 사전 지식**으로 `DECISIONS.md`에 먼저 등록(제안 D-011: "상단 ≤ 0.25%인 회의에서 인하 확률은 ε으로 고정하며, ε은 캘리브레이션 대상이 아니다").
2. 그 다음 재실행하고, 문서에는 "ZLB 회의 16건 제외 시 유효 표본 n=25(all)/23(scheduled)로 D-007의 30건 미달"임을 명시.
3. 마스크 후 우위가 2024년 3회 인하 예측(0.505 / 0.368 / 0.353 vs climatology \~0.1)에 집중돼 있음을 함께 보고. 이벤트 3개로 skill을 주장할 수 없다.

즉 결론은 여전히 "신호 불가"지만, **다음 단계는 "모델식 개선"이 아니라 "실현 가능 결과공간 제약 + 시장 baseline 확보"** 여야 한다.

---

### 5. H-2 상세 — 이벤트 정의를 계약에 맞춰라

현재 두 스코프 모두 계약 정산과 다르다.

- `all`: 2020-03-03, 03-15 행은 "긴급회의가 열렸다"는 사실 자체가 사후 정보. 긴급회의의 인하율은 \~100%이므로 모델은 구조적으로 이 이벤트를 맞힐 수 없고, 넣으면 Brier가 왜곡된다.
- `scheduled`: 2020-01-29(1.75) → 2020-04-29(0.25)로 건너뛰며 −150bp가 "hold"로 기록된다. 예측시장의 "3월 회의 후 상단 금리" 계약이었다면 0.25로 정산됐을 사건이 사라진다.

**제안**: 세 번째 스코프 `window` — 라벨 = 직전 정기 결정의 `upper_after` 대비 이번 정기 결정의 `upper_after` 변화. 2020년은 "1/29 이후 \~ 4/29까지 창"에서 −150 = cut. 이것이 Kalshi/Polymarket 금리 계약(회의일 기준 target range)의 정산 규칙과 일치하며, 긴급 행동을 버리지도 오염시키지도 않는다. 취소된 2020-03-18 회의는 예정 캘린더에 있었으므로 창의 경계로 별도 처리(계약이 그 날짜로 존재했는지 확인 필요).

---

### 6. 수학·구현 검산 (프로토콜 3, 4항)

- Brier: `Σ(p−y)²/n` ✓. BSS: `1 − model/baseline` ✓. Laplace baseline `(prior_cuts+1)/(index+2)`에서 `index`가 warmup 포함 누적 회의 수이므로 분모가 맞음 ✓.
- ECE(bins=5, n=41) = 0.0862 재현 ✓. 다만 5-bin ECE는 41건에서 통계적 의미가 약함 — 보조 지표로만.
- `signal_eligible = n ≥ 30 and model < climatology` — climatology 게이트로는 맞지만 D-007(시장 대비)의 구현은 아님(M-1). 필드명을 `passes_climatology_gate`로 바꾸고 `signal_eligible`은 시장 baseline 입력 전까지 항상 `False`로 두는 것을 권장.
- `_monthly_tail`의 월 연속성 검사, `_latest`의 observed\_at ≤ vintage 필터 ✓. `unemployment_change_3m = tail[-1] − tail[0]` (4개 → 3개월 차) ✓ 동일 vintage ✓.
- 확률 범위: 모든 p ∈ [0, 1] ✓, 합계 1 ✓. 단 H-1대로 정확히 0/1이 2건 존재(2020-06-10, 07-29) → `log(1−p)` 불능. `round` 제거 또는 `[1e-6, 1−1e-6]` 클리핑 필요.

---

### 7. 요구 변경사항 (우선순위순)

1. **(C-1)** `DECISIONS.md`에 ZLB 제약을 사전 등록한 뒤 `fed.py`에 실현 가능성 마스크 추가. `EXTENDED_BACKTEST.md`의 해석 문단을 "ZLB 결함이 결과를 지배; 제약 후 유효 표본 부족"으로 교체.
2. **(H-1)** 확률 클리핑, `round` 제거. `test_models.py`에 "p ∉ {0,1}" 테스트.
3. **(H-2)** `window` 스코프 구현, 세 스코프 결과를 한 표에 병기.
4. **(M-2)** `always_hold_brier` 필드와 BSS 추가.
5. **(M-1)** `signal_eligible` 의미 분리.
6. **(M-3)** 스냅샷에 `fetched_at`, 입력별 `observation_month`, `realtime_start`, 모델 버전, 스크립트 커밋 해시 저장.
7. **(M-4)** 시장 비교 단계 전에 "forecast cutoff = 시장 관측시각" 정렬 규칙을 결정으로 등록(전일 vintage는 시장이 아는 당일 08:30 발표를 모름).
8. **(L-1)** CSV `source`를 결정별 보도자료 URL로 교체, 검증기에 `monetaryYYYYMMDDa.htm` 패턴 검사 추가.
9. **(L-4)** 회귀 테스트: 체크인된 JSON을 재계산해 일치 확인, `scheduled` 스코프 연속성 테스트.

---

### 8. 잔여 리스크

- ALFRED 응답의 실제 HTTP 동작·429 재시도는 이번에 실행 검증하지 못했다(오프라인). GitHub Actions run `34155616512` 아티팩트도 확인하지 않았다.
- CPI 발표시각을 날짜 단위 vintage로만 다룬다. 회의 당일 발표를 포함하려면 발표 timestamp 테이블(이미 ChatGPT 보류 항목)이 선행돼야 한다.
- 6년 표본에 완전한 금리 사이클이 1개뿐이다. 어떤 스코프에서도 "시장보다 낫다"는 주장은 2025–2026 결정과 시장가격이 들어오기 전까지 불가능하다.
- 모델의 2024년 인하 예측 우위는 3건에 의존한다. D-007의 30건 기준을 "ZLB 제외 유효 표본 30건"으로 강화할지 결정이 필요하다.
