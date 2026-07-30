#!/usr/bin/env python3
"""Search and optionally archive HKEXnews filings by issuer stock code.

This helper uses the same public HKEXnews endpoints that power the website:
1. prefix.do resolves a ticker/code to HKEX stockId.
2. titleSearchServlet.do returns filing metadata for that stockId.

The title-search response contains a nested JSON string in the `result` field.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://www1.hkexnews.hk"
PREFIX_ENDPOINT = f"{BASE}/search/prefix.do"
TITLE_ENDPOINT = f"{BASE}/search/titleSearchServlet.do"
USER_AGENT = "Mozilla/5.0 (compatible; Codex-HKEX-Filings-Search/1.0)"


def fetch_text(url: str, timeout: int = 30) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - official HTTPS endpoint supplied by script
        return response.read().decode("utf-8", errors="replace")


def fetch_bytes(url: str, timeout: int = 60) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - official HTTPS endpoint supplied by script
        return response.read()


def parse_jsonp(raw: str) -> Any:
    match = re.search(r"^[^(]+\((.*)\)\s*;?\s*$", raw, flags=re.S)
    if not match:
        raise ValueError("Expected JSONP response from HKEX prefix.do")
    return json.loads(match.group(1))


def normalize_code(code: str) -> str:
    digits = re.sub(r"\D", "", code)
    return digits.zfill(5) if digits else code.strip()


def resolve_stock_id(code: str, market: str, lang: str) -> dict[str, Any]:
    normalized = normalize_code(code)
    params = {
        "callback": "callback",
        "lang": "EN" if lang.upper().startswith("E") else "ZH",
        "type": "A",
        "name": normalized,
        "market": market,
    }
    raw = fetch_text(f"{PREFIX_ENDPOINT}?{urlencode(params)}")
    payload = parse_jsonp(raw)
    if isinstance(payload, dict):
        matches = payload.get("stockInfo") or payload.get("data") or payload.get("result") or []
    else:
        matches = payload
    if not isinstance(matches, list):
        raise ValueError(f"Unexpected prefix.do matches type: {type(matches).__name__}")

    exact = [item for item in matches if str(item.get("code", "")).zfill(5) == normalized]
    if not exact:
        available = ", ".join(str(item.get("code")) for item in matches[:10])
        raise ValueError(f"No exact HKEX code match for {normalized}. Available: {available}")
    if len(exact) > 1:
        issuer_names = ", ".join(str(item.get("name")) for item in exact)
        raise ValueError(f"Multiple exact matches for {normalized}: {issuer_names}")
    return exact[0]


def title_search(stock_id: str, from_date: str, to_date: str, market: str, row_range: int, lang: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    params = {
        "sortDir": "0",
        "sortByOptions": "DateTime",
        "category": "0",
        "market": market,
        "stockId": stock_id,
        "documentType": "-1",
        "fromDate": from_date,
        "toDate": to_date,
        "title": "",
        "searchType": "0",
        "t1code": "-2",
        "t2Gcode": "-2",
        "t2code": "-2",
        "rowRange": str(row_range),
        "lang": "E" if lang.upper().startswith("E") else "C",
    }
    payload = json.loads(fetch_text(f"{TITLE_ENDPOINT}?{urlencode(params)}"))
    result_raw = payload.get("result", "[]")
    rows = json.loads(result_raw) if isinstance(result_raw, str) else result_raw
    if not isinstance(rows, list):
        raise ValueError(f"Unexpected title search result type: {type(rows).__name__}")
    return payload, rows


def filing_url(row: dict[str, Any]) -> str:
    link = str(row.get("FILE_LINK") or row.get("fileLink") or "")
    if not link:
        return ""
    if link.startswith("http"):
        return link
    return f"{BASE}{link}"


def row_date(row: dict[str, Any]) -> str:
    raw = str(row.get("DATE_TIME") or row.get("DateTime") or row.get("dateTime") or "")
    match = re.search(r"(\d{4})/(\d{2})/(\d{2})", raw)
    if match:
        return "-".join(match.groups())
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if match:
        return "-".join(match.groups())
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", raw)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return "unknown-date"


def row_title(row: dict[str, Any]) -> str:
    candidates = [row.get("TITLE"), row.get("LONG_TEXT"), row.get("SHORT_TEXT"), row.get("headline")]
    text = " ".join(str(item) for item in candidates if item)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return text or "untitled"


def safe_name(text: str, max_len: int = 120) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return (cleaned or "filing")[:max_len]


def write_raw_json(path: Path, stock: dict[str, Any], payload: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapped = {
        "fetched_at_epoch": int(time.time()),
        "stock": stock,
        "payload": payload,
        "rows": rows,
    }
    path.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2), encoding="utf-8")


def download_rows(rows: list[dict[str, Any]], download_dir: Path, pattern: str | None, extract_text: bool) -> list[Path]:
    download_dir.mkdir(parents=True, exist_ok=True)
    regex = re.compile(pattern, re.I) if pattern else None
    pdftotext = shutil.which("pdftotext")
    saved: list[Path] = []

    for row in rows:
        title = row_title(row)
        if regex and not regex.search(title):
            continue
        url = filing_url(row)
        if not url:
            print(f"[WARN] Missing FILE_LINK for: {title}", file=sys.stderr)
            continue
        filename = f"{row_date(row)}_{safe_name(title)}.pdf"
        dest = download_dir / filename
        if not dest.exists():
            try:
                dest.write_bytes(fetch_bytes(url))
            except (HTTPError, URLError, TimeoutError) as exc:
                print(f"[WARN] Download failed: {url} ({exc})", file=sys.stderr)
                continue
        saved.append(dest)
        if extract_text and pdftotext:
            txt_dest = dest.with_suffix(dest.suffix + ".txt")
            if not txt_dest.exists():
                subprocess.run([pdftotext, "-layout", str(dest), str(txt_dest)], check=False)
        elif extract_text and not pdftotext:
            print("[WARN] --extract-text requested but pdftotext is not installed", file=sys.stderr)
            extract_text = False
    return saved


def print_table(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        code = str(row.get("STOCK_CODE") or row.get("stockCode") or "")
        print(f"{row_date(row)}	{code}	{row_title(row)}	{filing_url(row)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Search HKEXnews title filings by Hong Kong stock code.")
    parser.add_argument("stock_code", help="HKEX stock code.")
    parser.add_argument("--from-date", required=True, help="Start date as YYYYMMDD")
    parser.add_argument("--to-date", required=True, help="End date as YYYYMMDD")
    parser.add_argument("--market", default="SEHK", help="HKEX market, default: SEHK")
    parser.add_argument("--row-range", type=int, default=200, help="Rows to request, default: 200")
    parser.add_argument("--lang", default="E", choices=["E", "C", "EN", "ZH"], help="Search language")
    parser.add_argument("--out-json", type=Path, help="Path to save raw search payload and parsed rows")
    parser.add_argument("--print-table", action="store_true", help="Print date, code, title, URL TSV")
    parser.add_argument("--download-dir", type=Path, help="Directory to download matched PDFs")
    parser.add_argument("--download-filter", help="Case-insensitive regex applied to filing titles before download")
    parser.add_argument("--extract-text", action="store_true", help="Run pdftotext -layout beside downloaded PDFs")
    args = parser.parse_args()

    for label, value in [("from-date", args.from_date), ("to-date", args.to_date)]:
        if not re.fullmatch(r"\d{8}", value):
            parser.error(f"--{label} must be YYYYMMDD")

    try:
        stock = resolve_stock_id(args.stock_code, args.market, args.lang)
        payload, rows = title_search(str(stock["stockId"]), args.from_date, args.to_date, args.market, args.row_range, args.lang)
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(f"Resolved {stock.get('code')} {stock.get('name')} stockId={stock.get('stockId')}", file=sys.stderr)
    print(f"Rows: {len(rows)}", file=sys.stderr)

    if args.out_json:
        write_raw_json(args.out_json, stock, payload, rows)
        print(f"Saved raw JSON: {args.out_json}", file=sys.stderr)

    if args.print_table:
        print_table(rows)

    if args.download_dir:
        saved = download_rows(rows, args.download_dir, args.download_filter, args.extract_text)
        print(f"Downloaded/kept PDFs: {len(saved)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
