// Supabase 連線設定。
//
// 這兩個值本來就是公開的：publishable key 是設計給瀏覽器用的，
// 真正的防線是資料表上的 Row Level Security（見 supabase-schema.sql）。
// 放在公開的 repo 裡沒有問題。
//
// 取得位置：Supabase 主控台 → Project Settings → API Keys
//   Project URL      → SUPABASE_URL       （https://xxxxx.supabase.co）
//   Publishable key  → SUPABASE_ANON_KEY  （sb_publishable_... 開頭）
//
// 舊版的 anon key（eyJ... 開頭）也還能用，但 Supabase 會在 2026 年底停用它，
// 所以新專案直接用 publishable key。變數名稱沿用 ANON_KEY 只是為了少改程式碼。
//
// 絕對不要放進來的：Secret key（sb_secret_... 開頭）與舊版 service_role key。
// 那兩把會繞過所有 RLS，等於把整個資料庫公開。
//
// 兩個都留空的話，頁面會維持純本機模式，跟加後端之前一模一樣。

window.SUPABASE_URL = "";
window.SUPABASE_ANON_KEY = "";
