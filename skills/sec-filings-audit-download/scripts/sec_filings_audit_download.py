from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


SOURCE_INDEX_FIELDS = [
    "company",
    "source_title",
    "source_type",
    "regulator_or_site",
    "filing_date",
    "period",
    "local_path",
    "url",
    "accessed_at",
    "reliability_rank",
    "notes",
]

MANIFEST_FIELDS = [
    "company",
    "company_name",
    "cik",
    "accessionNumber",
    "filingDate",
    "reportDate",
    "form",
    "primaryDocument",
    "primaryDocDescription",
    "sec_url",
    "local_path",
    "downloaded_at",
    "status",
    "document_scope",
    "document_count",
    "notes",
]

DEFAULT_USER_AGENT = ""


def seven_calendar_years_before(day: date) -> date:
    """Return the same calendar date seven years earlier, handling leap day."""
    try:
        return day.replace(year=day.year - 7)
    except ValueError:
        return day.replace(year=day.year - 7, day=28)


@dataclass(frozen=True)
class Filing:
    accession_number: str
    filing_date: str
    report_date: str
    form: str
    primary_document: str
    primary_doc_description: str


@dataclass(frozen=True)
class AuditResult:
    official_count: int
    local_accession_count: int
    complete_accession_count: int
    missing_accessions: list[str]
    extra_accessions: list[str]
    partial_accessions: list[str]
    missing_local_paths: list[str]
    missing_complete_submissions: list[str]
    missing_primary_documents: list[str]

    @property
    def complete(self) -> bool:
        return not any(
            (
                self.missing_accessions,
                self.partial_accessions,
                self.missing_local_paths,
                self.missing_complete_submissions,
                self.missing_primary_documents,
            )
        )

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["complete"] = self.complete
        return value


def filing_records_from_columns(
    columns: dict[str, list[str]], start_date: str, end_date: str
) -> list[Filing]:
    accessions = columns.get("accessionNumber", [])

    def get(field: str, index: int) -> str:
        values = columns.get(field, [])
        return values[index] if index < len(values) and values[index] else ""

    records: list[Filing] = []
    for index, accession in enumerate(accessions):
        filing_date = get("filingDate", index)
        if not start_date <= filing_date <= end_date:
            continue
        records.append(
            Filing(
                accession_number=accession,
                filing_date=filing_date,
                report_date=get("reportDate", index),
                form=get("form", index),
                primary_document=get("primaryDocument", index),
                primary_doc_description=get("primaryDocDescription", index),
            )
        )
    return records


def resolve_recorded_path(project_root: Path, recorded_path: str) -> Path:
    path = Path(recorded_path)
    if path.is_absolute():
        return path
    candidates = (project_root / path, project_root.parent / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_local_manifest_rows(
    official_root: Path, start_date: str, end_date: str
) -> dict[str, dict[str, str]]:
    rows_by_accession: dict[str, dict[str, str]] = {}
    for manifest in sorted(official_root.glob("sec_archive_manifest_*.csv")):
        with manifest.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                accession = row.get("accessionNumber", "")
                filing_date = row.get("filingDate", "")
                if not accession or not start_date <= filing_date <= end_date:
                    continue
                previous = rows_by_accession.get(accession)
                if previous is None or (
                    previous.get("status") != "downloaded"
                    and row.get("status") == "downloaded"
                ):
                    rows_by_accession[accession] = row
    return rows_by_accession


def compact_accession(accession_number: str) -> str:
    return accession_number.replace("-", "")


def normalize_cik(cik: str) -> str:
    return str(int(str(cik).strip()))


def safe_name(value: str) -> str:
    cleaned = value.strip().replace("/", "-")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned)
    return cleaned.strip("._") or "unknown"


def submissions_url(cik: str) -> str:
    return f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"


def historical_submissions_url(file_name: str) -> str:
    return f"https://data.sec.gov/submissions/{file_name}"


