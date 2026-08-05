# 持股帳本

一個純前端（單一 HTML 檔）的股票庫存追蹤頁面，資料儲存在瀏覽器的 localStorage，不需要後端。

## 本機開啟
直接用瀏覽器打開 `index.html` 即可使用。

## 部署到 GitHub Pages（免安裝任何工具）
1. 到 https://github.com/new 建立一個新的 repository（例如叫 `stock-portfolio`）。建議設為 **Private**，因為裡面會存放你的持股與金額資訊。
   - 注意：GitHub Pages 對 Private repo 需要付費方案（Pro/Team）才能啟用；若使用免費帳號，repo 需設為 Public 才能開啟 Pages，任何知道網址的人都看得到頁面（但資料存在「你自己瀏覽器」的 localStorage，其他人打開網址看到的是空白帳本，不會看到你的資料）。
2. 進入新建立的 repository 頁面，點 **Add file → Upload files**，把這個資料夾裡的 `index.html` 拖進去，按 **Commit changes**。
3. 到 repository 的 **Settings → Pages**，在 "Build and deployment" 的 Source 選擇 `Deploy from a branch`，Branch 選 `main` / `/(root)`，按 Save。
4. 等 1-2 分鐘，GitHub 會給你一個網址，格式類似：
   `https://<你的帳號>.github.io/stock-portfolio/`
5. 之後只要在外面用手機或電腦打開這個網址，就能新增/編輯持股。資料會存在該裝置瀏覽器的 localStorage，**同一個網址在不同裝置或不同瀏覽器上資料不會同步**（例如手機和電腦是分開的兩份資料）。

## 之後要更新頁面內容怎麼辦？
之後如果要調整功能（例如改版面、加圖表），只要把新的 `index.html` 再上傳一次覆蓋舊檔（Add file → Upload files，選擇覆蓋），GitHub Pages 會自動重新部署。

## 關於資料同步
目前版本資料存在單一瀏覽器裡，換裝置看不到。如果之後想要「多裝置同步」，常見做法有：
- 改用一個小型後端 + 資料庫（例如 Supabase / Firebase 的免費方案）
- 或是每次操作後手動「匯出 / 匯入」JSON 檔案

有需要的話我可以再幫你加上這些功能。
