"""Validator script to scan and report all unverified records and TODO_VERIFY placeholders."""

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def check_obj(obj, path, issues):
    if isinstance(obj, dict):
        if obj.get("verified") is False:
            issues.append(f"[UNVERIFIED RECORD] {path} (id: {obj.get('id', 'N/A')})")
        for k, v in obj.items():
            check_obj(v, f"{path}.{k}", issues)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            check_obj(item, f"{path}[{idx}]", issues)
    elif isinstance(obj, str):
        if "TODO_VERIFY" in obj:
            issues.append(f"[TODO_VERIFY VALUE] {path}: '{obj}'")


def main():
    print("=" * 60)
    print("Scheme Saathi – Data Verification & Quality Check")
    print("=" * 60)

    if not DATA_DIR.exists():
        print(f"Data directory {DATA_DIR} does not exist.")
        return

    issues = []
    total_files = 0

    for root, _, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith(".json"):
                total_files += 1
                filepath = Path(root) / f
                rel_path = filepath.relative_to(BASE_DIR)
                try:
                    with open(filepath, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                    check_obj(data, str(rel_path), issues)
                except Exception as e:
                    issues.append(f"[ERROR READING JSON] {rel_path}: {e}")

    print(f"\nScanned {total_files} JSON data files.")
    if issues:
        print(f"\nFound {len(issues)} items requiring verification by the owner:\n")
        for issue in issues:
            print(f"  • {issue}")
        print("\nPlease update these fields and set 'verified': true once confirmed.")
    else:
        print("\n✅ All data files are verified! No TODO_VERIFY placeholders found.")

    return len(issues)


if __name__ == "__main__":
    exit(1 if main() > 0 else 0)