def company_tickers_url() -> str:
    return "https://www.sec.gov/files/company_tickers.json"


def accession_folder_url(cik: str, filing: Filing) -> str:
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{normalize_cik(cik)}/{compact_accession(filing.accession_number)}/"
    )


def index_json_url(cik: str, filing: Filing) -> str:
    return accession_folder_url(cik, filing) + "index.json"


def complete_submission_url(cik: str, filing: Filing) -> str:
    return accession_folder_url(cik, filing) + f"{filing.accession_number}.txt"


def document_url(cik: str, filing: Filing, name: str) -> str:
    quoted = "/".join(urllib.parse.quote(part) for part in name.split("/"))
    return accession_folder_url(cik, filing) + quoted


def _folder_filing_date(folder: Path) -> str:
    match = re.match(r"(\d{4}-\d{2}-\d{2})_", folder.name)
    return match.group(1) if match else ""


def discover_archive_folders(
    official_root: Path, start_date: str, end_date: str
) -> dict[str, list[Path]]:
    folders: dict[str, list[Path]] = {}
    for folder in official_root.glob("sec_filings_*/*"):
        if not folder.is_dir():
            continue
        filing_date = _folder_filing_date(folder)
        if not start_date <= filing_date <= end_date:
            continue
        compact = folder.name.rsplit("_", 1)[-1]
        if not re.fullmatch(r"\d{18}", compact):
            continue
        accession = f"{compact[:10]}-{compact[10:12]}-{compact[12:]}"
        folders.setdefault(accession, []).append(folder)
    return folders


def archive_root(
    project_root: Path, company: str, start_date: str, end_date: str
) -> Path:
    return (
        project_root
        / "sources"
        / company
        / "official"
        / f"sec_filings_{start_date}_to_{end_date}"
    )


def filing_folder(
    project_root: Path,
    company: str,
    start_date: str,
    end_date: str,
    filing: Filing,
) -> Path:
    name = (
        f"{filing.filing_date}_{safe_name(filing.form)}_"
        f"{compact_accession(filing.accession_number)}"
    )
    return archive_root(project_root, company, start_date, end_date) / name


def required_document_names(
    filing: Filing, index_data: dict, document_scope: str
) -> list[str]:
    submission = f"{filing.accession_number}.txt"
    if document_scope == "submission":
        return [submission]

    names = [submission]
    if filing.primary_document:
        names.append(filing.primary_document)

    items = index_data.get("directory", {}).get("item", [])
    index_names = sorted(
        {
            item.get("name", "")
            for item in items
            if item.get("name") and not item.get("name", "").endswith("/")
        }
    )
    if document_scope == "html":
        suffixes = {".htm", ".html", ".xml", ".txt", ".pdf"}
        names.extend(
            name for name in index_names if Path(name).suffix.lower() in suffixes
        )
    elif document_scope == "full":
        names.extend(index_names)
    elif document_scope != "filing":
        raise ValueError(f"Unsupported document scope: {document_scope}")

    return list(dict.fromkeys(names))


