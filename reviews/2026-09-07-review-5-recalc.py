# Independent recomputation (Python 3.9 compatible, no repo imports)
import csv
import json
import math
import os
from statistics import fmean, pstdev

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load_csv(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def load_json(p):
    with open(p) as f:
        return json.load(f)
meetings = load_csv(f"{ROOT}/data/fomc_meetings_2019_2024.csv")
snaps = {s["meeting_date"]: s for s in load_json(f"{ROOT}/data/generated/fomc_feature_snapshots_2019_2024.json")}

def sig(x):
    return 1/(1+math.exp(-x)) if x>=0 else math.exp(x)/(1+math.exp(x))
def feas(p, r):
    if r <= 0.25: return 0.005
    return min(max(p,1e-6),1-1e-6)
def heur(s):
    score = -0.9*(s["cpi_yoy_nsa"]-2.0)+1.2*s["unemployment_change_3m"]+0.35*(s["unemployment_rate"]-4.0)+0.25*(s["policy_rate_upper"]-2.75)-0.5
    return feas(sig(score), s["policy_rate_upper"])
def brier(ps, ys): return sum((p-y)**2 for p,y in zip(ps,ys))/len(ps)
def ece(ps, ys, bins=5):
    g=[[] for _ in range(bins)]
    for p,y in zip(ps,ys): g[min(bins-1, math.floor(p*bins+1e-12))].append((p,y))
    return sum(len(b)/len(ps)*abs(fmean(p for p,_ in b)-fmean(y for _,y in b)) for b in g if b)

def run_baseline(rows, warmup=8):
    ps, cl, ys, ah = [], [], [], []
    prior = sum(r["decision"]=="cut" for r in rows[:warmup])
    for i, m in enumerate(rows[warmup:], start=warmup):
        s = {k: float(v) for k,v in snaps[m["meeting_date"]].items() if k in ("cpi_yoy_nsa","unemployment_rate","unemployment_change_3m","policy_rate_upper")}
        assert abs(s["policy_rate_upper"]-float(m["upper_before"]))<1e-9
        y = int(m["decision"]=="cut")
        ps.append(heur(s)); cl.append((prior+1)/(i+2)); ys.append(y); ah.append(0.0)
        prior += y
    return ps, cl, ys

def fit_logistic(X, Y, ridge=1.0, lr=0.05, iters=2000):
    cols = list(zip(*X)); means=[fmean(c) for c in cols]; scales=[max(pstdev(c),1e-9) for c in cols]
    M=[[(v-mu)/sc for v,mu,sc in zip(row,means,scales)] for row in X]
    pos=sum(Y); b=math.log((pos+1)/(len(Y)-pos+1)); w=[0.0]*len(cols); n=len(Y)
    for _ in range(iters):
        gb=0.0; gw=[0.0]*len(w)
        for row,y in zip(M,Y):
            sc=b+sum(wi*v for wi,v in zip(w,row)); p=1/(1+math.exp(-max(min(sc,35),-35))); e=p-y
            gb+=e
            for j,v in enumerate(row): gw[j]+=e*v
        b-=lr*gb/n
        for j in range(len(w)): w[j]-=lr*(gw[j]/n+ridge*w[j])
    return means,scales,b,w
def predict(model, x):
    means,scales,b,w=model
    return sig(b+sum(wi*(v-mu)/sc for wi,v,mu,sc in zip(w,x,means,scales)))
FEAT=("cpi_yoy_nsa","unemployment_rate","unemployment_change_3m","policy_rate_upper")
def fx(md): s=snaps[md]; return tuple(float(s[k]) for k in FEAT)

def run_wf(rows, warmup=8):
    ps, cl, ys, ib, zlb, coefs = [], [], [], [], [], []
    for i in range(warmup, len(rows)):
        tr=rows[:i]; X=[fx(r["meeting_date"]) for r in tr]; Y=[int(r["decision"]=="cut") for r in tr]
        model=fit_logistic(X,Y)
        m=rows[i]; r=float(snaps[m["meeting_date"]]["policy_rate_upper"])
        raw=predict(model, fx(m["meeting_date"]))
        ps.append(feas(raw,r)); ys.append(int(m["decision"]=="cut")); cl.append((sum(Y)+1)/(len(Y)+2))
        ib.append(feas(sig(model[2]), r))  # intercept-only + ZLB mask
        zlb.append(r<=0.25); coefs.append((m["meeting_date"], round(raw,4), [round(c,4) for c in model[3]]))
    return ps, cl, ys, ib, zlb, coefs

sched=[r for r in meetings if r["event_type"]=="scheduled"]
for name, rows, fn in (("all", meetings, "fed_baseline_backtest_all_2019_2024"), ("scheduled", sched, "fed_baseline_backtest_scheduled_2019_2024")):
    ps,cl,ys=run_baseline(rows); ref=load_json(f"{ROOT}/data/generated/{fn}.json")
    mism=sum(abs(p-q["probability_cut"])>1e-9 for p,q in zip(ps,ref["predictions"]))
    print(f"[baseline {name}] n={len(ps)} brier={brier(ps,ys):.6f} (json {ref['model_brier']:.6f}) clim={brier(cl,ys):.6f} (json {ref['sequential_climatology_brier']:.6f}) ah={brier([0]*len(ys),ys):.6f} ece={ece(ps,ys):.6f} (json {ref['calibration_ece']:.6f}) mismatched_preds={mism}")

ps,cl,ys,ib,zlb,coefs=run_wf(sched); ref=load_json(f"{ROOT}/data/generated/fed_walk_forward_logistic_2019_2024.json")
print(f"\n[walk-forward] n={len(ps)} brier={brier(ps,ys):.6f} (json {ref['model_brier']:.6f}) clim={brier(cl,ys):.6f} (json {ref['sequential_climatology_brier']:.6f}) ece={ece(ps,ys):.6f} (json {ref['calibration_ece']:.6f})")
ah=brier([0]*len(ys),ys)
print(f"  always-hold brier={ah:.6f}  BSS vs always-hold={1-brier(ps,ys)/ah:+.4f}  BSS vs clim={1-brier(ps,ys)/brier(cl,ys):+.4f}")
print(f"  intercept-only+ZLB mask brier={brier(ib,ys):.6f}  BSS vs clim={1-brier(ib,ys)/brier(cl,ys):+.4f}")
nz=[i for i,z in enumerate(zlb) if not z]
sub=lambda a: [a[i] for i in nz]
print(f"  NON-ZLB only (n={len(nz)}): model={brier(sub(ps),sub(ys)):.6f} clim={brier(sub(cl),sub(ys)):.6f} always-hold={brier([0]*len(nz),sub(ys)):.6f} intercept-only={brier(sub(ib),sub(ys)):.6f}")
print(f"    BSS(non-ZLB) vs clim={1-brier(sub(ps),sub(ys))/brier(sub(cl),sub(ys)):+.4f}  vs always-hold={1-brier(sub(ps),sub(ys))/brier([0]*len(nz),sub(ys)):+.4f}")
zi=[i for i,z in enumerate(zlb) if z]
print(f"  ZLB rows (n={len(zi)}): model sq-err sum={sum((ps[i]-ys[i])**2 for i in zi):.6f}  clim sq-err sum={sum((cl[i]-ys[i])**2 for i in zi):.6f}")
print("\n  per-meeting raw logistic p (pre-mask) and standardized coefficients [cpi, unrate, d3m, rate]:")
for d,raw,c in coefs: 
    i=[x[0] for x in coefs].index(d)
    print(f"   {d} raw={raw:.4f} final={ps[i]:.4f} y={ys[i]} clim={cl[i]:.3f} coef={c}")
