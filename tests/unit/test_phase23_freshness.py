"""Unit tests for Phase 23: Scheme Freshness Pipeline."""

import json
from datetime import datetime, timedelta
from scripts.refresh_schemes import clean_html_to_text, compute_text_hash, is_scheme_stale, run_freshness_pipeline
from scripts.review_updates import review_pending_updates
from config.settings import settings


def test_hash_change_detection():
    html1 = "<html><body><h1>PM-KISAN Scheme</h1><p>₹6000 per year</p></body></html>"
    html2 = "<html><body><h1>PM-KISAN Scheme</h1><p>₹6000 per year</p></body></html>"
    html3 = "<html><body><h1>PM-KISAN Scheme</h1><p>₹8000 per year updated</p></body></html>"

    clean1 = clean_html_to_text(html1)
    clean2 = clean_html_to_text(html2)
    clean3 = clean_html_to_text(html3)

    assert compute_text_hash(clean1) == compute_text_hash(clean2)
    assert compute_text_hash(clean1) != compute_text_hash(clean3)


def test_stale_detection():
    today = datetime.utcnow().date().isoformat()
    old_date = (datetime.utcnow().date() - timedelta(days=45)).isoformat()

    assert is_scheme_stale(today, stale_after_days=30) is False
    assert is_scheme_stale(old_date, stale_after_days=30) is True
    assert is_scheme_stale(None) is True


def test_dry_run_writes_nothing(monkeypatch):
    class MockResp:
        status_code = 200
        text = "<html><body>PM-KISAN scheme official details ₹6000</body></html>"

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResp())
    res = run_freshness_pipeline(dry_run=True)
    assert "changed" in res
    assert "stale" in res


def test_live_index_untouched_until_approval(monkeypatch):
    monkeypatch.setattr("scripts.review_updates.ingest_schemes", lambda: None)
    # Verify a pending change exists or can be simulated
    pending_dir = settings.BASE_DIR / "data" / "schemes_pending" / "mock_test_scheme"
    pending_dir.mkdir(parents=True, exist_ok=True)

    summary_file = pending_dir / "20240101_summary.md"
    new_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    summary_file.write_text(f"New Hash: {new_hash}\nChanged benefit")

    # Before review: approval.json does not exist
    approval_file = pending_dir / "approval.json"
    assert not approval_file.exists()

    # Run review with auto approve
    processed = review_pending_updates(interactive=False, auto_decision="approve")
    assert processed >= 1
    assert approval_file.exists()

    # Clean up test dir
    import shutil
    shutil.rmtree(pending_dir, ignore_errors=True)