def audit_filings(
    official_filings: list[Filing],
    *,
    project_root: Path,
    company: str,
    start_date: str,
    end_date: str,
    document_scope: str,
) -> AuditResult:
    official_root = project_root / "sources" / company / "official"
    manifest_rows = load_local_manifest_rows(official_root, start_date, end_date)
    folders = discover_archive_folders(official_root, start_date, end_date)
    official_by_accession = {
        filing.accession_number: filing for filing in official_filings
    }
    local_accessions = set(manifest_rows) | set(folders)
    official_accessions = set(official_by_accession)

    missing_accessions = sorted(official_accessions - local_accessions)
    extra_accessions = sorted(local_accessions - official_accessions)
    partial_accessions: list[str] = []
    missing_local_paths: list[str] = []
    missing_complete_submissions: list[str] = []
    missing_primary_documents: list[str] = []

    for accession in sorted(official_accessions & local_accessions):
        filing = official_by_accession[accession]
        accession_folders = folders.get(accession, [])
        manifest = manifest_rows.get(accession)

        if manifest and manifest.get("local_path"):
            local_path = resolve_recorded_path(project_root, manifest["local_path"])
            if not local_path.exists():
                missing_local_paths.append(accession)

        has_submission = any(
            (folder / f"{accession}.txt").exists() for folder in accession_folders
        )
        if not has_submission:
            missing_complete_submissions.append(accession)

        primary_required = document_scope != "submission" and bool(
            filing.primary_document
        )
        has_primary = not primary_required or any(
            (folder / filing.primary_document).exists()
            for folder in accession_folders
        )
        if not has_primary:
            missing_primary_documents.append(accession)

        manifest_partial = bool(
            manifest and manifest.get("status") not in ("", "downloaded")
        )
        if (
            (manifest_partial and (not has_submission or not has_primary))
            or not has_submission
            or not has_primary
            or accession in missing_local_paths
        ):
            partial_accessions.append(accession)

    complete_accession_count = (
        len(official_accessions)
        - len(missing_accessions)
        - len(set(partial_accessions))
    )
    return AuditResult(
        official_count=len(official_accessions),
        local_accession_count=len(local_accessions & official_accessions),
        complete_accession_count=complete_accession_count,
        missing_accessions=missing_accessions,
        extra_accessions=extra_accessions,
        partial_accessions=sorted(set(partial_accessions)),
        missing_local_paths=sorted(set(missing_local_paths)),
        missing_complete_submissions=sorted(
            set(missing_complete_submissions)
        ),
        missing_primary_documents=sorted(set(missing_primary_documents)),
    )


class SecClient:
    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        sleep_seconds: float = 0.12,
        attempts: int = 3,
    ):
        self.sleep_seconds = sleep_seconds
        self.attempts = attempts
        self._last_request = 0.0
        self.user_agent = user_agent

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.sleep_seconds:
            time.sleep(self.sleep_seconds - elapsed)

    def fetch_bytes(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            self._wait()
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": self.user_agent}
                )
                with urllib.request.urlopen(request, timeout=60) as response:
                    content = response.read()
                self._last_request = time.monotonic()
                return content
            except (urllib.error.HTTPError, urllib.error.URLError) as exc:
                last_error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(0.5 * (attempt + 1))
        assert last_error is not None
        raise last_error

    def fetch_json(self, url: str) -> dict:
        return json.loads(self.fetch_bytes(url).decode("utf-8"))


def resolve_cik(company: str, client: SecClient) -> tuple[str, str]:
    ticker = company.upper()
    data = client.fetch_json(company_tickers_url())
    for entry in data.values():
        if str(entry.get("ticker", "")).upper() == ticker:
            return normalize_cik(str(entry["cik_str"])), str(entry.get("title", ""))
    raise ValueError(f"Ticker not found in SEC company_tickers.json: {company}")


def collect_sec_filings(
    cik: str,
    start_date: str,
    end_date: str,
    client: SecClient,
) -> tuple[str, list[Filing]]:
    submissions = client.fetch_json(submissions_url(cik))
    records = filing_records_from_columns(
        submissions.get("filings", {}).get("recent", {}),
        start_date,
        end_date,
    )
    seen = {record.accession_number for record in records}
    for item in submissions.get("filings", {}).get("files", []):
        file_name = item.get("name", "")
        if not file_name:
            continue
        historical = client.fetch_json(historical_submissions_url(file_name))
        for record in filing_records_from_columns(
            historical, start_date, end_date
        ):
            if record.accession_number not in seen:
                records.append(record)
                seen.add(record.accession_number)
    records.sort(key=lambda row: (row.filing_date, row.accession_number))
    return str(submissions.get("name", "")), records


