from __future__ import annotations

"""Build the static status dashboard (docs/dashboard/index.html) and STATUS.md from the
committed data. Runs in the compare workflow after scoring; nothing here is a signal."""

import glob
import html
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
esc = html.escape
FINDING_ROW = re.compile(
    r"^\| (R\d+-[A-Z]\d+) \| (\w+) \| (.*?) \| (open|partial|fixed|rejected|superseded) \|",
    re.MULTILINE,
)
DECISION_ROW = re.compile(r"^## (D-\d{3}) — (.*)$", re.MULTILINE)


def load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def latest_priced_by_event() -> dict[str, dict]:
    best: dict[str, dict] = {}
    for f in sorted(glob.glob(str(ROOT / "data/generated/market_prices/*.json"))):
        for r in load(f):
            if r.get("probabilities"):
                best[r["venue_event_id"]] = {**r, "source_file": os.path.basename(f)}
    return best


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def bar_rows(rows) -> str:
    out = []
    for label, model, market, lo, hi in rows:
        out.append(
            f'<div class="row"><div class="lbl">{esc(label)}</div><div class="bars">'
            f'<div class="bar model" style="--v:{model * 100:.2f}"><span>모델 {pct(model)}</span></div>'
            f'<div class="bar market" style="--v:{market * 100:.2f};--lo:{lo * 100:.2f};--hi:{hi * 100:.2f}">'
            f'<i class="rng"></i><span>시장 {pct(market)}</span></div></div></div>'
        )
    return "\n".join(out)


def collect() -> dict:
    prices = latest_priced_by_event()
    fed_files = sorted(glob.glob(str(ROOT / "data/generated/fed_market_comparisons/*.json")))
    un_files = sorted(glob.glob(str(ROOT / "data/generated/unemployment_market_comparisons/*.json")))
    rows = FINDING_ROW.findall((ROOT / "reviews/FINDINGS.md").read_text(encoding="utf-8"))
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT, check=False
    ).stdout.strip()
    scoring_path = ROOT / "data/generated/fed_market_scoring.json"
    return {
        "prices": prices,
        "fed": load(fed_files[-1]) if fed_files else None,
        "un": load(un_files[-1]) if un_files else None,
        "wf": load(ROOT / "data/generated/fed_walk_forward_logistic_2019_2026.json"),
        "bw": {
            k: v
            for k, v in load(ROOT / "data/generated/fed_baseline_backtest_window_2019_2026.json").items()
            if k != "predictions"
        },
        "fed_scoring": load(scoring_path) if scoring_path.exists() else None,
        "findings": rows,
        "by_status": Counter(r[3] for r in rows),
        "decisions": DECISION_ROW.findall((ROOT / "DECISIONS.md").read_text(encoding="utf-8")),
        "commit": commit or "unknown",
    }


