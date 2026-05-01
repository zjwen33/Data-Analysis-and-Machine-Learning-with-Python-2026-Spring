# Google Maps 評論分析與決策支援系統

> **Note**: 評論不足的情況有待開發。

這是一個基於 Python 的 Google Maps 評論獲取、清洗與分析系統。本系統旨在自動抓取指定地標的 Google 評論，過濾掉潛在的「打卡送禮」等誘因性假評論，並透過關鍵字分析真實評論的正負向特徵，最後產出一份可解釋性（XAI）的決策支援報告，幫助使用者判斷是否前往該地點。

---

## 🚀 系統流程 (System Flow)

整個系統分為三個主要階段，由三支主要程式依序執行：

1. **第一階段：資料獲取 (`review_fetcher.py`)**
   - 使用者輸入 Google Maps 的分享短網址（如 `https://maps.app.goo.gl/...`）。（**Note**: 實際上，非短網址亦可解析）
   - 系統將短網址展開並擷取出地標的識別碼 (`data_id` 與 `data_cid`)。
   - 透過 SerpApi 呼叫 Google Maps API 獲取地標詳細資訊與最新評論（預設抓取至少 50 筆，對應 4 次 API 呼叫，實際可能因 API 返回結果而有所差異）。
   - 將原始資料存入本地端 SQLite 資料庫 (`reviews.db`) 進行快取，避免重複消耗 API 額度（快取有效期限預設為 30 天）。> **Note**: 此設定可以節省 API Key 額度，但如果要確保資料庫中的資料為最新資料，建議改為 7 天。）

2. **第二階段：資料清洗與數據分析 (`review_processor.py`)**
   - 讀取資料庫中尚未處理的原始評論資料。
   - 依據 `fake_keywords.txt` 字典檔，篩選出符合「5 顆星」且「包含誘因字眼」的潛在假評論（如：打卡送肉盤、招待等）。
   - 排除假評論後，重新計算該地標的「真實平均星等」與「真實星等分佈」。
   - 將分析後的統計數據（包含真假評論比例、評分分佈等）寫回資料庫中對應的紀錄。

3. **第三階段：特徵提取與決策報告生成 (`decision_maker.py`)**
   - 讀取資料庫中已清洗完成的「真實評論」與統計數據。
   - 根據 `positive_keywords.txt` 與 `negative_keywords.txt` 字典檔，針對四個維度（環境與衛生、服務與態度、餐點與食物、價格與CP值）進行文本掃描與情緒計數。
   - 找出該店家的「最大亮點（優點）」與「最大隱憂（缺點）」。
   - 自動生成一份白話文的決策報告（Decision Report），並提供情境導向的行動建議（例如：適合約會、適合外帶、建議避坑等）。

---

## 📁 檔案功能與參數說明

### 1. `review_fetcher.py` (資料獲取)
- **功能**：負責與 SerpApi 溝通，抓取 Google Maps 的地點資訊與評論資料，並寫入資料庫進行快取。支援多組 API Keys 自動輪替以避免配額耗盡。
- **主要參數/變數**：
  - `DB_PATH`: 指定資料庫路徑 (預設 `reviews.db`)。
  - `hl_lang`: API 請求的語言設定 (預設 `"zh-tw"`)。
  - `API_KEYS`: 透過讀取目錄下 `.env` 檔內所有 `SERPAPI_KEY` 開頭的環境變數。
  - `target_amount`: 預設抓取評論數量 (設定為 >50 筆)。
  - `"sort_by": "qualityScore"`: 「最相關」排序（預設）。
   （**Note**:`qualityScore` 排序蒐集到的比較會是有評論文字而非只有星等。其他可調整的選項包含：`newestFirst`（最新）、`ratingHigh`（最高分）、`ratingLow`（最低分）。）
- **使用方式**：直接執行程式，並在終端機輸入 Google Maps 網址。

### 2. `review_processor.py` (評論處理與假評過濾)
- **功能**：讀取原始評論，過濾誘因性假評價，並重新計算真實評分數據。
- **主要參數/變數**：
  - `DB_PATH`: 指定資料庫路徑。
  - `KEYWORDS_PATH`: 指定假評論字典檔路徑 (`fake_keywords.txt`)。
  - `hl_lang`: 查詢對應語言的快取紀錄 (預設 `"zh-tw"`)。
- **主要分析結果參數 (`analysis_result`)**：
  - `total_reviews`: 總處理筆數。
  - `fake_count` / `fake_ratio`: 假評論數量與佔比。
  - `fake_time_range`: 假評論發生的時間區段。
  - `real_reviews_count`: 真實評論筆數。
  - `real_average_rating`: 扣除假五星後的真實平均星等。
  - `real_rating_distribution`: 真實評論的 1~5 星等分佈統計。

### 3. `decision_maker.py` (決策報告生成)
- **功能**：透過關鍵字比對分析真實評論的優劣勢，並產出終端機格式的易讀報告與情境建議。
- **主要參數/變數**：
  - `POS_KEYWORDS_PATH`: 正向關鍵字字典檔 (`positive_keywords.txt`)。
  - `NEG_KEYWORDS_PATH`: 負向關鍵字字典檔 (`negative_keywords.txt`)。
  - `default_pos` / `default_neg`: 預設的正負向關鍵字分類（包含環境、服務、餐點、價格四個維度）。當字典檔不存在時會自動建立。
- **產出資訊**：星等真實度解析、正負評價特徵提取（亮點與隱憂）、情境導向行動建議。

### 4. 字典與設定檔
- **`fake_keywords.txt`**: 條列用於判定假評論的關鍵字（如：打卡、送、好評、招待等），每行一個字詞。若檔案不存在會由程式自動生成預設值。
- **`positive_keywords.txt`**: 正向評價特徵字典。格式為 `類別: 關鍵字1, 關鍵字2`（例如：`餐點與食物: 好吃, 美味, 推薦`）。
- **`negative_keywords.txt`**: 負向評價特徵字典。格式同上（例如：`環境與衛生: 髒, 臭, 吵`）。
- **`.env`**: (使用者須自行建立) 存放 SerpApi 的金鑰，格式為 `SERPAPI_KEY1=您的金鑰`。支援設定多組以自動切換。

### 5. 測試與輔助工具
- **`clear_dbs.py`**: 用於清除或重置資料庫的測試工具。
- **`reviews.db`**: SQLite 資料庫檔案，負責儲存 API 抓取下來的快取資料與分析結果。
**Note**: 可使用 DB Browser for SQLite 等軟體查看資料庫結構與內容。

---

## 🛠️ 如何使用

1. 確保已安裝相關套件：`pip install serpapi`。
2. 在專案根目錄建立 `.env` 檔案，並填寫您的 API Key：
   ```env
   SERPAPI_KEY1=your_api_key_here
   SERPAPI_KEY2=your_another_api_key_here
   ```
3. 依序執行以下程式碼，並在提示時貼上 Google Maps 分享網址：
   ```bash
   python review_fetcher.py     # 步驟一：抓取資料
   python review_processor.py   # 步驟二：清洗假評論
   python decision_maker.py     # 步驟三：產出決策報告
   ```
*(註：同一家店面的網址需經歷上述三步驟才能產生最終的決策報告。)*
