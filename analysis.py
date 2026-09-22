"""Shared, deterministic paired-analysis engine. No patient data is bundled."""
from io import BytesIO
import re
import zipfile
import json
import numpy as np
import pandas as pd
import scipy
from scipy.stats import wilcoxon, rankdata
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
_available_fonts = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams['font.family'] = [f for f in ['Microsoft JhengHei', 'Noto Sans CJK JP', 'Noto Sans CJK TC', 'DejaVu Sans'] if f in _available_fonts]
plt.rcParams['axes.unicode_minus'] = False

GROUPS = {1: 'SJS', 2: 'DES'}
TREATMENTS = {1: 'GB20', 2: 'GB20+BL2', 3: 'WL'}

def read_table(source, sheet=0):
    name = getattr(source, 'name', str(source))
    if hasattr(source, 'seek'):
        source.seek(0)
    if name.lower().endswith('.csv'):
        return pd.read_csv(source, dtype=str)
    return pd.read_excel(source, sheet_name=sheet, dtype=str)

def clean(df):
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    if df.columns.duplicated().any():
        raise ValueError('欄位名稱重複，請先修正來源資料。')
    return df

def ids(series):
    return series.astype('string').str.strip().replace('', pd.NA)

def validate_ids(df, col):
    df[col] = ids(df[col])
    if df[col].isna().any():
        raise ValueError(f'{col} 有空白 ID；請補齊或移除該列。')
    if df[col].duplicated().any():
        raise ValueError(f'{col} 有重複 ID；不會自動保留第一筆，請先確認資料。')

def clinical(measure, patients, metric='TBUT', eye='mean'):
    measure, patients = clean(measure), clean(patients)
    if not {'序號', 'Group'} <= set(measure):
        raise ValueError('檢測資料需要「序號」與「Group」欄位。')
    if not {'ID', 'TX Group'} <= set(patients):
        raise ValueError('分組資料需要「ID」與「TX Group」欄位。')
    validate_ids(measure, '序號')
    validate_ids(patients, 'ID')
    pattern = r'^TBUT(V\d+)-(OS|OD)$' if metric == 'TBUT' else r'^(V\d+)-(OS|OD)$'
    cols = [(c, re.fullmatch(pattern, c)) for c in measure]
    cols = [(c, m) for c, m in cols if m]
    if not cols:
        raise ValueError('此工作表沒有符合格式的眼別量測欄位。')
    tx = pd.to_numeric(patients['TX Group'], errors='coerce').map(TREATMENTS)
    lookup = dict(zip(patients.ID, tx))
    base = pd.DataFrame({'subject_id': measure['序號'],
                         'group': pd.to_numeric(measure.Group, errors='coerce').map(GROUPS),
                         'treatment': measure['序號'].map(lookup)})
    audit = {'input_subjects': len(base), 'unmatched_or_excluded_group': int(base[['group','treatment']].isna().any(axis=1).sum())}
    records = []
    invalid = 0
    for visit in sorted({m[1] for _, m in cols}):
        values = {}
        for c, m in cols:
            if m[1] == visit:
                v = pd.to_numeric(measure[c], errors='coerce').replace([np.inf, -np.inf], np.nan)
                invalid += int((measure[c].notna() & v.isna()).sum())
                values[m[2]] = v
        if eye == 'mean':
            value = (values.get('OS', pd.Series(np.nan, index=measure.index)) + values.get('OD', pd.Series(np.nan, index=measure.index))) / 2
        else:
            value = values.get(eye, pd.Series(np.nan, index=measure.index))
        records.append(base.assign(visit=visit, value=value))
    audit['invalid_measurement_cells'] = invalid
    return pd.concat(records, ignore_index=True).dropna(subset=['group','treatment']), audit

def generic(df, subject, before, after, group=None, treatment=None):
    df = clean(df)
    if before == after or subject in (before, after):
        raise ValueError('ID、前測與後測必須是不同欄位。')
    validate_ids(df, subject)
    base = pd.DataFrame({'subject_id': df[subject], 'group': ids(df[group]) if group else 'All', 'treatment': ids(df[treatment]) if treatment else 'All'})
    if base[['group','treatment']].isna().any().any():
        raise ValueError('分組欄位含空白，請先補齊。')
    invalid = 0
    records = []
    for col, visit in [(before,'V1'), (after,'V4')]:
        value = pd.to_numeric(df[col], errors='coerce').replace([np.inf,-np.inf], np.nan)
        invalid += int((df[col].notna() & value.isna()).sum())
        records.append(base.assign(visit=visit, value=value))
    return pd.concat(records), {'input_subjects':len(df), 'invalid_measurement_cells':invalid, 'unmatched_or_excluded_group':0}

def bh(p):
    p = np.asarray(p, dtype=float)
    result = np.full(len(p), np.nan)
    valid = np.flatnonzero(np.isfinite(p))
    order = valid[np.argsort(p[valid])]
    result[order] = np.minimum.accumulate((p[order]*len(order)/np.arange(1,len(order)+1))[::-1])[::-1].clip(0,1)
    return result