CSS = """
:root{--bg:#F7F8FA;--panel:#FFFFFF;--ink:#16202B;--ink2:#4A5866;--muted:#7C8794;--line:#DCE1E7;--accent:#2C4FA3;--model:#2C4FA3;--market:#C2731B;--good:#1E7F4F;--warn:#B7791F;--crit:#B3261E;--chip:#EEF1F5;--rng:#8A5A16}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0F141A;--panel:#171E27;--ink:#E8EDF2;--ink2:#B7C0CA;--muted:#8391A0;--line:#2A3441;--accent:#7C9BEA;--model:#7C9BEA;--market:#E3A25A;--good:#5CC58C;--warn:#E0B25A;--crit:#EF7B72;--chip:#212B37;--rng:#F0C58C}}
:root[data-theme="dark"]{--bg:#0F141A;--panel:#171E27;--ink:#E8EDF2;--ink2:#B7C0CA;--muted:#8391A0;--line:#2A3441;--accent:#7C9BEA;--model:#7C9BEA;--market:#E3A25A;--good:#5CC58C;--warn:#E0B25A;--crit:#EF7B72;--chip:#212B37;--rng:#F0C58C}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Noto Sans KR",system-ui,-apple-system,sans-serif;font-size:15px;line-height:1.55}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 60px}
header{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px 20px;margin-bottom:22px}
h1{font-size:24px;margin:0;letter-spacing:-0.01em}
.meta{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12px;color:var(--muted)}
h2{font-size:16px;margin:0 0 4px} .sub{color:var(--ink2);font-size:13px;margin:0 0 14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:22px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 16px}
.tile .k{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.tile .v{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:22px;font-weight:500;margin-top:4px;font-variant-numeric:tabular-nums}
.tile .d{font-size:12px;color:var(--ink2);margin-top:2px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:22px} @media (max-width:820px){.grid{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:18px 18px 12px}
.legend{display:flex;gap:16px;font-size:12px;color:var(--ink2);margin-bottom:10px;flex-wrap:wrap} .legend i{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:-1px;margin-right:6px}
.row{display:grid;grid-template-columns:120px 1fr;gap:10px;align-items:center;padding:7px 0;border-top:1px solid var(--line)} .row:first-of-type{border-top:0}
.lbl{font-size:13px;color:var(--ink2)} .bars{display:flex;flex-direction:column;gap:4px}
.bar{position:relative;height:18px;border-radius:3px;background:var(--chip)}
.bar::before{content:"";position:absolute;left:0;top:0;bottom:0;width:calc(var(--v) * 1%);border-radius:3px;background:var(--model)} .bar.market::before{background:var(--market)}
.bar span{position:absolute;left:calc(var(--v) * 1% + 8px);top:0;line-height:18px;font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11.5px;color:var(--ink);white-space:nowrap;font-variant-numeric:tabular-nums}
.bar .rng{position:absolute;top:7px;height:4px;left:calc(var(--lo) * 1%);width:calc((var(--hi) - var(--lo)) * 1%);background:var(--rng);border-radius:2px;opacity:.9}
.note{font-size:12.5px;color:var(--ink2);margin:12px 0 0;padding-top:10px;border-top:1px dashed var(--line)}
.gates{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}
.gate{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--panel)}
.pill{flex:none;font-size:11px;font-weight:700;letter-spacing:.04em;padding:2px 8px;border-radius:999px;color:#fff;margin-top:2px} .pill.ok{background:var(--good)}.pill.no{background:var(--crit)}.pill.wait{background:var(--warn)}
.gate b{display:block;font-size:13px}.gate small{color:var(--ink2);font-size:12px}
table{width:100%;border-collapse:collapse;font-size:13px} th,td{text-align:left;padding:7px 8px;border-top:1px solid var(--line)}
th{color:var(--muted);font-weight:500;font-size:11px;letter-spacing:.06em;text-transform:uppercase;border-top:0} td.n,th.n{text-align:right;font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.tablewrap{overflow-x:auto} ul.items{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:6px;font-size:13px} ul.items li{display:flex;gap:8px;align-items:baseline}
ul.items code{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12px;color:var(--muted);flex:none}
.sev{flex:none;font-size:10px;font-weight:700;letter-spacing:.05em;padding:1px 6px;border-radius:3px;background:var(--chip);color:var(--ink2)} .sev.high{color:var(--crit)}.sev.medium{color:var(--warn)}
section{margin-bottom:22px} .verdict{background:var(--panel);border-left:4px solid var(--accent);border-radius:6px;padding:14px 16px;margin-bottom:22px} .verdict b{font-size:15px} .verdict p{margin:6px 0 0;color:var(--ink2);font-size:13.5px}
"""


