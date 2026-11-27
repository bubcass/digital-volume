#!/usr/bin/env python3
"""Build one JSON Lines record per speaker per sitting day from debate XML.

The stable join key is ``member_uri`` (the ``TLCPerson/@href`` value), rather
than the speaker's display name.  Each record also retains the speech IDs and
section headings needed to link a Constituency Insights entry back to the
Digital Volume or the official Oireachtas debate page.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path
from typing import Iterable


DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
SPACE_RE = re.compile(r"\s+")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def clean_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return SPACE_RE.sub(" ", "".join(element.itertext())).strip()


def first_child(element: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in element if local_name(child.tag) == name), None)


def first_descendant(element: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in element.iter() if local_name(child.tag) == name), None)


def unique(values: Iterable[str]) -> list[str]:
    return list(OrderedDict.fromkeys(value for value in values if value))


def document_date(root: ET.Element, path: Path) -> str:
    for element in root.iter():
        if local_name(element.tag) == "FRBRWork":
            date = first_descendant(element, "FRBRdate")
            if date is not None and DATE_RE.fullmatch(date.get("date", "")):
                return date.get("date", "")

    match = DATE_RE.search(path.name) or DATE_RE.search(str(path))
    return match.group(0) if match else ""


def build_references(root: ET.Element) -> dict[str, dict[str, str]]:
    references: dict[str, dict[str, str]] = {}
    for element in root.iter():
        ref_id = element.get("eId", "")
        if not ref_id or not local_name(element.tag).startswith("TLC"):
            continue
        references[ref_id] = {
            "name": element.get("showAs", "").strip(),
            "uri": element.get("href", "").strip(),
            "type": local_name(element.tag),
        }
    return references


def direct_heading(section: ET.Element) -> str:
    return clean_text(first_child(section, "heading"))


def iter_speeches(
    element: ET.Element, headings: tuple[str, ...] = ()
) -> Iterable[tuple[ET.Element, tuple[str, ...]]]:
    name = local_name(element.tag)
    current_headings = headings
    if name == "debateSection":
        heading = direct_heading(element)
        if heading:
            current_headings = headings + (heading,)

    if name == "speech":
        yield element, current_headings
        return

    for child in element:
        yield from iter_speeches(child, current_headings)


def recorded_time(speech: ET.Element) -> str:
    from_element = first_child(speech, "from")
    time_element = first_descendant(from_element, "recordedTime") if from_element is not None else None
    return time_element.get("time", "") if time_element is not None else ""


def document_chamber(root: ET.Element, path: Path) -> str:
    for element in root.iter():
        if local_name(element.tag) not in {"FRBRthis", "FRBRuri"}:
            continue
        match = re.search(r"/debateRecord/(dail|seanad)/", element.get("value", ""))
        if match:
            return match.group(1)

    lowered = [part.lower() for part in path.parts]
    if "seanad" in lowered:
        return "seanad"
    if "dail" in lowered or "dáil" in lowered:
        return "dail"
    return "dail"


def source_xml_uri(root: ET.Element) -> str:
    for element in root.iter():
        if local_name(element.tag) != "FRBRManifestation":
            continue
        frbr_this = first_descendant(element, "FRBRthis")
        if frbr_this is not None:
            return frbr_this.get("value", "")
    return ""


def extract_file(path: Path, site_base: str) -> list[dict]:
    root = ET.parse(path).getroot()
    date = document_date(root, path)
    if not date:
        raise ValueError("could not determine sitting date")

    chamber = document_chamber(root, path)
    xml_uri = source_xml_uri(root)
    references = build_references(root)
    speakers: OrderedDict[str, dict] = OrderedDict()

    for speech, heading_path in iter_speeches(root):
        speaker_ref = speech.get("by", "").lstrip("#")
        if not speaker_ref:
            continue

        reference = references.get(speaker_ref, {})
        member_uri = reference.get("uri", "")
        key = member_uri or speaker_ref
        speech_id = speech.get("eId", "")
        from_label = clean_text(first_child(speech, "from"))
        time = recorded_time(speech)
        role_ref = speech.get("as", "").lstrip("#")
        role = references.get(role_ref, {}).get("name", "") if role_ref else ""

        record = speakers.setdefault(
            key,
            {
                "date": date,
                "chamber": chamber,
                "member_uri": member_uri,
                "member_id": member_uri.rstrip("/").rsplit("/", 1)[-1] if member_uri else "",
                "speaker_ref": speaker_ref,
                "name": reference.get("name", "") or from_label,
                "reference_type": reference.get("type", ""),
                "speech_count": 0,
                "first_spoken_at": "",
                "last_spoken_at": "",
                "roles": [],
                "from_labels": [],
                "topics": [],
                "speech_ids": [],
                "speech_urls": [],
                "debate_url": f"https://www.oireachtas.ie/en/debates/debate/{chamber}/{date}/",
                "digital_volume_url": f"{site_base}?date={date}&mode=edition" if site_base else "",
                "source_xml_uri": xml_uri,
            },
        )

        record["speech_count"] += 1
        if time:
            if not record["first_spoken_at"] or time < record["first_spoken_at"]:
                record["first_spoken_at"] = time
            if not record["last_spoken_at"] or time > record["last_spoken_at"]:
                record["last_spoken_at"] = time
        if role:
            record["roles"].append(role)
        if from_label:
            record["from_labels"].append(from_label)
        record["topics"].extend(heading_path)
        if speech_id:
            record["speech_ids"].append(speech_id)
            match = re.fullmatch(r"spk_(\d+)", speech_id)
            if match:
                record["speech_urls"].append(
                    f"https://www.oireachtas.ie/en/debates/debate/{chamber}/{date}/speech/{match.group(1)}/"
                )

    for record in speakers.values():
        for field in ("roles", "from_labels", "topics", "speech_ids", "speech_urls"):
            record[field] = unique(record[field])

    return list(speakers.values())


def xml_files(inputs: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for path in inputs:
        if path.is_file() and path.suffix.lower() == ".xml":
            files.add(path)
        elif path.is_dir():
            files.update(path.rglob("*.xml"))
        else:
            print(f"warning: skipping missing input: {path}", file=sys.stderr)
    return sorted(files)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        default=[Path("data/xml/dail")],
        help="XML files or directories (default: data/xml/dail)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/daily-speakers.jsonl"),
        help="JSON Lines output path (default: data/daily-speakers.jsonl)",
    )
    parser.add_argument(
        "--site-base",
        default="",
        help="optional Digital Volume base URL used to build per-day links",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    files = xml_files(args.inputs)
    if not files:
        print("error: no XML files found", file=sys.stderr)
        return 2

    records: list[dict] = []
    failed = 0
    for path in files:
        try:
            records.extend(extract_file(path, args.site_base.rstrip("/")))
        except (ET.ParseError, OSError, ValueError) as error:
            failed += 1
            print(f"warning: {path}: {error}", file=sys.stderr)

    records.sort(key=lambda row: (row["date"], row["name"], row["member_uri"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(
        f"Wrote {len(records)} speaker-day records from {len(files) - failed} XML files "
        f"to {args.output}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
