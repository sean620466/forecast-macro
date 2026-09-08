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
        "fed_files": fed_files,
        "price_files": sorted(glob.glob(str(ROOT / "data/generated/market_prices/*.json"))),
        "bw_predictions": load(ROOT / "data/generated/fed_baseline_backtest_window_2019_2026.json")["predictions"],
        "snapshots": load(ROOT / "data/generated/fomc_feature_snapshots_2019_2026.json"),
        "findings": rows,
        "by_status": Counter(r[3] for r in rows),
        "decisions": DECISION_ROW.findall((ROOT / "DECISIONS.md").read_text(encoding="utf-8")),
        "commit": commit or "unknown",
    }


CSS = """
:root{--cut:#1B8A8F;--hold:#8A94A0;--hike:#7A4DAA;--bg:#F7F8FA;--panel:#FFFFFF;--ink:#16202B;--ink2:#4A5866;--muted:#7C8794;--line:#DCE1E7;--accent:#2C4FA3;--model:#2C4FA3;--market:#C2731B;--good:#1E7F4F;--warn:#B7791F;--crit:#B3261E;--chip:#EEF1F5;--rng:#8A5A16}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--cut:#4FC3C7;--hold:#9AA5B1;--hike:#B892E6;--bg:#0F141A;--panel:#171E27;--ink:#E8EDF2;--ink2:#B7C0CA;--muted:#8391A0;--line:#2A3441;--accent:#7C9BEA;--model:#7C9BEA;--market:#E3A25A;--good:#5CC58C;--warn:#E0B25A;--crit:#EF7B72;--chip:#212B37;--rng:#F0C58C}}
:root[data-theme="dark"]{--cut:#4FC3C7;--hold:#9AA5B1;--hike:#B892E6;--bg:#0F141A;--panel:#171E27;--ink:#E8EDF2;--ink2:#B7C0CA;--muted:#8391A0;--line:#2A3441;--accent:#7C9BEA;--model:#7C9BEA;--market:#E3A25A;--good:#5CC58C;--warn:#E0B25A;--crit:#EF7B72;--chip:#212B37;--rng:#F0C58C}
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
.dist{display:flex;height:22px;border-radius:4px;overflow:hidden;background:var(--chip)} .dist i{display:block;height:100%} .dist i.c{background:var(--cut)} .dist i.h{background:var(--hold)} .dist i.k{background:var(--hike)}
.path{display:grid;grid-template-columns:150px 1fr 90px;gap:10px;align-items:center;padding:7px 0;border-top:1px solid var(--line)} .path:first-of-type{border-top:0} .path .n{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums;text-align:right;font-size:13px}
svg.chart{width:100%;height:auto;display:block} svg.chart text{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:10px;fill:var(--muted)} svg.chart .grid{stroke:var(--line);stroke-width:1} svg.chart .axis{stroke:var(--line)}
.small{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
section{margin-bottom:22px} .verdict{background:var(--panel);border-left:4px solid var(--accent);border-radius:6px;padding:14px 16px;margin-bottom:22px} .verdict b{font-size:15px} .verdict p{margin:6px 0 0;color:var(--ink2);font-size:13.5px}
"""


def _rate_of(key: str) -> float:
    if key.startswith("le_"):
        return float(key[3:])
    if key.startswith("gt_"):
        return float(key[3:]) + 0.25
    return float(key)


def rate_path_section(prices: dict, current: float) -> str:
    events = sorted(e for e in prices if e.startswith("KXFED-"))
    if not events:
        return ""
    rows = []
    for ev in events:
        r = prices[ev]
        probs = r["probabilities"]
        expected = sum(p * _rate_of(k) for k, p in probs.items())
        cut = sum(p for k, p in probs.items() if _rate_of(k) < current - 1e-9)
        hold = sum(p for k, p in probs.items() if abs(_rate_of(k) - current) < 1e-9)
        hike = 1.0 - cut - hold
        segs = "".join(
            f'<i class="{"c" if _rate_of(k) < current - 1e-9 else ("h" if abs(_rate_of(k) - current) < 1e-9 else "k")}" '
            f'style="width:{p * 100:.2f}%" title="{esc(k)}: {p * 100:.1f}%"></i>'
            for k, p in sorted(probs.items(), key=lambda kv: _rate_of(kv[0]))
            if p > 0
        )
        when = (r.get("outcome_at") or "")[:10]
        flag = " · 저유동성" if (r.get("completeness") or {}).get("low_liquidity") else ""
        rows.append(
            f'<div class="path"><div><b>{esc(when)}</b><br><small style="color:var(--muted)">{esc(ev)}{esc(flag)}</small></div>'
            f'<div><div class="dist">{segs}</div><small style="color:var(--ink2)">인하 {cut * 100:.0f}% · 동결 {hold * 100:.0f}% · 인상 {hike * 100:.0f}%</small></div>'
            f'<div class="n">{expected:.2f}%</div></div>'
        )
    return (
        '<section class="panel"><h2>시장이 보는 금리 경로</h2>'
        f'<p class="sub">Kalshi 사다리를 회의별로 이어 본 것. 막대는 회의 후 상단 금리의 확률분포(<span style="color:var(--cut)">■</span> 현재보다 낮음 · <span style="color:var(--hold)">■</span> 현재 {current:.2f}% · <span style="color:var(--hike)">■</span> 높음), 오른쪽은 기대 상단 금리. 모델 없이 시장만 본 값.</p>'
        + "\n".join(rows)
        + "</section>"
    )


