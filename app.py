from io import BytesIO
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from analysis import read_table, clinical, generic, analyze, plot, figure_bytes, bundle, demo, fmt

st.set_page_config(page_title='Paired analyze', page_icon='◌', layout='wide')
st.markdown('''<style>
.stApp {background:#F5F7FA;color:#172B3A}
.block-container {max-width:1380px;padding-top:2rem}
h1 {font-size:2.2rem!important;margin-bottom:1rem!important}
[data-testid="stVerticalBlockBorderWrapper"] {background:#FFFFFF;border-radius:16px}
[data-testid="stExpander"] {background:#FFFFFF;border-color:#DEE5ED;border-radius:12px}
[data-testid="stFileUploader"] {border-radius:12px}
[data-testid="stSidebar"] h2 {font-size:1.15rem}
[data-testid="stSidebar"] [role="radiogroup"] {gap:10px}
[data-testid="stSidebar"] label {padding:6px 0}
[data-testid="stTabs"] [role="tab"] {font-size:1rem;padding:12px 20px}
[data-testid="stDownloadButton"] button {border-radius:8px}
[data-testid="stMetricLabel"] {color:#526476}
[data-testid="stCaptionContainer"] {color:#526476}

h1 {letter-spacing:-.04em} h2 {letter-spacing:-.02em}
[data-testid="stMetric"] {background:white;border:1px solid #DEE5ED;border-radius:12px;padding:16px}
[data-testid="stMetricValue"] {font-size:1.5rem}
[data-testid="stSidebar"] {background:#EDF2F7}
button {min-height:44px} button:focus-visible {outline:3px solid #087E8B!important}
@media(prefers-reduced-motion:reduce) {* {animation:none!important;transition:none!important}}
</style>''', unsafe_allow_html=True)
st.title('Paired analyze')

st.caption('每人一列：樣本 ID、治療前、治療後。')
template = 'ID,Before,After\nEXAMPLE_001,3,7\nEXAMPLE_002,2,6\nEXAMPLE_003,4,5\nEXAMPLE_004,3,6\nEXAMPLE_005,5,4\nEXAMPLE_006,2,5\n'
st.download_button('下載三欄範本 CSV',template.encode('utf-8-sig'),'paired_template.csv','text/csv')
with st.expander('資料格式說明'):
    st.write('ID 是每人的唯一代碼；Before、After 填同一指標、同一單位的前後測數值。範本中的 EXAMPLE 為虛構資料，請全部替換成自己的資料。')
    st.write('圖表 Title 在上傳後設定，不需要放入資料檔。多組分析才需要額外的組別欄。缺值或非數字會排除；0 是有效數值。重複或空白 ID 必須先修正。')
    st.caption('原始 TBUT / Schirmer 模式另需檢測 Excel 與含 ID、TX Group 的分組 CSV。')

def upload_table(label,key):
    uploaded=st.file_uploader(label,type=['csv','xlsx'],key=key)
    if uploaded is None: return None
    sheet=0
    if uploaded.name.endswith('.xlsx'):
        with pd.ExcelFile(BytesIO(uploaded.getvalue())) as book:
            sheet=st.selectbox('選擇工作表',book.sheet_names,key=key+'_sheet')
    return read_table(uploaded,sheet)

with st.sidebar:
    st.header('資料來源')
    mode=st.radio('選擇資料類型',['一般前後測資料','示範資料','原始 TBUT / Schirmer'],label_visibility='collapsed')
    st.divider()
    st.caption('檢定方式')
    st.write('Wilcoxon · BH-FDR')
    with st.expander('資料處理與檢定規則'):
        st.caption('至少 4 組完整配對。雙尾 Wilcoxon 檢定；同一指標跨組別做 BH 校正。零差值依 wilcox 處理。')
        st.caption('資料在伺服器記憶體處理，不寫入上傳檔或共享快取。')

