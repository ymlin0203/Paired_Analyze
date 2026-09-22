# Paired Studio · 配對分析工作台

繁體中文 Streamlit 介面與共用 CLI：配對散點、連線、箱型圖、雙尾 Wilcoxon、BH-FDR、PNG / SVG 與完整統計下載。

## 本機啟動

建議 Python 3.12 或 3.13（目前本機亦以 Python 3.14 測試）。

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Windows 已安裝依賴後可雙擊 `start.bat`。介面提供合成示範資料，沒有內建病患資料。

## Streamlit Community Cloud

1. 建立 GitHub repository `paired-analysis-studio`，上傳本資料夾的程式與 `.streamlit/config.toml`。
2. 登入 https://share.streamlit.io/ ，選擇 Create app / Deploy from GitHub。
3. 選擇 repository 與分支 `main`，Main file path 設 `app.py`。
4. Advanced settings 選 Python 3.13，部署。網站網址以平台實際分配為準。

官方步驟：https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

部署包不含原始 Excel、病患 ID、研究圖或本機絕對路徑。上傳檔案在部署伺服器記憶體處理；程式不寫入原始上傳檔、不建立共享 cache。是否適合將研究資料上傳雲端，取決於你的研究資料處理規範與網站存取設定。

## 使用原研究檔案

選擇「原始 TBUT / Schirmer」，上傳檢測 Excel 與受試者 CSV，並選擇正確工作表：

- TBUT：`ACUDES-TBUT`；欄位 `序號`, `Group`, `TBUTV1-OS`, `TBUTV1-OD`, `TBUTV4-OS`, `TBUTV4-OD`。
- Schirmer：`ACUDES-Schirmers test`；欄位 `序號`, `Group`, `V1-OS`, `V1-OD`, `V4-OS`, `V4-OD`。
- 分組表：`ID`, `TX Group`。疾病 1=SJS、2=DES；治療 1=GB20、2=GB20+BL2、3=WL。
- 雙眼平均模式要求該時間點 OS 與 OD 都有有限數值，任何一眼缺失則該訪視缺失。
- 配對使用 ID，不使用列順序。重複、空白 ID 會停止分析。分組不匹配及無效量測會顯示計數。

一般資料模式：每位受試者一列，自行指定 ID、前測、後測與可選分組欄位。請以文字儲存有前導零的 ID。

## CLI

```bash
python cli.py --help
python cli.py demo --output results
python cli.py paired --input measurements.csv --id ID --pre baseline --post week8 --group group --treatment treatment --output results
python cli.py clinical --input "ACUDES-TBUT 20240130.xlsx" --sheet "ACUDES-TBUT" --patients patients.csv --metric TBUT --eye mean --before V1 --after V4 --output results
```

可選 `--dpi 150|300|600|1200`、`--ylabel`、`--before-label`、`--after-label`、`--complete-only`。失敗時輸出明確原因與非零退出碼。輸出 `statistics.csv`、`paired_analysis.zip`；ZIP 內含所有組別 PNG/SVG、統計及 settings.json。

## 方法與原專案追溯

參考圖片由 `Figure2_SuppFig1.py` 產生，其 run() 建立 `Supplemental Figure 1(a)_SJS_GB20_TBUT_(sec)`；另一支 `TBUT_Schirmer’s_TEST.py` 是多訪視、Friedman 檢定及可選菌相樣本篩選流程。本版本聚焦兩訪視配對分析，沒有套用後者的菌相篩選。

Wilcoxon：two-sided、zero_method=wilcox、method=auto、無 continuity correction；至少 4 組完整配對才檢定。SciPy 版本固定且記錄於匯出設定。不同 SciPy 版本處理 ties 的 auto 行為可能不同，因此固定版本對重現重要。

BH 範圍：每次上傳的一個指標，所有疾病 × 治療組別的有效 p 值；原研究模式為六個預定比較（缺乏可計算 p 值的比較不納入有效數）。切換圖表預覽不改變校正範圍。兩指標分開上傳，各自校正。

Median Δ 為完整配對的 median(after − before)，不是兩個邊際中位數相減。預設圖與原程式一致，包含未完整配對的單次測量；統計只含完整配對，也可改成圖上只顯示完整配對。箱型圖採 1.5 IQR 鬚，全部觀測值另以散點顯示。

修正原程式的兩個邊界處理：無法計算時顯示 N/A（不以 n.s. 暗示不顯著）；rank-biserial 改為非零差值的正負秩和差除以總秩和，以正確處理零值及方向。全零差值回報 all_zero_differences，p/q 為 N/A。

https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html

## 驗證

```bash
python -m unittest discover -s . -p test_analysis.py
```

包含 BH、缺失配對、順序對齊、重複 ID、雙眼缺欄、全零差值及小樣本邊界測試。另以本機原始 TBUT 資料核對六組 p/q 與 n，與原程式相符；SJS/GB20 為 n=23、Median Δ=+4.00。原始資料不隨程式發布。

## 介面設計

研究工作台風格：單一 sans-serif 字族，以字重區分標題與內文；主色 #126D78、底色 #F7F9FC、內文 #172B3A。8px 間距基準、8/12/16px 圓角，沒有裝飾動畫。使用 Streamlit 原生有標籤輸入與錯誤訊息，支援鍵盤焦點與窄螢幕堆疊。不要以顏色單獨傳達檢定狀態，不隱藏缺失資料計數，不用動畫分散對圖表的注意力。