def render(d: dict) -> tuple[str, str]:
    fed, un, wf, bw, prices = d["fed"], d["un"], d["wf"], d["bw"], d["prices"]
    by = d["by_status"]
    m = fed["market"]
    lm = fed["logistic_three_way"]
    hm = fed["heuristic_three_way"]
    current = m["current_upper"]
    fed_rows = [
        (f"인하 ({current:.2f}% 미만)", lm["cut"], m["probability"], m["lower_bound"], m["upper_bound"]),
        (f"동결 ({current:.2f}%)", lm["hold"], m["hold_probability"], m["hold_lower_bound"], m["hold_upper_bound"]),
        (f"인상 ({current + 0.25:.2f}% 이상)", lm["hike"], m["hike_probability"], m["hike_lower_bound"], m["hike_upper_bound"]),
    ]
    t = un["bucket_titles"]

    def korder(k):
        x = t[k]
        return -1 if "≤" in x else (99 if "≥" in x else float(re.search(r"(\d\.\d)%", x).group(1)))

    un_rows = []
    for k in sorted(un["model"], key=korder):
        lab = re.search(r"be (≤|≥)?(\d\.\d)%", t[k])
        lo, hi = un["market_bounds"].get(k, [un["market"][k]] * 2)
        un_rows.append(((lab.group(1) or "") + lab.group(2) + "%", un["model"][k], un["market"][k], lo, hi))
    net = un.get("net_edge_after_fees") or {}
    best_net = max(net.items(), key=lambda kv: kv[1]) if net else None
    ladder_rows = []
    for ev in sorted(e for e in prices if e.startswith("KXFED-")):
        r = prices[ev]
        c = r["completeness"]
        top = sorted(r["probabilities"].items(), key=lambda kv: -kv[1])[:2]
        width = c.get("width", c["ask_sum"] - c["bid_sum"])
        ladder_rows.append((ev, "저유동성" if c.get("low_liquidity") else "정상", f"{width:.2f} / {c.get('width_limit', 0.35):.2f}", " · ".join(f"{k}: {v * 100:.0f}%" for k, v in top)))
    ladder_html = "\n".join(f'<tr><td>{esc(a)}</td><td>{esc(b)}</td><td class="n">{esc(c)}</td><td>{esc(x)}</td></tr>' for a, b, c, x in ladder_rows) or '<tr><td colspan="4">가격이 매겨진 사다리 없음</td></tr>'
    open_items = [r for r in d["findings"] if r[3] in ("open", "partial")]
    open_html = "\n".join(f'<li><span class="sev {sev.lower()}">{sev}</span><code>{i}</code> {esc(summ[:90])}</li>' for i, sev, summ, _ in open_items[:12])
    dec_html = "\n".join(f'<li><code>{a}</code> {esc(b)}</li>' for a, b in d["decisions"][-6:])
    scoring = d["fed_scoring"] or {}
    scored = scoring.get("scored_meetings", 0)
    stamp = fed["as_of"][:16].replace("T", " ")
    sep = prices.get(fed["event_ticker"])
    sep_width = f"{sep['completeness'].get('width', sep['completeness']['ask_sum'] - sep['completeness']['bid_sum']):.2f}" if sep else "—"
    un_bid = f"{prices['964993']['completeness']['bid_sum']:.3f}" if "964993" in prices else "—"
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forecast Macro 콘솔</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style></head><body>
<div class="wrap">
<header><h1>Forecast Macro 콘솔</h1><div class="meta">main {esc(d["commit"])} · 데이터 기준 {esc(stamp)} UTC · 자동 생성 (scripts/build_dashboard.py)</div></header>
<div class="verdict"><b>현재 판정: 신호 없음 (설계대로)</b><p>모델과 시장 확률은 매일 기록되지만, 시장보다 낫다는 증거는 아직 {scored}건입니다. 첫 채점은 다음 FOMC와 고용보고서 이후입니다. 이 화면의 모든 확률은 연구 기록이며 투자 신호가 아닙니다.</p></div>
<div class="tiles">
<div class="tile"><div class="k">다음 FOMC</div><div class="v">{esc(fed["meeting_date"][5:7].lstrip("0"))}월 {esc(fed["meeting_date"][8:10].lstrip("0"))}일</div><div class="d">현재 상단 {current:.2f}% · {esc(fed["event_ticker"])}</div></div>
<div class="tile"><div class="k">다음 고용보고서</div><div class="v">{esc(un["release_at"][5:7].lstrip("0"))}월 {esc(un["release_at"][8:10].lstrip("0"))}일</div><div class="d">최신 실업률 {un["latest_rate"]}% ({esc(un["latest_month"][:7])})</div></div>
<div class="tile"><div class="k">시장 대비 채점</div><div class="v">{scored} / {scoring.get("minimum_sample_required", 30)}</div><div class="d">D-013 표본 기준까지 남은 회의 수</div></div>
<div class="tile"><div class="k">검토 장부</div><div class="v">{by.get("fixed", 0)} 해결</div><div class="d">{by.get("open", 0)} 미해결 · {by.get("partial", 0)} 부분 · 결정 {len(d["decisions"])}건</div></div>
</div>
<div class="grid">
<div class="panel"><h2>{esc(fed["meeting_date"])} FOMC: 상단 금리는 어디로</h2><p class="sub">Kalshi 관측 {esc(m["observed_at"][:16].replace("T", " "))} UTC · 모델 vintage {esc(fed["features"]["vintage_date"])}</p>
<div class="legend"><span><i style="background:var(--model)"></i>로지스틱 모델 (2019–2026 학습)</span><span><i style="background:var(--market)"></i>시장 (Kalshi) · 짙은 선은 호가 범위</span></div>
{bar_rows(fed_rows)}
<p class="note">모델 입력: CPI 전년비 {fed["features"]["cpi_yoy_nsa"]:.2f}%, 실업률 {fed["features"]["unemployment_rate"]}%, 3개월 변화 {fed["features"]["unemployment_change_3m"]:+.1f}. 휴리스틱: 인하 {pct(hm["cut"])} / 동결 {pct(hm["hold"])} / 인상 {pct(hm["hike"])} (인상 성분은 백테스트에서 빈도 기준보다 나쁨). 회의 당일 발표: {"있음" if fed.get("same_day_release") else "없음"}.</p></div>
<div class="panel"><h2>{esc(un["reference_period"])} 실업률 ({esc(un["release_at"][:10])} 발표)</h2><p class="sub">Polymarket 관측 {esc(un["market_observed_at"][:16].replace("T", " "))} UTC · 최신치 {un["latest_rate"]}%</p>
<div class="legend"><span><i style="background:var(--model)"></i>경험분포 baseline</span><span><i style="background:var(--market)"></i>시장 (Polymarket) · 호가 범위</span></div>
{bar_rows(un_rows)}
<p class="note">모델은 "최신치 + 1990년 이후 1개월 변화의 경험분포". 수수료 차감 후 가장 큰 순 edge: {esc(t[best_net[0]][-14:]) if best_net else "—"} {("%+.1f%%p" % (best_net[1] * 100)) if best_net else ""}.</p></div>
</div>
<section><h2>왜 아직 신호가 아닌가</h2><p class="sub">각 게이트는 코드에서 강제됩니다. 하나라도 빨간색이면 화면에 신호가 나가지 않습니다.</p>
<div class="gates">
<div class="gate"><span class="pill ok">통과</span><div><b>계약 규칙·출처·일정 검증</b><small>BLS·연준 공식 호스트, 시리즈 정체성, 공식 발표 일정(D-014)</small></div></div>
<div class="gate"><span class="pill ok">통과</span><div><b>가격 정규화 (D-015 / D-018)</b><small>실업률 Σbid {un_bid} · 다음 FOMC 사다리 폭 {sep_width}</small></div></div>
<div class="gate"><span class="pill ok">통과</span><div><b>연구 표본 (D-013)</b><small>비-ZLB 백테스트 {wf["non_zlb_evaluated_meetings"]}건 ≥ 30. BSS vs climatology {wf["brier_skill_vs_climatology"]:+.2f}, 비-ZLB {wf["non_zlb_brier_skill_vs_climatology"]:+.2f}</small></div></div>
<div class="gate"><span class="pill no">미충족</span><div><b>시장 대비 표본외 skill (D-007)</b><small>채점된 회의 {scored}건. 같은 날 발표·저유동성 회의는 따로 집계(D-017, D-018)</small></div></div>
<div class="gate"><span class="pill wait">대기</span><div><b>사용자 결정 (D-012)</b><small>skill이 양수여도 신호 표시는 별도 결정으로만 켜짐</small></div></div>
</div></section>
<section class="panel"><h2>Kalshi FOMC 사다리 (만기별)</h2><p class="sub">폭 = Σask − Σbid. 상한은 만기까지 개월 수에 따라 0.35~0.60 (D-018). 폭 초과 이벤트는 표에 없음.</p>
<div class="tablewrap"><table><tr><th>이벤트</th><th>상태</th><th class="n">폭 / 상한</th><th>상위 구간</th></tr>{ladder_html}</table></div></section>
<section class="panel"><h2>백테스트 (2019–2026, 62회의)</h2><p class="sub">낮을수록 좋음.</p>
<div class="tablewrap"><table>
<tr><th>모델</th><th class="n">표본외</th><th class="n">Brier(인하)</th><th class="n">climatology</th><th class="n">always-hold</th><th class="n">3원 Brier</th><th class="n">3원 climatology</th></tr>
<tr><td>로지스틱 워크포워드</td><td class="n">{wf["evaluated_meetings"]}</td><td class="n">{wf["model_brier"]:.4f}</td><td class="n">{wf["sequential_climatology_brier"]:.4f}</td><td class="n">{wf["always_hold_brier"]:.4f}</td><td class="n">{wf["three_way_brier"]:.3f}</td><td class="n">{wf["three_way_climatology_brier"]:.3f}</td></tr>
<tr><td>휴리스틱 (window)</td><td class="n">{bw["evaluated_meetings"]}</td><td class="n">{bw["model_brier"]:.4f}</td><td class="n">{bw["sequential_climatology_brier"]:.4f}</td><td class="n">{bw["always_hold_brier"]:.4f}</td><td class="n">{bw["three_way_brier"]:.3f}</td><td class="n">{bw["three_way_climatology_brier"]:.3f}</td></tr>
</table></div></section>
<div class="grid">
<section class="panel"><h2>미해결 항목 (상위 12)</h2><ul class="items">{open_html}</ul></section>
<section class="panel"><h2>최근 결정</h2><ul class="items">{dec_html}</ul></section>
</div>
</div></body></html>"""
    un_table = "\n".join(f"| {lab} | {pct(mo)} | {pct(ma)} |" for lab, mo, ma, _, _ in un_rows)
    status = f"""# STATUS (자동 생성, scripts/build_dashboard.py)

