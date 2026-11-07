"""Polite HTTP: on-disk cache, TTL, rate limit, retries."""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

import requests

from src.config import HTTP_CACHE_DIR, REQUEST_DELAY_S, USER_AGENT

log = logging.getLogger(__name__)
_last_call: dict[str, float] = {}


class FetchError(RuntimeError):
    pass


def _cache_path(url: str, cache_dir: Path) -> Path:
    return cache_dir / hashlib.sha256(url.encode()).hexdigest()


def fetch_bytes(
    url: str,
    ttl_s: float | None = None,
    cache_dir: Path = HTTP_CACHE_DIR,
    delay_s: float = REQUEST_DELAY_S,
    retries: int = 3,
    timeout: float = 30,
) -> bytes:
    """GET url with a disk cache. ttl_s=None means cache forever."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(url, cache_dir)
    if path.exists() and (ttl_s is None or time.time() - path.stat().st_mtime < ttl_s):
        return path.read_bytes()

    host = url.split("/")[2]
    wait = delay_s - (time.time() - _last_call.get(host, 0))
    if wait > 0:
        time.sleep(wait)

    err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            _last_call[host] = time.time()
            if resp.status_code == 404:
                raise FetchError(f"404 {url}")
            resp.raise_for_status()
            path.write_bytes(resp.content)
            return resp.content
        except FetchError:
            raise
        except Exception as exc:  # network, 5xx, proxy refusals
            err = exc
            time.sleep(2 ** attempt)
    if path.exists():  # stale cache beats nothing
        log.warning("Using stale cache for %s (%s)", url, err)
        return path.read_bytes()
    raise FetchError(f"{url}: {err}")