try:
    with st.expander('1  資料與配對',expanded=mode!='示範資料'):
        clinical_family=mode=='原始 TBUT / Schirmer'
        metric='TBUT'
        eye='mean'
        before,after='V1','V4'
        if mode=='示範資料':
            raw=demo()
            data,audit=generic(raw,'ID','baseline','week8','group','treatment')
            st.download_button('下載示範 CSV / 資料格式範本',raw.to_csv(index=False).encode('utf-8-sig'),'paired_demo.csv','text/csv')
        elif clinical_family:
            opt1,opt2=st.columns(2)
            metric=opt1.selectbox('指標',['TBUT','Schirmer'])
            eye=opt2.selectbox('眼別',['mean','OS','OD'],format_func=lambda x:{'mean':'雙眼平均（必須同時有 OS 與 OD）','OS':'OS 左眼','OD':'OD 右眼'}[x])
            st.caption('檢測表：序號、Group、TBUTV1-OS / TBUTV1-OD…；Schirmer 使用 V1-OS / V1-OD…。分組表：ID、TX Group。')
            up1,up2=st.columns(2)
            with up1:
                st.markdown('**檢測數值**')
                raw=upload_table('檢測 Excel / CSV','measure')
            with up2:
                st.markdown('**受試者分組**')
                patient=upload_table('分組 CSV / Excel','patients')
            if raw is None or patient is None:
                st.info('請上傳兩份資料，或從左側選擇示範資料。'); st.stop()
            data,audit=clinical(raw,patient,metric,eye)
            visits=sorted(data.visit.unique(),key=lambda x:int(x[1:]))
            if len(visits)<2: st.error('至少需要兩個時間點。'); st.stop()
            a,b=st.columns(2)
            before=a.selectbox('前測時間點',visits,index=0)
            after=b.selectbox('後測時間點',visits,index=visits.index('V4') if 'V4' in visits else len(visits)-1)
        else:
            st.caption('每位受試者一列，至少需要 ID、前測值、後測值。可另外指定疾病組別與治療組別。')
            raw=upload_table('上傳前後測資料','generic')
            if raw is None: st.info('請上傳 CSV 或 Excel。'); st.stop()
            cols=list(raw.columns)
            if len(cols)<3: st.error('資料至少需要三個欄位。'); st.stop()
            a,b,c=st.columns(3)
            subject=a.selectbox('受試者 ID',cols)
            pre=b.selectbox('前測欄位',cols,index=1)
            post=c.selectbox('後測欄位',cols,index=2)
            group=treatment=None
            with st.expander('多組分析（選填）'):
                treatment=st.selectbox('組別欄位',[None]+cols,format_func=lambda x:x or '不分組')
            data,audit=generic(raw,subject,pre,post,group,treatment)
            paired_values=data.pivot(index='subject_id',columns='visit',values='value')
            valid_ids=paired_values.dropna().index
            rejected=raw[~raw[subject].astype(str).str.strip().isin(valid_ids)].copy()
            if len(rejected):
                st.warning(f'{len(rejected)} 列缺少有效前後測數值，已排除。')
                with st.expander('查看排除資料'):
                    st.dataframe(rejected[[subject,pre,post]],hide_index=True)
            data=data[data.subject_id.isin(valid_ids)]
            raw=raw.loc[raw[subject].astype(str).str.strip().isin(valid_ids),list(dict.fromkeys([subject,pre,post]+([treatment] if treatment else [])))]
            st.caption(f'納入 {len(raw)} 組完整配對。僅使用已選取欄位。')
            st.download_button('下載有效配對資料',raw.to_csv(index=False).encode('utf-8-sig'),'valid_pairs.csv','text/csv')
        with st.expander('檢查前 10 筆資料'):
            st.dataframe(raw.head(10),hide_index=True,width='stretch')
    summary,panels=analyze(data,before,after,clinical_family)
except (ValueError,KeyError,TypeError,ImportError,OSError) as e:
    st.error(str(e)); st.stop()

if mode=='示範資料': st.caption('示範模式 · 合成資料，非研究結果。切換左側資料來源即可上傳自己的檔案。')
if audit['invalid_measurement_cells']: st.warning(f"{audit['invalid_measurement_cells']} 個非空白量測無法轉為有限數值，已視為缺失。")
if audit['unmatched_or_excluded_group']: st.warning(f"{audit['unmatched_or_excluded_group']} 位受試者未匹配分組或不屬於 SJS/DES × GB20/GB20+BL2/WL，已排除。")

