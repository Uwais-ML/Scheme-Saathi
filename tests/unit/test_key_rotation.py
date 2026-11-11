"""Unit tests for the key rotation helper."""

from utils.key_rotation import execute_with_key_rotation


def test_rotation_first_key_succeeds():
    """Verify first key works without touching subsequent keys."""
    keys = ["key1", "key2", "key3"]
    called_keys = []

    def mock_call(key: str):
        called_keys.append(key)
        return {"query": "test", "results": [1, 2, 3]}

    res = execute_with_key_rotation(keys, mock_call)
    assert res["ok"] is True
    assert res["data"] == {"query": "test", "results": [1, 2, 3]}
    assert called_keys == ["key1"]


def test_rotation_fails_over_to_second_key():
    """Verify failure on key1 falls over to key2."""
    keys = ["key1", "key2", "key3"]
    called_keys = []

    def mock_call(key: str):
        called_keys.append(key)
        if key == "key1":
            raise Exception("429 Too Many Requests: Rate limit exceeded")
        return "success_from_key2"

    res = execute_with_key_rotation(keys, mock_call)
    assert res["ok"] is True
    assert res["data"] == "success_from_key2"
    assert called_keys == ["key1", "key2"]


def test_rotation_all_keys_fail_returns_error():
    """Verify graceful failure when all keys fail."""
    keys = ["key1", "key2"]
    called_keys = []

    def mock_call(key: str):
        called_keys.append(key)
        raise Exception("401 Unauthorized: Invalid API key")

    res = execute_with_key_rotation(keys, mock_call, fallback_error="search_unavailable")
    assert res["ok"] is False
    assert res["error"] == "search_unavailable"
    assert called_keys == ["key1", "key2"]


def test_rotation_with_empty_keys():
    """Verify empty key list returns error without crashing."""
    res = execute_with_key_rotation([], lambda k: "never_called")
    assert res["ok"] is False
    assert res["error"] == "search_unavailable"


def test_rotation_with_dict_error_return():
    """Verify failover when function returns ok=False with retryable error."""
    keys = ["k1", "k2"]

    def mock_call(key: str):
        if key == "k1":
            return {"ok": False, "error": "quota exceeded"}
        return {"ok": True, "items": ["a"]}

    res = execute_with_key_rotation(keys, mock_call)
    assert res["ok"] is True
    assert res["data"] == {"ok": True, "items": ["a"]}
