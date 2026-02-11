#!/usr/bin/env python3
"""
Minimal local fetcher for Dáil debate XMLs.

Creates:
  ~/2026/2026-02-05_mul@.xml

No API calls.
No Hugging Face.
No git.
"""

import datetime as dt
import time
from pathlib import Path

import requests

BASE_URL = "https://data.oireachtas.ie/akn/ie/debateRecord/dail"
OUT_DIR = Path.home() / "2026"

START_DATE = dt.date(2026, 1, 1)
END_DATE = dt.date.today()

SLEEP_SECONDS = 0.3


def looks_like_xml(content: bytes) -> bool:
    if not content or len(content) < 100:
        return False
    head = content.lstrip()[:500].lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        return False
    return head.startswith(b"<?xml") or head.startswith(b"<")


def main():
    OUT_DIR.mkdir(exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "oireachtas-local-poc/1.0",
            "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
        }
    )

    d = START_DATE
    saved = 0
    missing = 0

    while d <= END_DATE:
        date_str = d.isoformat()
        url = f"{BASE_URL}/{date_str}/debate/mul@/main.xml"
        out_file = OUT_DIR / f"{date_str}_mul@.xml"

        try:
            r = session.get(url, timeout=30)

            if r.status_code == 404:
                missing += 1
            elif r.status_code == 200 and looks_like_xml(r.content):
                out_file.write_bytes(r.content)
                saved += 1
                print(f"✅ {out_file.name}")
            else:
                missing += 1

        except Exception as e:
            print(f"⚠️  {date_str}: {e}")

        d += dt.timedelta(days=1)
        time.sleep(SLEEP_SECONDS)

    print("\nDone")
    print(f"Saved XMLs: {saved}")
    print(f"No record / skipped: {missing}")


if __name__ == "__main__":
    main()