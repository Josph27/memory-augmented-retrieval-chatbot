"""Pre-flight connection guard for the inference server.

Before any LLM call, optionally check that the inference server is reachable
with a short timeout.  After a failed call the guard marks the server as
unavailable for a short period so that every subsequent call in the same turn
fails immediately with a clear message instead of waiting for the full
per-request timeout.
"""

from __future__ import annotations

import os
from time import monotonic
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


_CHECK_TIMEOUT = max(1.0, _env_float("CONNECTION_GUARD_CHECK_TIMEOUT", 3.0))
_CACHE_TTL = max(1.0, _env_float("CONNECTION_GUARD_CACHE_TTL", 30.0))


def _safe_urljoin(base: str, path: str) -> str:
    """Join a relative path to a base URL without stripping path segments.

    ``urllib.parse.urljoin("http://host/inference", "/health")`` returns
    ``"http://host/health"``, losing ``/inference``.  We preserve the full
    base path by ensuring the joined path is relative.
    """
    path = path.lstrip("/")
    if base.endswith("/"):
        return base + path
    # Split off the last segment if it looks like a path component rather
    # than a file — we want http://host/inference/health, not
    # http://host/health.
    parts = urlsplit(base)
    base_path = parts.path.rstrip("/") + "/"
    return urlunsplit((parts.scheme, parts.netloc, base_path + path, parts.query, parts.fragment))


def _is_server_error(status: int) -> bool:
    """Return True for 5xx status codes that indicate server unavailability."""
    return 500 <= status < 600


class InferenceServerUnreachable(RuntimeError):
    """The configured inference server cannot be reached."""

    def __init__(self, base_url: str, reason: str = "") -> None:
        self.base_url = base_url
        detail = reason or "connection failed"
        super().__init__(
            f"The inference server at {base_url} is unreachable: {detail}. "
            "Verify the server is running and OPENAI_BASE_URL is correct."
        )


class ConnectionGuard:
    """Lightweight health-check cache for the inference server.

    Every ``check()`` call does a quick HTTP round-trip (default 3 s) to the
    server's root or /health endpoint.  When the check passes the result is
    cached for *cache_ttl* seconds so repeated calls inside the same turn are
    free.  When the check fails or a downstream chat call raises a
    connection-level error, ``mark_unreachable()`` flips the guard to a
    stale-unhealthy state — subsequent ``check()`` calls will raise
    ``InferenceServerUnreachable`` immediately until the cache TTL expires.
    """

    def __init__(
        self,
        base_url: str,
        *,
        check_timeout: float | None = None,
        cache_ttl: float | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._check_timeout = max(
            1.0, check_timeout if check_timeout is not None else _CHECK_TIMEOUT
        )
        self._cache_ttl = max(1.0, cache_ttl if cache_ttl is not None else _CACHE_TTL)
        self._last_healthy: float | None = None
        self._last_unhealthy_reason: str | None = None
        self._last_unhealthy_at: float | None = None

    # ── public API ──────────────────────────────────────────────────────────

    def check(self) -> None:
        """Ensure the inference server is reachable (cached when healthy)."""
        # Healthy cache still valid?
        if self._last_healthy is not None:
            if (monotonic() - self._last_healthy) < self._cache_ttl:
                return

        # Unhealthy cache still valid?
        if self._last_unhealthy_at is not None:
            if (monotonic() - self._last_unhealthy_at) < self._cache_ttl:
                raise InferenceServerUnreachable(
                    self.base_url,
                    reason=self._last_unhealthy_reason or "previously unavailable",
                )

        # Do a quick round-trip.
        try:
            self._ping()
        except InferenceServerUnreachable:
            self.mark_unreachable(reason="health check ping failed")
            raise
        else:
            self._last_healthy = monotonic()
            self._last_unhealthy_reason = None
            self._last_unhealthy_at = None

    def mark_unreachable(self, reason: str = "") -> None:
        """Mark the server as unavailable (call after a connection failure)."""
        self._last_healthy = None
        self._last_unhealthy_reason = reason
        self._last_unhealthy_at = monotonic()

    # ── internal ────────────────────────────────────────────────────────────

    def _ping(self) -> None:
        """Do a single short-timeout HTTP round-trip to the server.

        Tries the /health endpoint first, then falls back to GET the base URL.
        Treats 5xx responses as failures — they indicate the server is running
        but cannot serve requests.
        """
        timeout = httpx.Timeout(
            self._check_timeout,
            connect=self._check_timeout,
            read=self._check_timeout,
            write=self._check_timeout,
            pool=self._check_timeout,
        )
        health_url = _safe_urljoin(self.base_url, "/health")

        # Try the /health endpoint first.
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(health_url)
                if not _is_server_error(resp.status_code):
                    return
        except Exception:
            pass  # Fall through to the base-URL probe.

        # Fallback: try the base URL.  5xx here also counts as unhealthy.
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(self.base_url)
                if _is_server_error(resp.status_code):
                    raise InferenceServerUnreachable(
                        self.base_url,
                        reason=f"server returned {resp.status_code}",
                    )
        except httpx.ConnectError as exc:
            raise InferenceServerUnreachable(
                self.base_url,
                reason=f"connect: {exc}",
            ) from exc
        except httpx.TimeoutException as exc:
            raise InferenceServerUnreachable(
                self.base_url,
                reason=f"timeout after {self._check_timeout:.0f}s",
            ) from exc
        except InferenceServerUnreachable:
            raise
        except Exception as exc:
            raise InferenceServerUnreachable(
                self.base_url,
                reason=f"{type(exc).__name__}: {exc}",
            ) from exc


def connection_guard_from_env() -> ConnectionGuard:
    """Create a guard for the configured inference server."""
    return ConnectionGuard(
        base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
    )