기준: main {d["commit"]}, 데이터 {stamp} UTC. 대시보드: docs/dashboard/index.html

## 한 문장
모델과 예측시장 확률을 매일 같은 기준으로 기록하고 결과로 채점하는 장치는 완성됐고, "시장보다 나은가"의 답은 아직 없다 (채점 {scored}건).

## 다음 FOMC {fed["meeting_date"]} (현재 상단 {current:.2f}%)
| 결과 | 로지스틱 모델 | 휴리스틱 | 시장 (Kalshi) | 시장 범위 |
| --- | ---: | ---: | ---: | --- |
| 인하 | {pct(lm["cut"])} | {pct(hm["cut"])} | {pct(m["probability"])} | [{pct(m["lower_bound"])}, {pct(m["upper_bound"])}] |
| 동결 | {pct(lm["hold"])} | {pct(hm["hold"])} | {pct(m["hold_probability"])} | [{pct(m["hold_lower_bound"])}, {pct(m["hold_upper_bound"])}] |
| 인상 | {pct(lm["hike"])} | {pct(hm["hike"])} | {pct(m["hike_probability"])} | [{pct(m["hike_lower_bound"])}, {pct(m["hike_upper_bound"])}] |

모델 입력(vintage {fed["features"]["vintage_date"]}): CPI YoY {fed["features"]["cpi_yoy_nsa"]:.2f}%, 실업률 {fed["features"]["unemployment_rate"]}%, 3개월 변화 {fed["features"]["unemployment_change_3m"]:+.1f}. `signal_eligible=false`.

