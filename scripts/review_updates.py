"""Interactive review command for pending scheme updates."""

import json
from datetime import datetime
from pathlib import Path
from config.settings import settings
from rag.ingest import ingest_schemes

PENDING_DIR = Path(settings.BASE_DIR) / "data" / "schemes_pending"


def review_pending_updates(interactive: bool = True, auto_decision: str | None = None) -> int:
    """Scan data/schemes_pending/ and review each update.

    Args:
        interactive: Whether to prompt via input() in terminal.
        auto_decision: 'approve' or 'reject' for non-interactive test runs.

    Returns:
        Number of updates processed.
    """
    if not PENDING_DIR.exists():
        print("No pending updates directory found.")
        return 0

    pending_schemes = [p for p in PENDING_DIR.iterdir() if p.is_dir()]
    if not pending_schemes:
        print("No pending updates found.")
        return 0

    processed = 0
    now_iso = datetime.utcnow().date().isoformat()

    for scheme_dir in pending_schemes:
        sid = scheme_dir.name
        approval_file = scheme_dir / "approval.json"
        rejection_file = scheme_dir / "rejection.json"

        if approval_file.exists() or rejection_file.exists():
            continue

        summaries = list(scheme_dir.glob("*_summary.md"))
        if not summaries:
            continue

        summary_file = summaries[0]
        with open(summary_file, "r", encoding="utf-8") as sfp:
            summary_content = sfp.read()

        print("=" * 60)
        print(f"Pending update for: {sid}")
        print("=" * 60)
        print(summary_content)

        decision = auto_decision
        if interactive and not decision:
            try:
                ans = input("[a]pprove / [r]eject / [s]kip: ").strip().lower()
                if ans == "a":
                    decision = "approve"
                elif ans == "r":
                    decision = "reject"
                else:
                    decision = "skip"
            except EOFError:
                decision = "skip"

        if decision == "approve":
            # Extract new hash from summary
            import re
            m = re.search(r"New Hash:\s*([a-f0-9]{64})", summary_content)
            new_hash = m.group(1) if m else "verified_hash"

            # Update scheme JSON
            scheme_json_path = settings.DATA_DIR / f"{sid}.json"
            if scheme_json_path.exists():
                with open(scheme_json_path, "r", encoding="utf-8") as fp:
                    scheme_data = json.load(fp)
                scheme_data["content_hash"] = new_hash
                scheme_data["last_verified"] = now_iso
                scheme_data["verified"] = True
                with open(scheme_json_path, "w", encoding="utf-8") as fp:
                    json.dump(scheme_data, fp, ensure_ascii=False, indent=2)

            # Record approval
            with open(approval_file, "w", encoding="utf-8") as afp:
                json.dump({"approved_by": "owner", "approved_at": now_iso, "hash": new_hash}, afp)

            # Re-ingest schemes into RAG index
            print(f"Re-ingesting RAG index for approved update: {sid}...")
            ingest_schemes()
            print(f"✅ Approved and re-ingested: {sid}")
            processed += 1

        elif decision == "reject":
            with open(rejection_file, "w", encoding="utf-8") as rfp:
                json.dump({"rejected_by": "owner", "rejected_at": now_iso}, rfp)
            print(f"❌ Rejected update for: {sid}")
            processed += 1
        else:
            print(f"Skipped: {sid}")

    return processed


if __name__ == "__main__":
    review_pending_updates(interactive=True)
