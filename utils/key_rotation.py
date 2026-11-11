"""Helper for rotating API keys on auth, rate limit, quota, or timeout errors."""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Keywords indicating a retryable key or quota failure
RETRYABLE_ERROR_KEYWORDS = (
    "401",
    "403",
    "429",
    "quota",
    "rate limit",
    "unauthorized",
    "invalid api key",
    "timed out",
    "timeout",
)


def is_retryable_error(exc_or_msg: Exception | str) -> bool:
    """Check if an exception or message indicates key or quota failure."""
    msg = str(exc_or_msg).lower()
    return any(keyword in msg for keyword in RETRYABLE_ERROR_KEYWORDS)


def execute_with_key_rotation(
    keys: list[str],
    call_fn: Callable[[str], Any],
    fallback_error: str = "search_unavailable",
) -> dict[str, Any]:
    """Execute a function across a list of keys, falling back to next key on failure.

    Args:
        keys: List of API keys to try in order.
        call_fn: Function accepting a single key and returning a result.
        fallback_error: Error code to return if all keys fail or no keys provided.

    Returns:
        dict: {"ok": True, "data": ...} on success,
              {"ok": False, "error": fallback_error} on complete failure.
    """
    if not keys:
        logger.warning("No API keys provided for rotation.")
        return {"ok": False, "error": fallback_error}

    for idx, key in enumerate(keys):
        try:
            result = call_fn(key)

            # If function returns a structured dict indicating failure
            if isinstance(result, dict) and not result.get("ok", True):
                err = str(result.get("error", ""))
                if is_retryable_error(err):
                    logger.warning(
                        "Key %d failed with retryable error: %s. Trying next key.",
                        idx + 1,
                        err,
                    )
                    continue

            return {"ok": True, "data": result}

        except Exception as exc:
            if is_retryable_error(exc):
                logger.warning(
                    "Key %d raised retryable error: %s. Trying next key.",
                    idx + 1,
                    exc,
                )
                continue
            else:
                logger.warning(
                    "Key %d failed with unexpected error: %s. Trying next key.",
                    idx + 1,
                    exc,
                )
                continue

    # All keys exhausted
    logger.error("All %d API keys failed.", len(keys))
    return {"ok": False, "error": fallback_error}
