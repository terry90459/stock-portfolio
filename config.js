// Supabase 連線設定。
//
// 這兩個值本來就是公開的：anon key 是設計給瀏覽器用的「發布金鑰」，
// 真正的防線是資料表上的 Row Level Security（見 supabase-schema.sql）。
// 所以放在公開的 repo 裡沒有問題，但 service_role key 絕對不要放進來。
//
// 取得位置：Supabase 主控台 → Project Settings → API
//   Project URL  → SUPABASE_URL
//   anon public  → SUPABASE_ANON_KEY
//
// 兩個都留空的話，頁面會維持純本機模式，跟加後端之前一模一樣。

window.SUPABASE_URL = "";
window.SUPABASE_ANON_KEY = "";
