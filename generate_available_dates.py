from huggingface_hub import HfApi
import re
import json
from pathlib import Path

# Your dataset
DATASET = "bubcass/oireachtas-debates"
BRANCH = "main"

# Where to write the index
OUTPUT = Path("data/available-dates.json")

def main():
    api = HfApi()

    print(f"Listing files in dataset {DATASET}...")

    files = api.list_repo_files(DATASET, repo_type="dataset", revision=BRANCH)

    date_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})_mul@\.xml$")

    dates = set()

    for f in files:
        m = date_pattern.search(f)
        if m:
            dates.add(m.group(1))

    sorted_dates = sorted(dates)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(json.dumps(sorted_dates, indent=2))

    print(f"Found {len(sorted_dates)} available debate dates.")
    print(f"Wrote: {OUTPUT}")

if __name__ == "__main__":
    main()