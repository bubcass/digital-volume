from pathlib import Path
from huggingface_hub import HfApi

REPO_ID = "bubcass/oireachtas-debates"
REPO_TYPE = "dataset"

# Point directly at the dail folder
DAIL_DIR = Path("/Users/david/Developer/2026-01-20_debates_edition/data/xml/dail")

NUM_WORKERS = 3  # keep modest to reduce timeouts; increase later if stable

def main():
    if not DAIL_DIR.exists():
        raise SystemExit(f"DAIL_DIR not found: {DAIL_DIR}")

    # Preflight: prove we can see files
    files = list(DAIL_DIR.rglob("*.xml"))
    print(f"Uploading dail from: {DAIL_DIR}")
    print(f"XML files found (recursive): {len(files)}")
    if files:
        print("Example file:", files[0].relative_to(DAIL_DIR))

    api = HfApi()

    api.upload_large_folder(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        folder_path=str(DAIL_DIR),
        num_workers=NUM_WORKERS,
        print_report=True,
        print_report_every=60,
    )

    print("Done.")

if __name__ == "__main__":
    main()