import sys, numpy as np, collections, datetime as dt
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import g67_dmi_ema as g
from multiprocessing import Pool
PRE=(g.ts(2018,9,1), g.ts(2021,7,20))

def run(tf, comp, cool, hold):
    g.set_tf(tf); g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = comp, cool, hold
    D=g.load("XAUUSD"); sg=[(i,d) for i,d in g.signals(D) if g.block_ok(D,i,d,"B6")]
    rows=g.trades("XAUUSD","E2",8.0,None,sg)
    for t in rows: t["p"]="pre" if PRE[0]<=t["utc"]<PRE[1] else g.period_of(t["utc"])
    return rows

def path(r,days,risk):
    eq=peak=1.0; dd=wd=0; cur=None; ds=1.0
    for x,dy in zip(r,days):
        if dy!=cur: cur=dy; ds=eq
        eq*=1+risk*x; peak=max(peak,eq); dd=max(dd,1-eq/peak); wd=max(wd,1-eq/ds)
    return eq,dd,wd

def report(name, rows):
    dec=[t for t in rows if t["p"] in g.DECIDE]
    rs=np.array([t["r"] for t in dec]); days=np.array([t["utc"]//86400 for t in dec])
    yrs=(dec[-1]["utc"]-dec[0]["utc"])/(365.25*86400)
    print(f"\n##### {name}: {len(rs)} lenh ({yrs:.1f} nam 2021-07..2026-06), exp {rs.mean():+.3f}, tong {rs.sum():+.1f}R, thang {np.mean(rs>0):.0%}, cost {np.mean([t['cost_r'] for t in dec]):.3f}R, gross {np.mean([t['r']+t['cost_r'] for t in dec]):+.3f}")
    for p in ("pre","train","validate","test","examples"):
        seg=[t for t in rows if t["p"]==p]
        if not seg: print(f"  {p}: 0"); continue
        b=[t["r"] for t in seg if t["d"]==1]; s=[t["r"] for t in seg if t["d"]==-1]
        print(f"  {p:9s} n={len(seg):4d} exp={np.mean([t['r'] for t in seg]):+.3f} | mua {len(b)} {np.mean(b) if b else 0:+.3f} | ban {len(s)} {np.mean(s) if s else 0:+.3f}")
    q=collections.defaultdict(float)
    for t in dec:
        d=dt.datetime.utcfromtimestamp(t["utc"]); q[(d.year,(d.month-1)//3)]+=t["r"]
    eqc=np.cumsum(rs); ddR=np.max(np.maximum.accumulate(np.r_[0,eqc])-np.r_[0,eqc])
    streak=max(len(x) for x in ''.join('L' if r<0 else 'W' for r in rs).split('W'))
    holds=[t["hold_h"] for t in dec]
    print(f"  quy duong {sum(v>0 for v in q.values())}/{len(q)}, DD {ddR:.1f}R, chuoi thua {streak}, lenh/tuan {len(rs)/(yrs*52):.1f}, giu TV {np.median(holds):.1f}h max {max(holds):.0f}h")
    print("  stress x2+0.1R:", {p: round(float(np.mean([t['r']-t['cost_r']-0.1 for t in dec if t['p']==p])),3) for p in g.DECIDE})
    with Pool(8) as pool: sims=[m for ch in pool.map(g.random_job,[("XAUUSD",dec,"E2",8.0,None,700+k,15) for k in range(8)]) for m in ch]
    print(f"  ngau nhien TB {np.mean(sims):+.3f}, p={np.mean(np.array(sims)>=rs.mean()):.3f}")
    rng=np.random.default_rng(3); n=int(len(rs)/yrs)
    for risk in (0.01,0.015):
        eq,dd,wd=path(rs,days,risk)
        res=[path(rs[s:s+n],days[s:s+n],risk) for s in rng.integers(0,max(1,len(rs)-n),3000)]
        rets=[x[0]-1 for x in res]; dds=[x[1] for x in res]
        print(f"  risk {risk*100:.1f}%: x{eq:.2f} ({(eq**(1/yrs)-1)*100:+.0f}%/nam) DD {dd*100:.0f}% ngay {wd*100:.1f}% | 1 nam: trung vi {np.median(rets)*100:+.0f}% p10 {np.percentile(rets,10)*100:+.0f}% DDp90 {np.percentile(dds,90)*100:.0f}% cham10% {np.mean(np.array(dds)>=0.1)*100:.0f}% cham20% {np.mean(np.array(dds)>=0.2)*100:.0f}%")

if __name__=="__main__":
    report("M15 (doi chieu)", run("M15",16,8,480))
    report("M30 cung so nen (nen 16 nen = 8h)", run("M30",16,8,480))
    report("M30 cung thoi gian (nen 8 nen = 4h)", run("M30",8,4,240))
    report("H1 cung so nen (nen 16 nen = 16h)", run("H1",16,8,480))
    report("H1 cung thoi gian (nen 4 nen = 4h)", run("H1",4,2,120))