def _write_bytes_atomic(path: Path, data: bytes, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(data)
    temporary.replace(path)
    return True


def _existing_folder_for_filing(
    official_root: Path, filing: Filing
) -> Path | None:
    compact = compact_accession(filing.accession_number)
    candidates = sorted(official_root.glob(f"sec_filings_*/*_{compact}"))
    return candidates[0] if candidates else None


def download_missing_filings(
    official_filings: list[Filing],
    *,
    accessions: Iterable[str],
    project_root: Path,
    company: str,
    cik: str,
    start_date: str,
    end_date: str,
    document_scope: str,
    client: SecClient,
    overwrite: bool,
) -> dict[str, str]:
    selected = set(accessions)
    official_root = project_root / "sources" / company / "official"
    results: dict[str, str] = {}
    for filing in official_filings:
        if filing.accession_number not in selected:
            continue
        folder = _existing_folder_for_filing(official_root, filing) or filing_folder(
            project_root, company, start_date, end_date, filing
        )
        errors: list[str] = []
        index_data: dict = {}
        if document_scope != "submission":
            try:
                index_data = client.fetch_json(index_json_url(cik, filing))
                _write_bytes_atomic(
                    folder / "index.json",
                    json.dumps(index_data, ensure_ascii=False, indent=2).encode(
                        "utf-8"
                    ),
                    overwrite,
                )
            except Exception as exc:  # Keep remaining accessions moving.
                errors.append(f"index: {exc}")

        for name in required_document_names(filing, index_data, document_scope):
            path = folder / name
            if path.exists() and not overwrite:
                continue
            url = (
                complete_submission_url(cik, filing)
                if name == f"{filing.accession_number}.txt"
                else document_url(cik, filing, name)
            )
            try:
                _write_bytes_atomic(path, client.fetch_bytes(url), overwrite)
            except Exception as exc:  # Report accession-level partial state.
                errors.append(f"{name}: {exc}")
        results[filing.accession_number] = " | ".join(errors)
    return results


def source_row_accession(row: dict[str, str]) -> str:
    notes = row.get("notes", "")
    match = re.search(r"\baccession\s+(\d{10}-\d{2}-\d{6})\b", notes, re.I)
    return match.group(1) if match else ""


def _write_csv(
    path: Path,
    rows: Iterable[dict[str, str]],
    fields: list[str],
    *,
    encoding: str = "utf-8-sig",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def merge_source_index(
    path: Path, candidate_rows: Iterable[dict[str, str]]
) -> list[dict[str, str]]:
    existing_rows: list[dict[str, str]] = []
    fields = list(SOURCE_INDEX_FIELDS)
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames:
                fields = list(reader.fieldnames)
            existing_rows = list(reader)

    seen = {
        accession
        for accession in (source_row_accession(row) for row in existing_rows)
        if accession
    }
    appended: list[dict[str, str]] = []
    for row in candidate_rows:
        accession = source_row_accession(row)
        if accession and accession in seen:
            continue
        existing_rows.append(row)
        appended.append(row)
        if accession:
            seen.add(accession)

    if appended or not path.exists():
        _write_csv(path, existing_rows, fields)
    return appended


def update_source_index_append(
    path: Path, new_rows: Iterable[dict[str, str]]
) -> list[dict[str, str]]:
    combined: list[dict[str, str]] = []
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as handle:
            combined = list(csv.DictReader(handle))
    seen = {
        accession
        for accession in (source_row_accession(row) for row in combined)
        if accession
    }
    changed = not path.exists()
    for row in new_rows:
        accession = source_row_accession(row)
        if accession and accession in seen:
            continue
        combined.append(row)
        changed = True
        if accession:
            seen.add(accession)
    if changed:
        _write_csv(path, combined, SOURCE_INDEX_FIELDS)
    return combined


def _relative_recorded_path(project_root: Path, path: Path) -> str:
    return str(Path(project_root.name) / path.relative_to(project_root))


def _source_index_row(
    company: str,
    company_name: str,
    cik: str,
    filing: Filing,
    local_path: Path,
    project_root: Path,
    accessed_at: str,
) -> dict[str, str]:
    title = f"{company_name} {filing.filing_date} Form {filing.form}"
    if filing.primary_doc_description:
        title += f" - {filing.primary_doc_description}"
    return {
        "company": company,
        "source_title": title,
        "source_type": filing.form,
        "regulator_or_site": "SEC EDGAR",
        "filing_date": filing.filing_date,
        "period": filing.report_date,
        "local_path": _relative_recorded_path(project_root, local_path),
        "url": (
            document_url(cik, filing, filing.primary_document)
            if filing.primary_document
            else complete_submission_url(cik, filing)
        ),
        "accessed_at": accessed_at,
        "reliability_rank": "1",
        "notes": (
            "Official SEC EDGAR filing archived from company submissions index; "
            f"accession {filing.accession_number}."
        ),
    }


def _manifest_and_source_rows(
    official_filings: list[Filing],
    *,
    project_root: Path,
    company: str,
    company_name: str,
    cik: str,
    start_date: str,
    end_date: str,
    accessed_at: str,
    document_scope: str,
    errors: dict[str, str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    official_root = project_root / "sources" / company / "official"
    manifest_rows: list[dict[str, str]] = []
    source_rows: list[dict[str, str]] = []
    for filing in official_filings:
        folder = _existing_folder_for_filing(official_root, filing) or filing_folder(
            project_root, company, start_date, end_date, filing
        )
        submission = folder / f"{filing.accession_number}.txt"
        primary = (
            folder / filing.primary_document
            if filing.primary_document
            else submission
        )
        primary_required = document_scope != "submission" and bool(
            filing.primary_document
        )
        status = (
            "downloaded"
            if submission.exists()
            and (not primary_required or primary.exists())
            and not errors.get(filing.accession_number)
            else "partial"
        )
        local_path = primary if primary.exists() else submission
        document_count = sum(
            path.exists()
            for path in dict.fromkeys((submission, primary))
        )
        manifest_rows.append(
            {
                "company": company,
                "company_name": company_name,
                "cik": normalize_cik(cik),
                "accessionNumber": filing.accession_number,
                "filingDate": filing.filing_date,
                "reportDate": filing.report_date,
                "form": filing.form,
                "primaryDocument": filing.primary_document,
                "primaryDocDescription": filing.primary_doc_description,
                "sec_url": (
                    document_url(cik, filing, filing.primary_document)
                    if filing.primary_document
                    else complete_submission_url(cik, filing)
                ),
                "local_path": _relative_recorded_path(project_root, local_path),
                "downloaded_at": accessed_at,
                "status": status,
                "document_scope": document_scope,
                "document_count": str(document_count),
                "notes": errors.get(filing.accession_number, ""),
            }
        )
        if status == "downloaded":
            source_rows.append(
                _source_index_row(
                    company,
                    company_name,
                    cik,
                    filing,
                    local_path,
                    project_root,
                    accessed_at,
                )
            )
    return manifest_rows, source_rows


def run_workflow(
    *,
    company: str,
    cik: str,
    company_name: str,
    project_root: Path,
    start_date: str,
    end_date: str,
    accessed_at: str,
    document_scope: str,
    audit_only: bool,
    overwrite: bool,
    client: SecClient,
) -> dict[str, object]:
    sec_name, filings = collect_sec_filings(
        cik, start_date, end_date, client
    )
    resolved_name = company_name or sec_name
    before = audit_filings(
        filings,
        project_root=project_root,
        company=company,
        start_date=start_date,
        end_date=end_date,
        document_scope=document_scope,
    )
    if audit_only:
        return {
            "company": company,
            "cik": normalize_cik(cik),
            "window": {"start": start_date, "end": end_date},
            "audit": before.to_dict(),
        }

    selected = sorted(
        set(before.missing_accessions) | set(before.partial_accessions)
    )
    errors = download_missing_filings(
        filings,
        accessions=selected,
        project_root=project_root,
        company=company,
        cik=cik,
        start_date=start_date,
        end_date=end_date,
        document_scope=document_scope,
        client=client,
        overwrite=overwrite,
    )
    after = audit_filings(
        filings,
        project_root=project_root,
        company=company,
        start_date=start_date,
        end_date=end_date,
        document_scope=document_scope,
    )
    manifest_rows, source_rows = _manifest_and_source_rows(
        filings,
        project_root=project_root,
        company=company,
        company_name=resolved_name,
        cik=cik,
        start_date=start_date,
        end_date=end_date,
        accessed_at=accessed_at,
        document_scope=document_scope,
        errors=errors,
    )
    official_root = project_root / "sources" / company / "official"
    manifest_path = (
        official_root
        / f"sec_archive_manifest_{start_date}_to_{end_date}.csv"
    )
    append_path = official_root / f"source_index_append_{company}_{accessed_at}.csv"
    audit_path = official_root / f"sec_audit_{start_date}_to_{end_date}.json"
    source_index_path = project_root / "data" / "source_index.csv"
    _write_csv(manifest_path, manifest_rows, MANIFEST_FIELDS)
    appended = merge_source_index(source_index_path, source_rows)
    append_rows = update_source_index_append(append_path, appended)

    result: dict[str, object] = {
        "company": company,
        "company_name": resolved_name,
        "cik": normalize_cik(cik),
        "window": {"start": start_date, "end": end_date},
        "pre_audit": before.to_dict(),
        "audit": after.to_dict(),
        "download_requested": selected,
        "download_errors": {
            accession: error for accession, error in errors.items() if error
        },
        "source_index_added": len(appended),
        "source_index_append_rows": len(append_rows),
        "outputs": {
            "manifest": _relative_recorded_path(project_root, manifest_path),
            "audit": _relative_recorded_path(project_root, audit_path),
            "source_index_append": _relative_recorded_path(
                project_root, append_path
            ),
            "source_index": _relative_recorded_path(
                project_root, source_index_path
            ),
        },
        "complete": after.complete,
    }
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    current_day = date.today()
    today = current_day.isoformat()
    default_start_date = seven_calendar_years_before(current_day).isoformat()
    parser = argparse.ArgumentParser(
        description="Archive an SEC filing window or audit and backfill an existing archive."
    )
    parser.add_argument("company")
    parser.add_argument("--cik")
    parser.add_argument("--company-name", default="")
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--start-date",
        default=default_start_date,
        help="First filing date (default: same calendar date seven years ago).",
    )
    parser.add_argument("--end-date", default=today)
    parser.add_argument("--accessed-at", default=today)
    parser.add_argument(
        "--document-scope",
        choices=("submission", "filing", "html", "full"),
        default="submission",
        help="Retention scope: submission (default), filing, html, or full.",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Report accession and local-file gaps without downloading.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--user-agent",
        required=True,
        help="A truthful SEC-compliant User-Agent supplied for this run.",
    )
    parser.add_argument("--sleep-seconds", type=float, default=0.12)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    client = SecClient(args.user_agent, args.sleep_seconds)
    if args.cik:
        cik = normalize_cik(args.cik)
        company_name = args.company_name
    else:
        cik, resolved_name = resolve_cik(args.company, client)
        company_name = args.company_name or resolved_name
    result = run_workflow(
        company=args.company.upper(),
        cik=cik,
        company_name=company_name,
        project_root=project_root,
        start_date=args.start_date,
        end_date=args.end_date,
        accessed_at=args.accessed_at,
        document_scope=args.document_scope,
        audit_only=args.audit_only,
        overwrite=args.overwrite,
        client=client,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["audit"]["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