def line_chart(series, *, width=560, height=170, y_min=0.0, y_max=1.0, x_labels=None, y_fmt=lambda v: f"{v:.0%}") -> str:
    """Minimal theme-aware SVG line chart. series: [(name, css_color, dashed, [(x, y), ...])] with x in [0, 1]."""
    left, right, top, bottom = 42, 10, 10, 24
    w, h = width - left - right, height - top - bottom

    def sx(x):
        return left + x * w

    def sy(y):
        return top + (1 - (y - y_min) / (y_max - y_min)) * h

    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img">']
    for i in range(5):
        y = y_min + (y_max - y_min) * i / 4
        parts.append(f'<line class="grid" x1="{left}" x2="{left + w}" y1="{sy(y):.1f}" y2="{sy(y):.1f}"/>')
        parts.append(f'<text x="{left - 6}" y="{sy(y) + 3:.1f}" text-anchor="end">{esc(y_fmt(y))}</text>')
    for label, x in (x_labels or []):
        parts.append(f'<text x="{sx(x):.1f}" y="{height - 8}" text-anchor="middle">{esc(label)}</text>')
    for name, color, dashed, pts in series:
        if not pts:
            continue
        d = " ".join(f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(pts))
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"{dash}/>')
        x, y = pts[-1]
        parts.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3.5" fill="{color}"><title>{esc(name)}: {esc(y_fmt(y))}</title></circle>')
    parts.append("</svg>")
    return "\n".join(parts)


def trajectory_section(fed_files: list[str], price_files: list[str], event_ticker: str, meeting_date: str) -> str:
    comps = [load(f) for f in fed_files]
    comps = [c for c in comps if c.get("logistic_three_way") and c.get("event_ticker") == event_ticker]
    if len(comps) < 2:
        return ""
    times = [c["as_of"][:16] for c in comps]
    n = len(comps)
    xs = [i / (n - 1) for i in range(n)]
    market_hike = [(x, c["market"]["hike_probability"]) for x, c in zip(xs, comps, strict=True)]
    model_hike = [(x, c["logistic_three_way"]["hike"]) for x, c in zip(xs, comps, strict=True)]
    market_hold = [(x, c["market"]["hold_probability"]) for x, c in zip(xs, comps, strict=True)]
    model_hold = [(x, c["logistic_three_way"]["hold"]) for x, c in zip(xs, comps, strict=True)]
    labels = [(times[0].replace("T", " "), 0.0), (times[-1].replace("T", " "), 1.0)]
    chart = line_chart(
        [("시장 인상", "var(--market)", False, market_hike), ("모델 인상", "var(--model)", False, model_hike),
         ("시장 동결", "var(--market)", True, market_hold), ("모델 동결", "var(--model)", True, model_hold)],
        x_labels=labels,
    )
    return (
        f'<section class="panel"><h2>{esc(meeting_date)} FOMC 예측 추이</h2>'
        f'<p class="sub">기록 {n}건 (첫 기록 {esc(times[0][:10])}). 실선 = 인상 확률, 점선 = 동결 확률. '
        '<span style="color:var(--market)">■</span> 시장 · <span style="color:var(--model)">■</span> 모델. 회의일까지 매일 한 점씩 늘어납니다.</p>'
        + chart + "</section>"
    )


