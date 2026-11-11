"""Unit and fault-injection tests for Phase 12 ModelRouter and graceful degradation."""

import time
from pathlib import Path
from utils.model_router import ModelRouter, ModelEntry, RoleUnavailable, TRACES_FILE
from agent.fallback_messages import get_fallback_message


def test_fallback_order_second_succeeds(tmp_path):
    """Verify router tries first entry, fails, and succeeds with second entry."""
    router = ModelRouter()
    # Mock two entries for test role
    router.roles["test_llm"] = [
        ModelEntry(role="test_llm", provider="failing_prov", key_env="FAKE_KEY_1"),
        ModelEntry(role="test_llm", provider="working_prov", key_env="FAKE_KEY_2"),
    ]

    called = []

    def mock_fn(entry):
        called.append(entry.provider)
        if entry.provider == "failing_prov":
            raise Exception("500 Internal Server Error")
        return "success_from_second"

    res = router.call("test_llm", mock_fn)
    assert res == "success_from_second"
    assert called == ["failing_prov", "working_prov"]
    assert router.degraded is True


def test_expired_key_marked_and_skipped():
    """Verify 401 error marks entry as expired and skips it on next call."""
    router = ModelRouter()
    entry1 = ModelEntry(role="test_role", provider="expired_prov", key_env="K1")
    entry2 = ModelEntry(role="test_role", provider="healthy_prov", key_env="K2")
    router.roles["test_role"] = [entry1, entry2]

    def mock_fn(entry):
        if entry.provider == "expired_prov":
            raise Exception("401 Unauthorized: Invalid API key")
        return "healthy_result"

    res1 = router.call("test_role", mock_fn)
    assert res1 == "healthy_result"
    assert entry1.status == "expired"
    assert entry1.is_available() is False

    # Second call should not even attempt expired_prov
    attempted = []
    res2 = router.call("test_role", lambda e: attempted.append(e.provider) or "ok")
    assert res2 == "ok"
    assert attempted == ["healthy_prov"]


def test_cooldown_on_429():
    """Verify 429 quota error sets 60s cooldown."""
    router = ModelRouter()
    entry = ModelEntry(role="test_429", provider="rate_limited", key_env="K")
    backup = ModelEntry(role="test_429", provider="backup", key_env="K")
    router.roles["test_429"] = [entry, backup]

    def mock_fn(e):
        if e.provider == "rate_limited":
            raise Exception("429 Too Many Requests: Quota exceeded")
        return "backup_ok"

    res = router.call("test_429", mock_fn)
    assert res == "backup_ok"
    assert entry.status == "cooldown"
    assert entry.cooldown_until > time.time()
    assert entry.is_available() is False


def test_all_entries_exhausted_raises_role_unavailable():
    """Verify RoleUnavailable exception is raised when every candidate fails."""
    router = ModelRouter()
    router.roles["dead_role"] = [
        ModelEntry(role="dead_role", provider="p1", key_env="K"),
        ModelEntry(role="dead_role", provider="p2", key_env="K"),
    ]

    try:
        router.call("dead_role", lambda e: (_ for _ in ()).throw(Exception("dead")))
        assert False, "Should have raised RoleUnavailable"
    except RoleUnavailable as exc:
        assert exc.role == "dead_role"


def test_tracing_spans_logged():
    """Verify trace spans are appended to traces/traces.jsonl."""
    router = ModelRouter()
    router.roles["trace_role"] = [ModelEntry(role="trace_role", provider="traced_p", key_env="K")]
    router.call("trace_role", lambda e: "ok")

    assert TRACES_FILE.exists()
    content = TRACES_FILE.read_text(encoding="utf-8")
    assert "trace_role" in content
    assert "traced_p" in content


def test_graceful_degradation_messages():
    """Verify pre-written fallback messages return correct language."""
    hi_msg = get_fallback_message("main_llm_down", "hi")
    en_msg = get_fallback_message("main_llm_down", "en")
    assert "तकनीकी समस्या" in hi_msg
    assert "having trouble right now" in en_msg
