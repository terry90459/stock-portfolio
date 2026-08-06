-- 持股存摺 · Supabase 結構
-- 在 Supabase 主控台的 SQL Editor 貼上整段執行一次即可。
-- 重複執行是安全的（有 if not exists / drop policy if exists 保護）。

create table if not exists public.holdings (
  id             text        not null,                    -- 前端產生的識別碼
  user_id        uuid        not null default auth.uid()
                             references auth.users on delete cascade,
  code           text        not null,                    -- 股票代號
  name           text        not null,                    -- 名稱
  shares         numeric     not null,                    -- 股數
  buy_price      numeric     not null,                    -- 買進價
  buy_date       date,                                    -- 買進日，可空
  fee            numeric,                                 -- null = 用標準費率計算
  regular        boolean     not null default false,      -- 是否定期定額
  price_override numeric,                                 -- null = 用自動報價
  dividend       numeric,                                 -- null = 依除息紀錄自動計算
  updated_at     timestamptz not null default now(),
  primary key (user_id, id)
);

-- 只能看到與修改自己的資料。
-- 網站是公開的靜態頁面，anon key 任何人都拿得到，
-- 這條規則才是實際的防線：沒登入或不是本人，一列都讀不到。
alter table public.holdings enable row level security;

drop policy if exists "holdings are private" on public.holdings;
create policy "holdings are private"
  on public.holdings
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create index if not exists holdings_user_idx on public.holdings (user_id);

-- 每次更新自動蓋時間戳
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists holdings_touch on public.holdings;
create trigger holdings_touch
  before update on public.holdings
  for each row execute function public.touch_updated_at();


-- ── 賣出紀錄（2026-08 新增）────────────────────────────
-- 每一列是一個「部位切片」：有 sell_date 就是已結束的部位，沒有就是持有中。
-- 部分賣出時把原本那列拆成兩列，買進手續費按股數比例分攤。
-- 已經建過表的話，單獨執行這段即可。

alter table public.holdings add column if not exists sell_date  date;
alter table public.holdings add column if not exists sell_price numeric;
alter table public.holdings add column if not exists sell_fee   numeric;  -- null = 用標準費率
alter table public.holdings add column if not exists sell_tax   numeric;  -- null = 用標準稅率

create index if not exists holdings_open_idx
  on public.holdings (user_id) where sell_date is null;
