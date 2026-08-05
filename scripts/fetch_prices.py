#!/usr/bin/env python3
"""
抓取台股當日收盤行情，輸出成 prices.json 供前端頁面讀取。

資料來源：
  - 上市（TWSE）：https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
  - 上櫃（TPEx）：https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes

兩個來源都是公開 OpenAPI，不需要金鑰。任一來源失敗不會中斷整個流程，
只要至少有一個成功就會寫出檔案。
"""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

TWSE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"

# 上市依序嘗試，取交易日最新的一份。
# OpenAPI 版本觀察到會落後一個交易日，官網版本據稱有當日資料，兩邊都抓再比。
TWSE_SOURCES = [
    ("OpenAPI", TWSE_URL),
    ("官網open_data", "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data"),
]

# 櫃買中心的端點名稱歷年改過，依序嘗試，取第一個能解析出資料的
TPEX_URLS = [
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
]

TIMEOUT = 40
TPE = timezone(timedelta(hours=8))


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
    """行情欄位都是字串，且可能出現 '--'、'' 或帶千分位逗號。"""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in ("", "--", "---", "N/A", "null"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def roc_to_iso(roc):
    """民國日期字串 '1150731' 轉成 '2026-07-31'。"""
    digits = "".join(ch for ch in str(roc) if ch.isdigit())
    if len(digits) < 7:
        return None
    try:
        year = int(digits[:-4]) + 1911
        return f"{year:04d}-{digits[-4:-2]}-{digits[-2:]}"
    except ValueError:
        return None


def pick(row, *keys):
    """櫃買的欄位名稱不太固定，依序找第一個存在的鍵。"""
    for key in keys:
        if key in row and str(row[key]).strip() != "":
            return row[key]
    return None


def parse_twse(rows):
    """解析上市行情列表，回傳 (資料, 交易日)。"""
    out = {}
    trade_date = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(pick(row, "Code", "證券代號", "股票代號") or "").strip()
        close = to_float(pick(row, "ClosingPrice", "收盤價"))
        if not code or close is None:
            continue
        if trade_date is None:
            trade_date = roc_to_iso(pick(row, "Date", "日期") or "")
        out[code] = {
            "name": str(pick(row, "Name", "證券名稱", "股票名稱") or "").strip(),
            "close": close,
            "change": to_float(pick(row, "Change", "漲跌價差")) or 0.0,
            "market": "上市",
        }
    return out, trade_date


def fetch_twse():
    """抓所有上市來源，回傳交易日最新的一份。"""
    best, best_date, best_label = {}, None, None
    for label, url in TWSE_SOURCES:
        try:
            rows = http_get_json(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  [上市/{label}] 抓取失敗：{exc}", file=sys.stderr)
            continue

        data, date = parse_twse(rows if isinstance(rows, list) else [])
        if not data:
            print(f"  [上市/{label}] 沒有解析出資料", file=sys.stderr)
            continue

        print(f"  [上市/{label}] {len(data)} 檔，交易日 {date}")
        # 日期較新者勝；抓不到日期的來源只在沒有其他選擇時採用
        if best_date is None or (date is not None and date > best_date):
            best, best_date, best_label = data, date, label

    if best_label:
        print(f"  [上市] 採用 {best_label}（交易日 {best_date}）")
    return best, best_date


def fetch_tpex():
    last_error = None
    for url in TPEX_URLS:
        try:
            rows = http_get_json(url)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue

        if not isinstance(rows, list) or not rows:
            continue

        out = {}
        trade_date = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = pick(row, "SecuritiesCompanyCode", "Code", "股票代號", "代號")
            close = to_float(pick(row, "Close", "ClosingPrice", "收盤", "收盤價"))
            if not code or close is None:
                continue
            code = str(code).strip()
            if trade_date is None:
                raw_date = pick(row, "Date", "date", "資料日期")
                if raw_date:
                    trade_date = roc_to_iso(raw_date)
            out[code] = {
                "name": str(
                    pick(row, "CompanyName", "Name", "公司名稱", "名稱") or ""
                ).strip(),
                "close": close,
                "change": to_float(pick(row, "Change", "漲跌", "漲跌價差")) or 0.0,
                "market": "上櫃",
            }
        if out:
            return out, trade_date

    if last_error:
        print(f"[warn] 上櫃資料抓取失敗：{last_error}", file=sys.stderr)
    return {}, None


def main():
    prices = {}
    trade_date = None
    sources = []

    dates = []

    try:
        twse, date_twse = fetch_twse()
        if twse:
            prices.update(twse)
            sources.append(f"上市 {len(twse)} 檔")
            if date_twse:
                dates.append(date_twse)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] 上市資料抓取失敗：{exc}", file=sys.stderr)

    try:
        tpex, date_tpex = fetch_tpex()
        if tpex:
            prices.update(tpex)
            sources.append(f"上櫃 {len(tpex)} 檔")
            print(f"  [上櫃] {len(tpex)} 檔，交易日 {date_tpex}")
            if date_tpex:
                dates.append(date_tpex)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] 上櫃資料抓取失敗：{exc}", file=sys.stderr)

    # 兩市場日期不同時取較舊的，寧可低報也不要讓使用者以為資料比實際新
    trade_date = min(dates) if dates else None
    if len(set(dates)) > 1:
        print(f"[warn] 兩市場交易日不一致：{sorted(set(dates))}，保守標示為 {trade_date}",
              file=sys.stderr)

    if not prices:
        print("[fatal] 兩個來源都沒有資料，不覆寫既有的 prices.json", file=sys.stderr)
        return 1

    payload = {
        "updatedAt": datetime.now(TPE).isoformat(timespec="seconds"),
        "tradeDate": trade_date,
        "tradeDates": sorted(set(dates)),
        "count": len(prices),
        "sources": sources,
        "prices": prices,
    }

    with open("prices.json", "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))

    print(f"[done] 已寫入 prices.json，共 {len(prices)} 檔，交易日 {trade_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
