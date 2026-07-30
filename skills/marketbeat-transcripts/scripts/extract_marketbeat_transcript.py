#!/opt/homebrew/bin/python3
"""Extract MarketBeat / Quartr earnings call transcript pages to JSON."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup

try:
    import requests
except ImportError:
    requests = None
    import urllib.request


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"
        )
    }
    if requests is not None:
        response = requests.get(url, headers=headers, timeout=40)
        response.raise_for_status()
        return response.text

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def infer_quarter(text: str) -> str | None:
    match = re.search(r"\b(Q[1-4])\s+(\d{4})\b", text, re.IGNORECASE)
    if match:
        return f"{match.group(2)}{match.group(1).upper()}"
    return None


def find_earnings_page(symbol: str, exchange: str | None) -> str:
    if exchange:
        return f"https://www.marketbeat.com/stocks/{exchange.upper()}/{symbol.upper()}/earnings/"

    search_url = f"https://www.marketbeat.com/pages/search.aspx?query={quote_plus(symbol.upper())}"
    soup = BeautifulSoup(fetch_html(search_url), "html.parser")
    earnings_pattern = re.compile(rf"^/stocks/[^/]+/{re.escape(symbol.upper())}/earnings/?$", re.IGNORECASE)
    stock_pattern = re.compile(rf"^/stocks/[^/]+/{re.escape(symbol.upper())}/?$", re.IGNORECASE)
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if earnings_pattern.match(href):
            return urljoin("https://www.marketbeat.com", href)
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if stock_pattern.match(href):
            return urljoin("https://www.marketbeat.com", href.rstrip("/") + "/earnings/")

    for candidate_exchange in ["NASDAQ", "NYSE", "AMEX", "OTCMKTS"]:
        candidate = f"https://www.marketbeat.com/stocks/{candidate_exchange}/{symbol.upper()}/earnings/"
        try:
            html = fetch_html(candidate)
        except Exception:
            continue
        title = BeautifulSoup(html, "html.parser").title
        title_text = title.get_text(" ", strip=True) if title else ""
        if symbol.upper() in title_text.upper() and "EARNINGS" in title_text.upper():
            return candidate

    raise ValueError(
        f"Could not find MarketBeat earnings page for {symbol}. "
        "Try passing --exchange, e.g. --exchange NASDAQ."
    )


def find_report_urls(symbol: str, exchange: str | None) -> list[str]:
    earnings_url = find_earnings_page(symbol, exchange)
    soup = BeautifulSoup(fetch_html(earnings_url), "html.parser")
    urls = []
    seen = set()
    for link in soup.find_all("a", href=True):
        href = link["href"].split("#", 1)[0]
        if "/earnings/reports/" not in href:
            continue
        url = urljoin("https://www.marketbeat.com", href) + "#transcript"
        if url not in seen:
            urls.append(url)
            seen.add(url)
    if not urls:
        raise ValueError(f"No MarketBeat earnings report links found on {earnings_url}.")
    return urls


def find_transcript_by_ticker(symbol: str, quarter: str | None, exchange: str | None) -> tuple[dict, str]:
    errors = []
    for url in find_report_urls(symbol, exchange):
        try:
            data = parse_transcript(fetch_html(url), url, symbol.upper(), None)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            continue
        if quarter is None or data["quarter"].upper() == quarter.upper():
            return data, url
    if quarter:
        raise ValueError(
            f"No MarketBeat transcript matched {symbol.upper()} {quarter}. "
            f"Checked {len(errors)} report pages with parse errors: {len(errors)}."
        )
    raise ValueError(f"No parseable MarketBeat transcripts found for {symbol.upper()}.")


def parse_transcript(html: str, url: str, symbol: str, quarter: str | None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    transcript_root = soup.select_one("#transcript")
    presentation = soup.select_one("#transcriptPresentation")
    if presentation is None:
        raise ValueError("Could not find #transcriptPresentation in MarketBeat page.")

    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    heading_node = soup.find("h1")
    heading = heading_node.get_text(" ", strip=True) if heading_node else ""
    source_note = " | ".join(clean_lines(transcript_root.get_text("\n", strip=True))[:4]) if transcript_root else ""
    resolved_quarter = quarter or infer_quarter(" ".join([heading, page_title, source_note])) or "UNKNOWN"

    transcript = []
    for section in presentation.select('section[class*="transcript-line"]'):
        lines = clean_lines(section.get_text("\n", strip=True))
        if not lines:
            continue
        timestamp_index = next(
            (idx for idx, line in enumerate(lines) if re.fullmatch(r"\d{2}:\d{2}:\d{2}", line)),
            None,
        )
        if timestamp_index is None:
            speaker = lines[0]
            title = lines[1] if len(lines) > 1 else ""
            timestamp = ""
            content = "\n\n".join(lines[2:])
        else:
            speaker = lines[0] if timestamp_index >= 1 else ""
            title = " ".join(lines[1:timestamp_index]) if timestamp_index > 1 else ""
            timestamp = lines[timestamp_index]
            content = "\n\n".join(lines[timestamp_index + 1 :])
        transcript.append(
            {
                "speaker": speaker,
                "title": title,
                "timestamp": timestamp,
                "content": content,
            }
        )

    return {
        "symbol": symbol,
        "quarter": resolved_quarter,
        "source_provider": "MarketBeat / Quartr",
        "source_url": url,
        "page_title": page_title,
        "heading": heading,
        "source_note": source_note,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "transcript": transcript,
    }


def default_output_path(output_dir: Path, symbol: str, quarter: str) -> Path:
    return output_dir / f"{symbol}_{quarter}.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract a MarketBeat / Quartr earnings transcript page to JSON."
    )
    parser.add_argument("--url", help="MarketBeat earnings report URL with transcript section.")
    parser.add_argument("--html-file", help="Saved MarketBeat HTML file to parse instead of fetching URL.")
    parser.add_argument("--symbol", required=True, help="Issuer symbol.")
    parser.add_argument("--exchange", help="Optional MarketBeat exchange path segment, e.g. NASDAQ or NYSE.")
    parser.add_argument("--quarter", help="Quarter label such as 2024Q3. Inferred when possible.")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output JSON.",
    )
    parser.add_argument("--output", help="Explicit output JSON path.")
    args = parser.parse_args()

    if args.url and args.html_file:
        print("Pass only one of --url or --html-file.", file=sys.stderr)
        return 2

    if args.url:
        parsed = urlparse(args.url)
        if "marketbeat.com" not in parsed.netloc:
            print("URL must be a marketbeat.com page.", file=sys.stderr)
            return 2
        html = fetch_html(args.url)
        source_url = args.url
        data = parse_transcript(html, source_url, args.symbol.upper(), args.quarter)
    else:
        if args.html_file:
            html_path = Path(args.html_file).expanduser()
            html = html_path.read_text(encoding="utf-8", errors="replace")
            source_url = html_path.resolve().as_uri()
            data = parse_transcript(html, source_url, args.symbol.upper(), args.quarter)
        else:
            data, source_url = find_transcript_by_ticker(args.symbol, args.quarter, args.exchange)

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = Path(args.output).expanduser() if args.output else default_output_path(
        output_dir, data["symbol"], data["quarter"]
    )
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {output.resolve()}")
    print(f"Transcript turns: {len(data['transcript'])}")
    print(f"Source: {data['source_provider']} {data['source_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
