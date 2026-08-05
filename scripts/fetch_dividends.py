#!/usr/bin/env python3
"""
累積台股除權息事件，輸出成 dividends.json 供前端計算累計配息。

重要限制：證交所與櫃買的公開 API 多半只提供「當期」資料，沒有歷史區間查詢。
因此本腳本採「逐日累積」策略 —— 每天抓當期公告並合併進 dividends.json，
歷史深度隨時間長出來。腳本啟用之前的除息紀錄抓不回來，需在頁面手動輸入。

合併規則：以 代號|除息日 為唯一鍵，已存在的事件不會被覆寫。
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

TIMEOUT = 40
TPE = timezone(timedelta(hours=8))
OUTPUT = "dividends.json"

# 依序嘗試；欄位名稱各端點不同，靠 pick() 容錯
SOURCES = [
    ("上市-除權除息計算結果", "https://openapi.twse.com.tw/v1/exchangeReport/TWT49U"),
    ("上市-除權除息預告", "https://openapi.twse.com.tw/v1/exchangeReport/TWT48U"),
    ("上櫃-除權息", "https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost"),
]

# 各欄位的候選鍵名（中英混雜，端點之間不一致）
KEYS_CODE = ("Code", "SecuritiesCompanyCode", "StockID", "股票代號", "證券代號", "公司代號")
KEYS_NAME = ("Name", "CompanyName", "股票名稱", "證券名稱", "公司名稱")
KEYS_DATE = ("Date", "ExRightsExDividendDate", "ExDate", "除權息交易日", "除權除息交易日", "資料日期", "除息交易日")
KEYS_CASH = (
    "CashDividend", "CashEarningsDistribution", "現金股利", "息值",
    "股東配發-盈餘分配之現金股利(元/股)", "權值+息值",
)
KEYS_STOCK = ("StockDividend", "權值", "股東配發-盈餘轉增資配股(元/股)")
KEYS_TYPE = ("Type", "權/息", "除權息", "類別")


def http_get_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; stock-portfolio/1.0)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def to_float(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("元", "")
    if text in ("", "--", "---", "N/A", "null", "-"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def roc_to_iso(raw):
    """民國 '1150716' 或 '115/07/16' -> '2026-07-16'；已是西元格式則原樣回傳。"""
    if not raw:
        return None
    text = str(raw).strip()
    if len(text) == 10 and text[4] in "-/":
        return text.replace("/", "-")
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 8 and digits.startswith(("19", "20")):
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    if len(digits) < 7:
        return None
    try:
        return f"{int(digits[:-4]) + 1911:04d}-{digits[-4:-2]}-{digits[-2:]}"
    except ValueError:
        return None


def pick(row, keys):
    for key in keys:
        if key in row and str(row[key]).strip() != "":
            return row[key]
    return None


def parse_rows(label, rows):
    """把任一來源的資料列轉成統一格式，無法解析的列直接跳過。"""
    events = {}
    if not isinstance(rows, list) or not rows:
        return events

    # 印出第一列的鍵名，方便日後在 Actions log 裡對照欄位是否改名
    print(f"  [{label}] 欄位：{list(rows[0].keys())[:12]}")

    for row in rows:
        if not isinstance(row, dict):
            continue
        code = pick(row, KEYS_CODE)
        ex_date = roc_to_iso(pick(row, KEYS_DATE))
        if not code or not ex_date:
            continue

        cash = to_float(pick(row, KEYS_CASH)) or 0.0
        stock = to_float(pick(row, KEYS_STOCK)) or 0.0

        # 「權值+息值」這類合併欄位，若標記為純除權則不算現金
        marker = str(pick(row, KEYS_TYPE) or "")
        if "權" in marker and "息" not in marker:
            cash = 0.0

        if cash <= 0 and stock <= 0:
            continue

        key = f"{str(code).strip()}|{ex_date}"
        events[key] = {
            "code": str(code).strip(),
            "name": str(pick(row, KEYS_NAME) or "").strip(),
            "exDate": ex_date,
            "cash": round(cash, 4),
            "stock": round(stock, 4),
        }
    return events


def load_existing():
    if not os.path.exists(OUTPUT):
        return {}
    try:
        with open(OUTPUT, encoding="utf-8") as handle:
            data = json.load(handle)
        return {f"{e['code']}|{e['exDate']}": e for e in data.get("events", [])}
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 既有 {OUTPUT} 無法讀取，視為空的：{exc}", file=sys.stderr)
        return {}


def main():
    existing = load_existing()
    before = len(existing)
    print(f"[info] 既有事件 {before} 筆")

    found_any = False
    for label, url in SOURCES:
        try:
            rows = http_get_json(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  [{label}] 抓取失敗：{exc}", file=sys.stderr)
            continue

        parsed = parse_rows(label, rows)
        if parsed:
            found_any = True
        new_keys = [k for k in parsed if k not in existing]
        existing.update({k: v for k, v in parsed.items() if k not in existing})
        print(f"  [{label}] 解析 {len(parsed)} 筆，新增 {len(new_keys)} 筆")

    if not found_any and before == 0:
        print("[warn] 所有來源都沒有解析出事件，仍會寫出空檔案", file=sys.stderr)

    events = sorted(existing.values(), key=lambda e: (e["exDate"], e["code"]), reverse=True)
    payload = {
        "updatedAt": datetime.now(TPE).isoformat(timespec="seconds"),
        "note": "逐日累積，啟用前的歷史除息不含在內",
        "count": len(events),
        "events": events,
    }
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))

    print(f"[done] 已寫入 {OUTPUT}，共 {len(events)} 筆（新增 {len(events) - before}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
