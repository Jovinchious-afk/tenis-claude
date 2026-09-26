# -*- coding: utf-8 -*-
"""Precijenjeno / podcijenjeno: osjetljivost NASE pouzdanosti na varijablu (uz kontrolu cijene)
naspram informacije koju varijabla nosi o ishodu (uz kontrolu cijene). Plus split-half."""
import sys, numpy as np, pandas as pd, base
surf = sys.argv[1] if len(sys.argv) > 1 else "hard"
df = base.build(surface=None if surf == "all" else surf)
df = df[df.p_dev.notna() & df.win.notna()].copy().reset_index(drop=True)

def resid_on(y, x):
    m = ~(np.isnan(y) | np.isnan(x))
    out = np.full(len(y), np.nan)
    A = np.column_stack([np.ones(m.sum()), x[m]])
    coef, *_ = np.linalg.lstsq(A, y[m], rcond=None)
    out[m] = y[m] - A @ coef
    return out

lp = df.logit_p.values
conf_r = resid_on(df.conf.values.astype(float), lp)
VARS = ["d_elo_s","d_elo_o","d_rank","d_serve","d_fs_pct","d_fs_won","d_ss_won","d_ret","d_hold","d_bps","d_bpc",
        "d_tb","d_dec","d_f5","d_f10","d_fq","d_aoe5","d_aoe","aoe5_p","d_m7","d_s7","d_rest","d_m39","d_age","age_p","d_h",
        "d_tbest","seas_w_d","cons_gap"]
half = df.date <= df.date.median()
rows = []
for v in VARS:
    x = df[v].values.astype(float)
    xr = resid_on(x, lp)
    r_model, p_model, n = base.corr(xr, conf_r)
    r_out, p_out, _ = base.corr(x, df.resid.values)
    r1, _, n1 = base.corr(x[half.values], df.resid.values[half.values])
    r2, _, n2 = base.corr(x[~half.values], df.resid.values[~half.values])
    rows.append(dict(var=v, n=n, model_uses_r=r_model, P_model=p_model, informs_r=r_out, P_inf=p_out, half1=r1, half2=r2))
out = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(f"{surf}: n={len(df)}")
print(out.round(3).to_string(index=False))
out.to_csv(f"out_vars2_{surf}.csv", index=False)