def backtest_timeline_section(bw_predictions: list[dict]) -> str:
    n = len(bw_predictions)
    if n < 2:
        return ""
    width, height, left, right, top, bottom = 900, 200, 42, 10, 10, 26
    w, h = width - left - right, height - top - bottom
    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img">']
    for i in range(5):
        y = i / 4
        yy = top + (1 - y) * h
        parts.append(f'<line class="grid" x1="{left}" x2="{left + w}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        parts.append(f'<text x="{left - 6}" y="{yy + 3:.1f}" text-anchor="end">{y:.0%}</text>')
    clim = " ".join(f"{'M' if i == 0 else 'L'}{left + i / (n - 1) * w:.1f},{top + (1 - p['baseline_probability_cut']) * h:.1f}" for i, p in enumerate(bw_predictions))
    parts.append(f'<path d="{clim}" fill="none" stroke="var(--muted)" stroke-width="1.5" stroke-dasharray="4 4"/>')
    for i, p in enumerate(bw_predictions):
        x = left + i / (n - 1) * w
        y = top + (1 - p["probability_cut"]) * h
        color = {"cut": "var(--cut)", "hold": "var(--hold)", "hike": "var(--hike)"}[p["actual_decision"]]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"><title>{esc(p["meeting_date"])} 실제 {esc(p["actual_decision"])} · 모델 P(인하) {p["probability_cut"]:.2f}</title></circle>')
        if i % 8 == 0 or i == n - 1:
            parts.append(f'<text x="{x:.1f}" y="{height - 8}" text-anchor="middle">{esc(p["meeting_date"][:7])}</text>')
    parts.append("</svg>")
    return (
        '<section class="panel"><h2>모델의 과거 성적 타임라인 (휴리스틱, 2020–2026)</h2>'
        '<p class="sub">점 높이 = 모델이 낸 인하 확률, 점 색 = 실제 결정(<span style="color:var(--cut)">●</span> 인하 · <span style="color:var(--hold)">●</span> 동결 · <span style="color:var(--hike)">●</span> 인상). 점선 = 과거 빈도 기준(climatology). 인하 점이 높고 나머지 점이 낮을수록 좋은 모델입니다.</p>'
        + "\n".join(parts) + "</section>"
    )


def macro_section(snapshots: list[dict]) -> str:
    n = len(snapshots)
    if n < 2:
        return ""
    xs = [i / (n - 1) for i in range(n)]
    labels = [(snapshots[i]["meeting_date"][:4], xs[i]) for i in range(n) if i == 0 or snapshots[i]["meeting_date"][:4] != snapshots[i - 1]["meeting_date"][:4]]
    panels = []
    for title, key, y0, y1, fmt in (
        ("CPI 전년비 (%)", "cpi_yoy_nsa", 0.0, 10.0, lambda v: f"{v:.0f}"),
        ("실업률 (%)", "unemployment_rate", 3.0, 15.0, lambda v: f"{v:.0f}"),
        ("정책금리 상단 (%)", "policy_rate_upper", 0.0, 6.0, lambda v: f"{v:.0f}"),
    ):
        pts = [(x, float(r[key])) for x, r in zip(xs, snapshots, strict=True)]
        chart = line_chart([(title, "var(--accent)", False, pts)], width=300, height=140, y_min=y0, y_max=y1, x_labels=labels[::2], y_fmt=fmt)
        latest = pts[-1][1]
        panels.append(f'<div><h2 style="font-size:14px">{esc(title)} <span class="meta">최근 {latest:.2f}</span></h2>{chart}</div>')
    return (
        '<section class="panel"><h2>모델이 보는 경제 지표 (회의 전날 vintage, 2019–2026)</h2>'
        '<p class="sub">각 회의 직전에 실제로 공개돼 있던 값. 나중에 수정된 값이 아닙니다.</p>'
        f'<div class="small">{"".join(panels)}</div></section>'
    )


def calendar_section(today: str) -> str:
    import csv

    names = {"cpi": "CPI (소비자물가)", "employment_situation": "고용보고서 (실업률)", "fomc": "FOMC 금리 결정"}
    scored = {"employment_situation": "실업률 비교 채점", "fomc": "Fed 비교 채점", "cpi": "모델 없음 (시장만 기록)"}
    rows = [r for r in csv.DictReader((ROOT / "data/release_schedule.csv").open(encoding="utf-8")) if r["release_date"] >= today]
    rows.sort(key=lambda r: (r["release_date"], r["release_time_local"]))
    html_rows = "\n".join(
        f'<tr><td class="n">{esc(r["release_date"])}</td><td>{esc(r["release_time_local"])} ET</td><td>{esc(names.get(r["series"], r["series"]))}</td><td>{esc(r["reference_period"])}</td><td>{esc(scored.get(r["series"], ""))}</td></tr>'
        for r in rows[:8]
    )
    return (
        '<section class="panel"><h2>다가오는 일정</h2><p class="sub">공식 발표 일정(BLS·연준). 각 날짜에 어떤 채점이 일어나는지.</p>'
        f'<div class="tablewrap"><table><tr><th class="n">날짜</th><th>시각</th><th>발표</th><th>대상</th><th>우리 시스템</th></tr>{html_rows}</table></div></section>'
    )


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
{rate_path_section(prices, current)}
{trajectory_section(d["fed_files"], d["price_files"], fed["event_ticker"], fed["meeting_date"])}
{calendar_section(fed["as_of"][:10])}
{backtest_timeline_section(d["bw_predictions"])}
{macro_section(d["snapshots"])}
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
