"""Manual scheme freshness check pipeline.

Fetches live official source pages, detects text hash changes, saves pending diffs,
and generates freshness reports without touching the live corpus.
"""

import argparse
import hashlib
from datetime import datetime
from pathlib import Path
import re
import requests
from config.settings import settings

PENDING_DIR = Path(settings.BASE_DIR) / "data" / "schemes_pending"
REPORT_DIR = Path(settings.BASE_DIR) / "reports" / "freshness"


def clean_html_to_text(html_content: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", " ", html_content)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def compute_text_hash(text: str) -> str:
    """Compute sha256 hash of cleaned text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_scheme_stale(last_verified_str: str | None, stale_after_days: int | None = None) -> bool:
    """Check if last verification date is older than configured threshold."""
    if not last_verified_str:
        return True
    threshold = stale_after_days or settings.STALE_AFTER_DAYS
    try:
        last_dt = datetime.fromisoformat(last_verified_str)
        delta_days = (datetime.utcnow() - last_dt).days
        return delta_days >= threshold
    except Exception:
        return True


def run_freshness_pipeline(scheme_id: str | None = None, dry_run: bool = False) -> dict:
    """Execute the freshness scan over schemes."""
    data_dir = settings.DATA_DIR
    files = [data_dir / f"{scheme_id}.json"] if scheme_id else list(data_dir.glob("*.json"))

    results = {
        "changed": [],
        "unchanged": [],
        "failed": [],
        "stale": [],
        "past_deadline": [],
    }

    today_str = datetime.utcnow().strftime("%Y%m%d")
    now_iso = datetime.utcnow().date().isoformat()

    print(f"Starting Scheme Freshness Check (Dry-run: {dry_run})...")

    for fpath in files:
        if not fpath.exists():
            continue
        import json
        with open(fpath, "r", encoding="utf-8") as fp:
            scheme = json.load(fp)

        sid = scheme.get("scheme_id")
        source_url = scheme.get("source_url")
        stored_hash = scheme.get("content_hash", "")
        last_verified = scheme.get("last_verified")

        # Check deadline
        deadline = scheme.get("status", {}).get("deadline")
        if deadline and deadline < now_iso:
            results["past_deadline"].append(sid)

        # Check stale
        if is_scheme_stale(last_verified):
            results["stale"].append(sid)

        if not source_url:
            continue

        # Fetch URL
        try:
            resp = requests.get(source_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                results["failed"].append({"scheme_id": sid, "url": source_url, "error": f"HTTP {resp.status_code}"})
                continue
            cleaned = clean_html_to_text(resp.text)
            new_hash = compute_text_hash(cleaned)

            if not stored_hash or new_hash != stored_hash:
                results["changed"].append(sid)
                print(f"  [CHANGED / UNINITIALIZED] {sid} (Hash: {new_hash[:8]} vs {stored_hash[:8] or 'none'})")

                if not dry_run:
                    scheme_pending = PENDING_DIR / sid
                    scheme_pending.mkdir(parents=True, exist_ok=True)
                    # Save fetched markdown
                    out_md = scheme_pending / f"{today_str}.md"
                    with open(out_md, "w", encoding="utf-8") as out_fp:
                        out_fp.write(f"# Fetched live content for {sid} ({today_str})\nSource: {source_url}\n\n{cleaned[:5000]}")

                    # Summary
                    summary_md = scheme_pending / f"{today_str}_summary.md"
                    summary_text = (
                        f"## Update Summary for {sid}\n"
                        f"- Fetch Date: {today_str}\n"
                        f"- Source: {source_url}\n"
                        f"- Stored Hash: {stored_hash or 'None'}\n"
                        f"- New Hash: {new_hash}\n"
                        f"- Action Required: Review changes and run `python -m scripts.review_updates` to approve.\n"
                    )
                    with open(summary_md, "w", encoding="utf-8") as sum_fp:
                        sum_fp.write(summary_text)
            else:
                results["unchanged"].append(sid)
                print(f"  [UNCHANGED] {sid}")

        except Exception as e:
            results["failed"].append({"scheme_id": sid, "url": source_url, "error": str(e)})

    # Generate Report
    if not dry_run:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_file = REPORT_DIR / f"{today_str}.md"
        report_content = (
            f"# Scheme Freshness Report – {today_str}\n\n"
            f"- **Changed / Pending Review:** {len(results['changed'])} ({', '.join(results['changed']) or 'None'})\n"
            f"- **Unchanged:** {len(results['unchanged'])} ({', '.join(results['unchanged']) or 'None'})\n"
            f"- **Fetch Failed:** {len(results['failed'])}\n"
            f"- **Stale Schemes:** {len(results['stale'])} ({', '.join(results['stale']) or 'None'})\n"
            f"- **Past Deadline:** {len(results['past_deadline'])} ({', '.join(results['past_deadline']) or 'None'})\n"
        )
        with open(report_file, "w", encoding="utf-8") as rfp:
            rfp.write(report_content)
        print(f"\nFreshness report generated: {report_file}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Refresh scheme data and check for updates.")
    parser.add_argument("--scheme", help="Specific scheme_id to refresh", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Do not write pending files or reports")
    args = parser.parse_args()

    run_freshness_pipeline(scheme_id=args.scheme, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
