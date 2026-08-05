#!/usr/bin/env python3
"""
抓取台股當日收盤行情，輸出成 prices.json 供前端頁面讀取。

資料來源：
  - 上市：證交所 OpenAPI 與官網 API 都抓，取交易日較新者
    （OpenAPI 實測落後一個交易日；官網路徑改版過，列多個候選逐個試）
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
# OpenAPI 版本實測會落後一個交易日；官網 API 路徑改版過數次，列多個候選逐個試。
TWSE_OPENAPI = ("OpenAPI", TWSE_URL)


def twse_site_sources():
    """證交所官網候選網址，MI_INDEX 需要帶日期。"""
    d = datetime.now(TPE).strftime("%Y%m%d")
    return [
        ("官網rwd/STOCK_DAY_ALL",
         "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL?response=json"),
        ("官網STOCK_DAY_ALL",
         "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json"),
        ("官網rwd/MI_INDEX",
         f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={d}&type=ALLBUT0999&response=json"),
        ("官網MI_INDEX",
         f"https://www.twse.com.tw/exchangeReport/MI_INDEX?date={d}&type=ALLBUT0999&response=json"),
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
    """民國 '1150731' → '2026-07-31'；已是西元格式（20260805、2026-08-05）則原樣轉換。"""
    if not roc:
        return None
    text = str(roc).strip()
    if len(text) == 10 and text[4] in "-/":
        return text.replace("/", "-")
    digits = "".join(ch for ch in text if ch.isdigit())
    # 八碼且以 19/20 開頭視為西元，否則按民國年加 1911
    if len(digits) == 8 and digits.startswith(("19", "20")):
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
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


def _tables_from(payload):
    """
    把各種回應攤平成 (fields, rows) 的清單。證交所有三種格式：
      1. 直接是 dict 陣列（OpenAPI）
      2. {"fields":[...], "data":[[...]]}（舊版官網）
      3. {"tables":[{"fields":[...], "data":[...]}]} 或 fields9/data9（MI_INDEX）
    """
    out = []
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict):
            out.append((None, payload))
        return out
    if not isinstance(payload, dict):
        return out

    if isinstance(payload.get("tables"), list):
        for t in payload["tables"]:
            if isinstance(t, dict) and isinstance(t.get("fields"), list) and isinstance(t.get("data"), list):
                out.append((t["fields"], t["data"]))

    if isinstance(payload.get("fields"), list) and isinstance(payload.get("data"), list):
        out.append((payload["fields"], payload["data"]))

    for key in payload:
        if key.startswith("data") and key != "data":
            fkey = "fields" + key[4:]
            if isinstance(payload.get(fkey), list) and isinstance(payload[key], list):
                out.append((payload[fkey], payload[key]))
    return out


import re

# 只保留個股與 ETF：四碼股票（含特別股尾碼字母）、00 開頭的 ETF。
# 權證（03xxxx）、ETN（02xxxx）、可轉債等六碼代號一律排除。
_KEEP_CODE = re.compile(r"^(?:\d{4}[A-Z]?|00\d{2,4}[A-Z]?)$", re.I)


def is_tradable(code):
    return bool(_KEEP_CODE.match(str(code).strip()))


def _col(fields, *needles):
    """在欄位名稱清單中找出第一個符合的索引。"""
    for i, f in enumerate(fields):
        text = str(f)
        for n in needles:
            if n in text:
                return i
    return None


def parse_twse(payload, fallback_date=None):
    """解析上市行情，回傳 (資料, 交易日)。吃得下 dict 陣列與 fields/data 陣列兩種。"""
    best, best_date, best_skipped = {}, None, 0

    for fields, rows in _tables_from(payload):
        out, date, skipped = {}, None, 0

        if fields is None:                      # dict 陣列
            for row in rows:
                if not isinstance(row, dict):
                    continue
                code = str(pick(row, "Code", "證券代號", "股票代號") or "").strip()
                close = to_float(pick(row, "ClosingPrice", "收盤價"))
                if not code or close is None:
                    continue
                if not is_tradable(code):
                    skipped += 1
                    continue
                if date is None:
                    date = roc_to_iso(pick(row, "Date", "日期") or "")
                out[code] = {
                    "name": str(pick(row, "Name", "證券名稱", "股票名稱") or "").strip(),
                    "close": close,
                    "change": to_float(pick(row, "Change", "漲跌價差")) or 0.0,
                    "market": "上市",
                }
        else:                                    # fields + data 陣列
            i_code = _col(fields, "證券代號", "股票代號", "Code")
            i_close = _col(fields, "收盤價", "ClosingPrice")
            i_name = _col(fields, "證券名稱", "股票名稱", "Name")
            i_chg = _col(fields, "漲跌價差", "Change")
            if i_code is None or i_close is None:
                continue
            for row in rows:
                if not isinstance(row, list) or len(row) <= max(i_code, i_close):
                    continue
                code = str(row[i_code]).strip().strip('="')
                close = to_float(row[i_close])
                if not code or close is None:
                    continue
                if not is_tradable(code):
                    skipped += 1
                    continue
                out[code] = {
                    "name": str(row[i_name]).strip() if i_name is not None and len(row) > i_name else "",
                    "close": close,
                    "change": (to_float(row[i_chg]) or 0.0) if i_chg is not None and len(row) > i_chg else 0.0,
                    "market": "上市",
                }

        if out and len(out) > len(best):
            best, best_date, best_skipped = out, date, skipped

    if best_date is None:
        best_date = fallback_date
    return best, best_date, best_skipped


def fetch_twse():
    """抓所有上市來源，回傳交易日最新的一份。"""
    best, best_date, best_label = {}, None, None

    for label, url in [TWSE_OPENAPI] + twse_site_sources():
        try:
            payload = http_get_json(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  [上市/{label}] 抓取失敗：{exc}", file=sys.stderr)
            continue

        # 官網回應常帶 date 欄位（YYYYMMDD）
        fallback = None
        if isinstance(payload, dict) and payload.get("date"):
            fallback = roc_to_iso(payload["date"])
        data, date, skipped = parse_twse(payload, fallback)

        if not data:
            print(f"  [上市/{label}] 沒有解析出資料", file=sys.stderr)
            continue

        extra = f"，濾除非個股 {skipped} 筆" if skipped else ""
        print(f"  [上市/{label}] {len(data)} 檔，交易日 {date}{extra}")
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
