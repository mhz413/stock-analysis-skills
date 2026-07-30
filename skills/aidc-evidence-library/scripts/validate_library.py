#!/usr/bin/env python3
"""Validate the structural integrity of an Evidence/Event Library."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


CARD_SECTIONS = ("## 基本信息", "## 内容摘要", "## 重要数字", "## 事件标签", "## 可以支持哪些投资结论")
BASE_FILES = ("index.csv", "datapoints.csv", "README.md", "open_items.md")
EVENT_FILES = ("event_library.csv", "event_to_evidence_map.csv", "event_open_items.csv")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def has_bom(path: Path) -> bool:
    return path.read_bytes().startswith(b"\xef\xbb\xbf")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cards_dir", type=Path)
    args = parser.parse_args()
    root = args.cards_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not root.is_dir():
        print(f"ERROR: directory not found: {root}", file=sys.stderr)
        return 2

    for name in BASE_FILES:
        if not (root / name).is_file():
            errors.append(f"missing required file: {name}")

    index_path = root / "index.csv"
    if not index_path.is_file():
        for message in errors:
            print(f"ERROR: {message}")
        return 1

    _, index_rows = read_csv(index_path)
    evidence_ids = [row.get("evidence_id", "").strip() for row in index_rows]
    id_set = set(evidence_ids)
    if "" in id_set:
        errors.append("index.csv contains a blank evidence_id")
    if len(evidence_ids) != len(id_set):
        errors.append("index.csv contains duplicate evidence_id values")

    card_paths = [root / f"{evidence_id}.md" for evidence_id in evidence_ids if evidence_id]
    if len(card_paths) != len(index_rows):
        errors.append("card count does not equal index row count")

    for card in card_paths:
        if not card.is_file():
            errors.append(f"missing Evidence Card: {card.name}")
            continue
        text = card.read_text(encoding="utf-8")
        for section in CARD_SECTIONS:
            if section not in text:
                errors.append(f"{card.name}: missing section {section}")

    for row in index_rows:
        local = row.get("local_path", "").strip()
        if not local:
            errors.append(f"{row.get('evidence_id')}: blank local_path")
            continue
        path = Path(local)
        candidates = (path, root.parents[3] / path, root.parents[2] / path)
        if not path.is_absolute() and not any(candidate.exists() for candidate in candidates):
            warnings.append(f"{row.get('evidence_id')}: local_path not resolved from common roots: {local}")
        elif path.is_absolute() and not path.exists():
            errors.append(f"{row.get('evidence_id')}: local_path does not exist: {local}")

    for csv_path in root.glob("*.csv"):
        if not has_bom(csv_path):
            errors.append(f"CSV lacks UTF-8 BOM: {csv_path.name}")

    present_event_files = [name for name in EVENT_FILES if (root / name).is_file()]
    if present_event_files and len(present_event_files) != len(EVENT_FILES):
        errors.append("Event Library is partial; required CSV files are not all present")
    if len(present_event_files) == len(EVENT_FILES):
        _, events = read_csv(root / "event_library.csv")
        _, mappings = read_csv(root / "event_to_evidence_map.csv")
        _, open_events = read_csv(root / "event_open_items.csv")
        event_ids = [row.get("event_id", "").strip() for row in events]
        event_set = set(event_ids)
        if len(event_ids) != len(event_set):
            errors.append("event_library.csv contains duplicate event_id values")
        mapped_events = {row.get("event_id", "").strip() for row in mappings}
        mapped_evidence = {row.get("evidence_id", "").strip() for row in mappings}
        if event_set - mapped_events:
            errors.append(f"events without mappings: {sorted(event_set - mapped_events)}")
        if mapped_events - event_set:
            errors.append(f"mappings reference unknown events: {sorted(mapped_events - event_set)}")
        if mapped_evidence - id_set:
            errors.append(f"mappings reference unknown evidence: {sorted(mapped_evidence - id_set)}")
        unresolved = {row.get("event_id", "").strip() for row in events if row.get("disputed_or_unresolved", "").strip().lower() == "yes"}
        open_set = {row.get("event_id", "").strip() for row in open_events}
        if unresolved != open_set:
            errors.append("event_open_items.csv does not exactly match unresolved events")

    print(f"Evidence cards: {len(card_paths)}")
    if present_event_files:
        print(f"Event CSV layer: {len(present_event_files)}/{len(EVENT_FILES)} files")
    for message in warnings:
        print(f"WARNING: {message}")
    for message in errors:
        print(f"ERROR: {message}")
    print(f"Result: {'FAIL' if errors else 'PASS'} ({len(errors)} errors, {len(warnings)} warnings)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
