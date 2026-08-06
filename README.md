# 持股帳本

台股持股追蹤頁面。純前端、無後端伺服器，持股資料存在瀏覽器的 localStorage，
收盤價由 GitHub Actions 每個交易日自動抓取。

網址：https://terry90459.github.io/stock-portfolio/

## 功能

- 總覽：總投入金額、總收益金額、總收益率
- 持股明細：依代號分組，統整列（股數合計／總價金／收益金額／收益率）可展開檢視每一筆買入紀錄
- 輸入代號自動帶出中文名稱與市場別（上市／上櫃）
- 目前價格自動套用最近收盤價，也可手動覆寫（標記為「手動」，按 ↺ 還原自動）

## 自動報價

`.github/workflows/update-prices.yml` 於台北時間週一至週五 15:30 與 18:00 執行
`scripts/fetch_prices.py`，抓取當日收盤行情寫入 `prices.json` 並 commit 回 repo。
也可以到 Actions 頁面手動按 **Run workflow** 立即執行一次。

資料來源（皆為公開 OpenAPI，不需金鑰）：

收盤價：

- 上市：`https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL`
- 上櫃：`https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes`

除權息：櫃買的 `tpex_exright_prepost`，加上從兩家 swagger 自動探索出摘要含
「除權/除息」的端點。端點代號會隨官方改版變動，所以用探索取代硬寫。
櫃買的除息日欄位官方拼作 `ExRrightsExDividendDate`（Rrights，兩個 r），
對照表已納入。

價格是**收盤價**，不是即時報價。兩個來源都失敗時腳本會直接結束，不會覆寫既有的
`prices.json`，頁面仍會顯示上一次的價格。

## prices.json 格式

```json
{
  "updatedAt": "2026-08-05T18:02:11+08:00",
  "tradeDate": "2026-08-05",
  "count": 1373,
  "sources": ["上市 1373 檔"],
  "prices": {
    "2330": { "name": "台積電", "close": 1085.0, "change": 15.0, "market": "上市" }
  }
}
```

## 本機執行

```bash
python3 scripts/fetch_prices.py   # 產生 prices.json
python3 -m http.server 8000       # 開 http://localhost:8000
```

直接用瀏覽器開 `index.html` 也可以，但 `fetch()` 讀 `prices.json` 會被
`file://` 的 CORS 規則擋掉，價格會變成手動輸入模式。用上面的 http.server 就正常。

## 跨裝置同步（Supabase）

`config.js` 填入 Supabase 專案網址與 anon key 之後，頁面上方會出現帳號列，
用 Email 收登入連結即可跨裝置同步。兩個值留空則維持純本機模式。

設定步驟：

1. 建立 Supabase 專案
2. SQL Editor 貼上 `supabase-schema.sql` 執行
3. Authentication → URL Configuration 把網站網址加入 Redirect URLs
4. Project Settings → API Keys 取得 Project URL 與 Publishable key，填進 `config.js`

Publishable key（`sb_publishable_...`）是設計給瀏覽器用的公開金鑰，放在公開 repo 沒問題；
真正的防線是資料表的 Row Level Security，規則是「只能存取 `user_id = auth.uid()` 的列」。
舊版 anon key（`eyJ...`）也還能用，但 Supabase 將於 2026 年底停用。

**Secret key（`sb_secret_...`）與舊版 service_role key 絕對不要放進 config.js**，
那兩把會繞過所有 RLS。

免費方案閒置 7 天會暫停專案，排程裡有一個「喚醒 Supabase」步驟負責定期戳它。

## 已知限制

- 未登入時資料只存在該裝置的瀏覽器，清除瀏覽器資料會一併清掉。
- 只涵蓋上市與上櫃，興櫃與海外標的沒有自動報價，需手動輸入價格。
- 收盤價未還原除權息，長期持有的報酬率會低估（累計配息欄位可補回現金股利部分）。
- 資料來源包含「除權息預告表」，內含尚未到期的除息日。計算累計配息時只採計
  除息日已過的事件，未到期的另外以「待除息」提示，不計入收益。
- 只處理現金股利。除權（配股）會記錄在 `dividends.json` 的 `stock` 欄位，
  但股數增加尚未反映在持股上，需自行調整股數。