left,right=st.columns([1,2.4],gap='large')
with left:
    st.subheader('2  圖表設定')
    idx=st.selectbox('預覽組別',list(summary.index),format_func=lambda i:f"{summary.loc[i,'group']} · {summary.loc[i,'treatment']}") if len(summary)>1 else summary.index[0]
    row=summary.loc[idx]
    chart_title=st.text_input('圖表 Title',str(row['treatment']) if row['treatment']!='All' else '治療前後比較',key=f'title_{mode}_{idx}')
    g=row['group']
    prefix='Sjögren' if g=='SJS' else 'Dry-eye' if g=='DES' else ''
    baseline_label=f'{prefix}-Baseline' if prefix and before=='V1' else ('Before' if mode=='一般前後測資料' else before)
    after_label=f'{prefix}-8Week' if prefix and after=='V4' else ('After' if mode=='一般前後測資料' else after)
    with st.expander('標籤、配色與座標',expanded=False):
        label1=st.text_input('前測顯示文字',baseline_label,key=f'label1_{g}_{before}')
        label2=st.text_input('後測顯示文字',after_label,key=f'label2_{g}_{after}')
        ylabel=st.text_input('Y 軸名稱與單位','Value' if mode=='一般前後測資料' else ('TBUT (sec)' if metric=='TBUT' else 'Schirmer (mm/5 min)'),key='ylabel_'+metric)
        color=st.color_picker('散點與箱型圖顏色','#887575')
        complete_only=st.checkbox('圖上僅顯示完整配對',value=True,help='預設與原程式相同：圖上保留單次量測；統計一律只使用完整配對。')
        limits=None
        if st.checkbox('自訂 Y 軸範圍'):
            a,b=st.columns(2)
            lo=a.number_input('最小值',value=0.0); hi=b.number_input('最大值',value=12.0)
            if hi<=lo: st.error('最大值必須大於最小值。'); st.stop()
            limits=(lo,hi)
        dpi=st.select_slider('PNG 解析度 (DPI)',[150,300,600,1200],value=300)
        st.caption('SVG 為向量圖，放大不失真。1200 DPI 需要較多記憶體與處理時間。')
config=dict(labels=(label1,label2),ylabel=ylabel,color=color,complete_only=complete_only,limits=limits,dpi=dpi,before=before,after=after,eye=eye,source_mode=mode,title=chart_title)
with right:
    st.subheader('3  分析結果')
    a,b,c=st.columns(3)
    a.metric('完整配對',int(row.n_pairs)); b.metric('Median Δ',f'{row.median_delta:+.2f}' if pd.notna(row.median_delta) else 'N/A'); c.metric('p 值' if len(summary)==1 else 'BH 校正',fmt(row.p,'p') if len(summary)==1 else fmt(row.q_bh,'q'))
    fig=plot(panels[(row.group,row.treatment)],row,labels=config['labels'],ylabel=ylabel,color=color,complete_only=complete_only,limits=limits,title=chart_title)
    st.pyplot(fig,width='stretch')
    st.caption(f"{int(row.n_incomplete)} 位受試者缺少其中一次量測。n 為完整配對數；Median Δ = median(後測 − 前測)。BH 校正涵蓋本指標的 {int(row.bh_valid_tests)} 個有效檢定。")
    if row.status!='ok': st.warning({'insufficient_pairs':'完整配對少於 4 組，未計算檢定。','all_zero_differences':'所有配對差值為零，Wilcoxon p 值不適用。'}[row.status])
    a,b=st.columns(2)
    a.download_button('下載圖表 PNG',figure_bytes(fig,'png',dpi),'paired_plot.png','image/png',width='stretch',type='primary')
    b.download_button('下載 SVG',figure_bytes(fig,'svg'),'paired_plot.svg','image/svg+xml',width='stretch')
    plt.close(fig)

st.divider()
st.subheader('統計與匯出')
with st.expander('查看所有組別統計',expanded=False):
    st.dataframe(summary,hide_index=True,width='stretch')
st.download_button('下載統計 CSV',summary.to_csv(index=False).encode('utf-8-sig'),'statistics.csv','text/csv')
st.caption('批次匯出會將目前 Title、圖軸文字、配色和顯示範圍套用到所有組別。')
if st.button('建立所有組別圖表 ZIP',type='primary'):
    with st.spinner('產生 PNG、SVG、統計摘要與分析設定…'):
        payload=bundle(summary,panels,config)
    st.download_button('下載完整分析 ZIP',payload,'paired_analysis.zip','application/zip')
with st.expander('方法與來源追溯'):
    st.write('圖形來源：Figure2_SuppFig1.py；原始研究模式採雙眼嚴格平均，V1 / V4，疾病組別 1=SJS、2=DES，治療組別 1=GB20、2=GB20+BL2、3=WL。')
    st.write('每位受試者是統計單位。配對依 ID 對齊；重複 ID 會停止分析。預設圖形保留未配對量測，但檢定與差值只用完整配對。每份上傳指標獨立校正，預覽選擇不影響 BH 家族。')
    st.write('Wilcoxon signed-rank：two-sided、zero_method=wilcox、method=auto。Rank-biserial = (正差秩和 − 負差秩和) / 非零差值秩和；正值代表後測增加。N/A 不代表不顯著。')
    st.caption('這個版本專注於兩時間點配對分析；另一支 TBUT_Schirmer’s_TEST.py 的多時間點 Friedman 與菌相篩選未納入。')
