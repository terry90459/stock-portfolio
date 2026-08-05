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

- 上市：`https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL`
- 上櫃：`https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes`

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

## 已知限制

- **資料不跨裝置同步**。持股資料存在各裝置自己的瀏覽器裡，手機和電腦是兩份獨立資料。清除瀏覽器資料會一併清掉。
- 只涵蓋上市與上櫃，興櫃與海外標的沒有自動報價，需手動輸入價格。
- 收盤價未還原除權息，長期持有的報酬率會低估。