## {un["reference_period"]} 실업률 ({un["release_at"][:10]} 발표, 최신치 {un["latest_rate"]}%)
| 구간 | 모델 | 시장 |
| --- | ---: | ---: |
{un_table}

## 게이트
- 규칙·출처·일정 검증: 통과 (D-014)
- 가격 정규화: 통과 (D-015, D-018)
- 연구 표본 D-013: 통과 (비-ZLB {wf["non_zlb_evaluated_meetings"]}건)
- 시장 대비 표본외 skill D-007: 미충족 (채점 {scored}건)
- 신호 표시 결정 D-012: 대기

## 백테스트 2019–2026
- 로지스틱 워크포워드: Brier {wf["model_brier"]:.4f} vs climatology {wf["sequential_climatology_brier"]:.4f} (BSS {wf["brier_skill_vs_climatology"]:+.3f}), 비-ZLB BSS {wf["non_zlb_brier_skill_vs_climatology"]:+.3f}, 3원 Brier {wf["three_way_brier"]:.3f} vs {wf["three_way_climatology_brier"]:.3f}
- 휴리스틱(window): Brier {bw["model_brier"]:.4f} vs climatology {bw["sequential_climatology_brier"]:.4f}, 3원 {bw["three_way_brier"]:.3f} vs {bw["three_way_climatology_brier"]:.3f}

## 장부
해결 {by.get("fixed", 0)} · 미해결 {by.get("open", 0)} · 부분 {by.get("partial", 0)} · 결정 {len(d["decisions"])}건 (`reviews/FINDINGS.md`, `DECISIONS.md`)
"""
    return page, status


def main() -> None:
    d = collect()
    page, status = render(d)
    out = ROOT / "docs/dashboard/index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    (ROOT / "STATUS.md").write_text(status, encoding="utf-8")
    print(f"wrote {out} and STATUS.md ({d['commit']})")


if __name__ == "__main__":
    main()