def analyze(data, before='V1', after='V4', clinical_family=False):
    if before == after:
        raise ValueError('請選擇不同的前後測時間點。')
    keys = [(g,t) for g in GROUPS.values() for t in TREATMENTS.values()] if clinical_family else list(data.groupby(['group','treatment'], sort=True).groups)
    rows, panels = [], {}
    for g,t in keys:
        subset = data[(data.group==g) & (data.treatment==t)]
        if subset.duplicated(['subject_id','visit']).any():
            raise ValueError('同一受試者與時間點有重複紀錄。')
        wide = subset.pivot(index='subject_id',columns='visit',values='value').reindex(columns=[before,after])
        paired = wide.dropna()
        diff = (paired[after]-paired[before]).to_numpy(float)
        p = stat = r = np.nan
        status = 'ok'
        nz = diff[diff != 0]
        if len(diff)<4:
            status = 'insufficient_pairs'
        elif not len(nz):
            status = 'all_zero_differences'
        else:
            stat,p = wilcoxon(diff, zero_method='wilcox', alternative='two-sided', method='auto')
            ranks = rankdata(abs(nz))
            r = float(np.sum(ranks*np.sign(nz))/ranks.sum())
        rows.append(dict(group=g,treatment=t,n_pairs=len(paired),n_incomplete=len(wide)-len(paired),n_nonzero=len(nz),median_before=paired[before].median(),median_after=paired[after].median(),median_delta=np.median(diff) if len(diff) else np.nan,statistic=stat,p=p,rank_biserial=r,status=status))
        panels[(g,t)] = wide
    summary = pd.DataFrame(rows)
    if summary.empty:
        raise ValueError('沒有可分析的組別。')
    summary['q_bh'] = bh(summary.p)
    summary['bh_valid_tests'] = int(summary.p.notna().sum())
    return summary, panels

def fmt(v, name):
    return f'{name} = N/A' if not np.isfinite(v) else f'{name} < 0.001' if v<.001 else f'{name} = {v:.3f}'

def plot(wide, row, labels=('Baseline','8-Week'), ylabel='TBUT (sec)', color='#887575', complete_only=False, limits=None, title=None):
    wide = wide.dropna() if complete_only else wide
    fig, ax = plt.subplots(figsize=(6.5,5.5), dpi=140)
    values = [wide[c].dropna().to_numpy() for c in wide]
    bp = ax.boxplot([x if len(x) else [np.nan] for x in values], positions=[1,2], widths=.55, patch_artist=True,showfliers=False,medianprops={'color':'black','linewidth':2.5},boxprops={'color':'#4a4a4a','alpha':.25},whiskerprops={'color':'#4a4a4a','alpha':.25},capprops={'color':'#4a4a4a','alpha':.25})
    for box in bp['boxes']:
        box.set_facecolor(color); box.set_alpha(.12)
    rng = np.random.default_rng(7)
    for _, vals in wide.sort_index().iterrows():
        j = rng.uniform(-.06,.06)
        y = vals.to_numpy(float)
        ax.plot(np.array([1,2])+j,y,color='black',alpha=.1,lw=.9,zorder=2)
        ax.scatter(np.array([1,2])+j,y,s=80,color=color,alpha=.9,edgecolors='#4a4a4a',linewidths=.9,zorder=4)
    delta = row['median_delta']
    note = f'Median Δ = {delta:+.2f}' if np.isfinite(delta) else 'Median Δ = N/A'
    note += '\n'+fmt(row['p'],'p')+'  |  '+fmt(row['q_bh'],'q (BH)')+f"  (n={row['n_pairs']})"
    ax.text(.03,.97,note,transform=ax.transAxes,va='top',fontsize=11,bbox=dict(fc='white',ec='none',alpha=.85))
    finite = wide.to_numpy(float); finite = finite[np.isfinite(finite)]
    if limits:
        ax.set_ylim(*limits)
    elif finite.size:
        span = np.ptp(finite); pad = .1*span if span else 1
        ax.set_ylim(finite.min()-pad,finite.max()+pad)
    ax.set_xticks([1,2],labels); ax.set_xlabel('Visit',fontsize=15)
    ax.set_ylabel(ylabel,fontsize=15); ax.set_title(str(row['treatment']) if title is None else title,fontsize=16,pad=12)
    ax.tick_params(labelsize=12,width=2,length=8)
    for s in ax.spines.values(): s.set_linewidth(2)
    fig.tight_layout()
    return fig

def figure_bytes(fig, fmt='png', dpi=300):
    output=BytesIO(); fig.savefig(output,format=fmt,dpi=dpi,bbox_inches='tight'); return output.getvalue()

def bundle(summary, panels, config):
    output=BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('statistics.csv',summary.to_csv(index=False))
        z.writestr('settings.json',json.dumps({**config,'scipy_version':scipy.__version__,'test':'two-sided Wilcoxon, wilcox, auto','BH':'all valid tests in this uploaded metric; preview selection does not change family'},ensure_ascii=False,indent=2))
        for idx,row in summary.iterrows():
            if not len(panels[(row.group,row.treatment)]): continue
            fig=plot(panels[(row.group,row.treatment)],row,**{k:config[k] for k in ['labels','ylabel','color','complete_only','limits','title'] if k in config})
            name=re.sub(r'[^\w+.-]+','_',f'{idx+1}_{row.group}_{row.treatment}')
            for fmt_ in ['png','svg']:
                z.writestr(f'{name}.{fmt_}',figure_bytes(fig,fmt_,config.get('dpi',300)))
            plt.close(fig)
    return output.getvalue()

def demo():
    rng=np.random.default_rng(7)
    rows=[]
    for g in GROUPS.values():
        for t in TREATMENTS.values():
            for i in range(23):
                pre=float(rng.choice([1,2,2.5,3,3.5,4.5]))
                post=max(0,pre+float(rng.choice([2,3,4,4.5,5]))-(2 if t=='WL' else 0))
                rows.append(dict(ID=f'DEMO-{g}-{t}-{i+1:02}',group=g,treatment=t,baseline=pre,week8=post))
    return pd.DataFrame(rows)
