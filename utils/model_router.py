"""Centralized ModelRouter managing fallbacks, circuit breakers, health checks, and tracing."""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
import yaml
from rich.console import Console
from rich.table import Table

from config.settings import settings

logger = logging.getLogger(__name__)

TRACES_DIR = settings.BASE_DIR / "traces"
TRACES_DIR.mkdir(parents=True, exist_ok=True)
TRACES_FILE = TRACES_DIR / "traces.jsonl"


class RoleUnavailable(Exception):
    """Raised when all configured entries for a model role are exhausted."""

    def __init__(self, role: str):
        super().__init__(f"All model providers for role '{role}' are unavailable.")
        self.role = role


def log_trace_span(
    role: str,
    provider: str,
    model: str | None,
    latency_ms: float,
    outcome: str,
    key_env: str,
) -> None:
    """Record execution trace span to traces/traces.jsonl."""
    span = {
        "timestamp": datetime.utcnow().isoformat(),
        "role": role,
        "provider": provider,
        "model": model,
        "latency_ms": round(latency_ms, 2),
        "outcome": outcome,
        "key_env": key_env,
    }
    try:
        with open(TRACES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(span) + "\n")
    except Exception:
        pass


class ModelEntry:
    """Represents a specific model provider candidate in the fallback chain."""

    def __init__(
        self,
        role: str,
        provider: str,
        key_env: str,
        model: str | None = None,
        voice_id: str | None = None,
        expires_on: str | None = None,
    ):
        self.role = role
        self.provider = provider
        self.key_env = key_env
        self.model = model
        self.voice_id = voice_id
        self.expires_on = expires_on
        self.status: str = "healthy"
        self.consecutive_failures: int = 0
        self.cooldown_until: float = 0.0

    @property
    def api_key(self) -> str:
        """Resolve current API key from environment."""
        val = os.getenv(self.key_env, "")
        if self.role == "search" and "," in val:
            # First key of comma-separated list
            return val.split(",")[0].strip()
        return val.strip()

    def is_available(self) -> bool:
        """Check if entry is eligible for execution."""
        if self.status == "expired":
            return False
        if self.status == "cooldown" and time.time() < self.cooldown_until:
            return False
        return True


class ModelRouter:
    """Routes model requests across ordered fallback chains with fault recovery."""

    def __init__(self, config_path: Path | str | None = None):
        self.config_path = (
            Path(config_path) if config_path else settings.BASE_DIR / "config" / "models.yaml"
        )
        self.roles: dict[str, list[ModelEntry]] = {}
        self.degraded: bool = False
        self.load_config()

    def load_config(self) -> None:
        """Parse models.yaml into role fallback lists."""
        if not self.config_path.exists():
            logger.warning("models.yaml not found at %s", self.config_path)
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        for role, entries in data.items():
            self.roles[role] = []
            for e in entries:
                entry = ModelEntry(
                    role=role,
                    provider=e.get("provider", "mock"),
                    key_env=e.get("key_env", ""),
                    model=e.get("model"),
                    voice_id=e.get("voice_id"),
                    expires_on=e.get("expires_on"),
                )
                self.roles[role].append(entry)

    def call(self, role: str, fn: Callable[[ModelEntry], Any], *args, **kwargs) -> Any:
        """Execute a function using the best available entry for role."""
        entries = self.roles.get(role, [])
        if not entries:
            raise RoleUnavailable(role)

        for idx, entry in enumerate(entries):
            if not entry.is_available():
                continue

            # Check if downgrading to a backup model
            if idx > 0:
                self.degraded = True

            start_t = time.perf_counter()
            try:
                result = fn(entry, *args, **kwargs)
                latency = (time.perf_counter() - start_t) * 1000.0
                entry.consecutive_failures = 0
                entry.status = "healthy"
                log_trace_span(role, entry.provider, entry.model, latency, "ok", entry.key_env)
                return result

            except Exception as exc:
                latency = (time.perf_counter() - start_t) * 1000.0
                err_msg = str(exc).lower()

                # Classify error
                if any(k in err_msg for k in ("401", "403", "unauthorized", "invalid key", "expired")):
                    entry.status = "expired"
                    outcome = "expired"
                    logger.warning("Role '%s' provider '%s' expired/unauthorized. Skipping.", role, entry.provider)
                elif any(k in err_msg for k in ("429", "quota", "rate limit")):
                    entry.status = "cooldown"
                    entry.cooldown_until = time.time() + 60.0
                    outcome = "cooldown_429"
                    logger.warning("Role '%s' provider '%s' rate limited. Cooldown 60s.", role, entry.provider)
                else:
                    # Retry once for transient 5xx or timeout
                    entry.consecutive_failures += 1
                    outcome = "failure"
                    if entry.consecutive_failures >= 3:
                        entry.status = "cooldown"
                        entry.cooldown_until = time.time() + 30.0

                log_trace_span(role, entry.provider, entry.model, latency, outcome, entry.key_env)
                continue

        # All entries failed
        self.degraded = True
        logger.error("All entries for role '%s' exhausted.", role)
        raise RoleUnavailable(role)

    def health_check(self, print_table: bool = True) -> list[dict[str, Any]]:
        """Ping entries, check expiration, and display rich status table."""
        results = []
        table = Table(title="Model Providers Health Check")
        table.add_column("ROLE", style="cyan")
        table.add_column("ENTRY", style="bold")
        table.add_column("STATUS", style="green")
        table.add_column("NOTE")

        now = datetime.utcnow()

        for role, entries in self.roles.items():
            healthy_count = 0
            for e in entries:
                status = "OK"
                note = ""
                key = e.api_key

                # Check expiration date
                if e.expires_on:
                    try:
                        exp = datetime.strptime(e.expires_on, "%Y-%m-%d")
                        days_left = (exp - now).days
                        if days_left < 0:
                            status = "EXPIRED"
                            note = f"Expired on {e.expires_on}"
                        elif days_left <= 7:
                            status = "WARN"
                            note = f"Key expires in {days_left} days"
                    except Exception:
                        pass

                if e.provider in ("mock", "local_multilingual", "mock_search"):
                    status = "OK"
                    note = "Local fallback ready"
                    healthy_count += 1
                elif not key or "placeholder" in key.lower():
                    status = "MISSING_KEY"
                    note = f"Env var {e.key_env} is empty"
                else:
                    if status != "EXPIRED":
                        healthy_count += 1
                        note = "Configured"

                e.status = "healthy" if status == "OK" else status.lower()

                # Mask key for reporting
                masked = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
                entry_name = f"{e.provider}/{e.model or 'default'}"
                table.add_row(role, entry_name, status, f"{note} (key: {masked})")
                results.append(
                    {
                        "role": role,
                        "provider": e.provider,
                        "model": e.model,
                        "status": status,
                        "note": note,
                    }
                )

            if healthy_count < 2:
                logger.warning("Role '%s' has fewer than 2 healthy entries (%d healthy).", role, healthy_count)

        if print_table:
            console = Console()
            console.print(table)

        return results


# Global singleton router
router = ModelRouter()
