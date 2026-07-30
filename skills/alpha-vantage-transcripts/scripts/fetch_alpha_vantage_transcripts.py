#!/usr/bin/env python3
"""Fetch Alpha Vantage earnings call transcripts as JSON files."""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

API_URL = "https://www.alphavantage.co/query"

try:
    import requests
except ImportError:
    requests = None
    import urllib.request


def fetch_transcript(api_key: str, symbol: str, quarter: str) -> dict:
    params = {
        "function": "EARNINGS_CALL_TRANSCRIPT",
        "symbol": symbol,
        "quarter": quarter,
        "apikey": api_key,
    }

    if requests is not None:
        response = requests.get(API_URL, params=params, timeout=40)
        print(f"HTTP status: {response.status_code}")
        response.raise_for_status()
        return response.json()

    with urllib.request.urlopen(f"{API_URL}?{urlencode(params)}", timeout=40) as response:
        print(f"HTTP status: {response.status}")
        return json.load(response)


def expand_quarters(args: argparse.Namespace) -> list[str]:
    if args.quarters:
        return args.quarters
    if args.years:
        return [f"{year}Q{quarter}" for year in args.years for quarter in range(1, 5)]
    return [args.quarter]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch earnings call transcripts from Alpha Vantage."
    )
    parser.add_argument("--symbol", required=True, help="Issuer symbol.")
    parser.add_argument("--quarter", help="Single quarter in YYYYQn form.")
    parser.add_argument(
        "--quarters",
        nargs="+",
        default=None,
        help="Explicit quarters to fetch, e.g. --quarters 2024Q4 2025Q1.",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=None,
        help="Fetch Q1-Q4 for each year, e.g. --years 2024 2025.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("ALPHA_VANTAGE_API_KEY"),
        help="Alpha Vantage API key. Defaults to ALPHA_VANTAGE_API_KEY when set.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output JSON path for a single quarter.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for saved JSON files. Relative paths resolve from the current working directory.",
    )
    args = parser.parse_args()

    if not args.api_key:
        print("Missing API key. Set ALPHA_VANTAGE_API_KEY or pass --api-key.", file=sys.stderr)
        return 2

    if not args.quarter and not args.quarters and not args.years:
        print("Specify --quarter, --quarters, or --years.", file=sys.stderr)
        return 2

    quarters = expand_quarters(args)
    if args.output and len(quarters) != 1:
        print("--output can only be used when fetching a single quarter.", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for quarter in quarters:
        print(f"\nFetching {args.symbol} {quarter}...")
        data = fetch_transcript(args.api_key, args.symbol, quarter)

        output = Path(args.output).expanduser() if args.output else output_dir / f"{args.symbol}_{quarter}.json"
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        redacted = json.dumps(data, ensure_ascii=False, indent=2).replace(args.api_key, "[REDACTED_API_KEY]")
        print(redacted[:4000])
        print(f"\nSaved full response to: {output.resolve()}")

        transcript = data.get("transcript") if isinstance(data, dict) else None
        if isinstance(transcript, list):
            status = f"transcript turns: {len(transcript)}"
        elif transcript:
            status = "transcript field found"
        else:
            status = "no transcript field found"
        summary.append((quarter, status, output.resolve()))
        print(status.capitalize() + ".")

    if len(summary) > 1:
        print("\nSummary:")
        for quarter, status, output in summary:
            print(f"- {quarter}: {status}; saved to {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
