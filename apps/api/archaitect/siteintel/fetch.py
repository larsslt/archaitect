"""HTTP layer: one pooled client, hard time budgets, one retry, cache with stale-if-error. No source logic here."""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Callable, Protocol
import httpx
from .cache import TtlCache, make_key

USER_AGENT = 'ArchAItect-prototype/0.7 (research prototype; see project repository)'


@dataclass
class FetchResult:
    body: bytes | None
    ms: int
    cached: bool = False
    stale: bool = False
    error: str | None = None


Accept = Callable[[bytes], bool]


class Fetcher(Protocol):
    def post_xml(self, source_id: str, url: str, body: str, ttl: float, timeout: float, accept: Accept | None = None) -> FetchResult: ...
    def get(self, source_id: str, url: str, params: dict[str, str], ttl: float, timeout: float, accept: Accept | None = None) -> FetchResult: ...


class HttpFetcher:
    def __init__(self, cache: TtlCache | None = None, client: httpx.Client | None = None):
        self.cache = cache or TtlCache(None)
        self.client = client or httpx.Client(
            headers={'User-Agent': USER_AGENT, 'Accept-Encoding': 'gzip'},
            limits=httpx.Limits(max_connections=24, max_keepalive_connections=12), follow_redirects=True)

    def _run(self, key: str, ttl: float, timeout: float, call, accept: Accept | None = None) -> FetchResult:
        t0 = time.perf_counter()
        hit = self.cache.get(key, ttl)
        if hit is not None and (accept is None or accept(hit)):
            return FetchResult(hit, int((time.perf_counter() - t0) * 1000), cached=True)
        err = 'unbekannt'
        tmo = httpx.Timeout(timeout, connect=min(4.0, timeout))
        for attempt in range(2):
            try:
                r = call(tmo)
                if r.status_code == 200 and r.content and (accept is None or accept(r.content)):
                    self.cache.put(key, r.content)  # only complete, plausible answers are cached
                    return FetchResult(r.content, int((time.perf_counter() - t0) * 1000))
                err = f'HTTP {r.status_code}' if r.status_code != 200 else 'unbrauchbare Antwort'
                if r.status_code == 200 or (r.status_code < 500 and r.status_code != 429):
                    break  # deterministic refusals (4xx, exception reports) will not heal on retry
            except httpx.HTTPError as exc:
                err = type(exc).__name__
            if attempt == 0:
                time.sleep(0.25)
        stale = self.cache.get(key, ttl, allow_stale=True)
        if stale is not None and accept is not None and not accept(stale):
            stale = None
        ms = int((time.perf_counter() - t0) * 1000)
        if stale is not None:
            return FetchResult(stale, ms, cached=True, stale=True, error=err)
        return FetchResult(None, ms, error=err)

    def post_xml(self, source_id: str, url: str, body: str, ttl: float, timeout: float, accept: Accept | None = None) -> FetchResult:
        key = make_key(source_id, url, body)
        return self._run(key, ttl, timeout, lambda tmo: self.client.post(url, content=body.encode('utf-8'), headers={'Content-Type': 'application/xml'}, timeout=tmo), accept)

    def get(self, source_id: str, url: str, params: dict[str, str], ttl: float, timeout: float, accept: Accept | None = None) -> FetchResult:
        key = make_key(source_id, url, *(f'{k}={params[k]}' for k in sorted(params)))
        return self._run(key, ttl, timeout, lambda tmo: self.client.get(url, params=params or None, timeout=tmo), accept)
