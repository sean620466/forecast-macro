# 과제 19 응답 — 수수료 모델과 net edge

작성: Claude. 브랜치 `claude/task-19-fees`.

## 출처

- Polymarket: `docs.polymarket.com/polymarket-learn/trading/fees` (2026-09-08 열람). taker fee = C·rate·p·(1−p), Economics rate 0.05, maker 0.
  문서의 예시 표($1.75 at 50c)는 Crypto(0.07) 탭이며 Economics는 $1.25.
- Kalshi: 시리즈 API(`/series/KXFED`)가 `fee_type=quadratic_with_maker_fees`, `fee_multiplier=1`을 보고. 공식 상수는 PDF에 있어 이번에
  읽지 못했고 일반 공식(0.07·p·(1−p), 센트 올림; maker 0.0175)을 `verified=false`로 넣었다.

## 구현

- `fees.py`: `FeeSchedule`(출처 URL, 열람 시각, verified), `taker_fee`, `break_even_probability = ask + fee(ask)`, `net_edge = 모델 확률 − break-even`.
- 어댑터의 `fee_schedule_id`를 실제 값으로 교체. 가격 스냅샷의 각 호가에 `fees`(수수료, 손익분기 확률, 검증 여부) 기록.
- 실업률 비교 기록에 `net_edge_after_fees`. Fed 사다리는 구간이 두 계약의 차이라 rung별 수수료만 기록(R19-M2).

## D-003에 대한 함의

Polymarket Economics에서 50c 계약의 taker 수수료는 1.25%p, 30c는 1.05%p다. 8%p 임계값은 수수료보다 훨씬 크지만, 스프레드(실업률 꼬리 구간
4~5%p)와 합치면 얇은 구간에서는 8%p도 충분하지 않을 수 있다. D-003 재검토는 채점 데이터가 쌓인 뒤로 미룬다.

테스트 164건 통과.
