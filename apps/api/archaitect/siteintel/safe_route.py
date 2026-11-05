"""Route class that turns unexpected exceptions into a JSON 500 that still passes through the CORS middleware.

Without it Starlette's ServerErrorMiddleware answers outside CORS, the browser drops the response and fetch() reports only a
network error ("Load failed" in Safari, "Failed to fetch" in Chrome). With it the client sees the real cause and the request id is logged.
"""
from __future__ import annotations
import logging
import uuid
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.routing import APIRoute

log = logging.getLogger('archaitect.siteintel')


class SafeRoute(APIRoute):
    def get_route_handler(self):
        inner = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await inner(request)
            except (HTTPException, StarletteHTTPException, RequestValidationError):
                raise
            except Exception as exc:  # noqa: BLE001 - last line of defence, logged with traceback
                rid = uuid.uuid4().hex[:8]
                log.exception('unhandled error %s on %s %s', rid, request.method, request.url.path)
                raise HTTPException(500, f'Interner Fehler ({type(exc).__name__}, Ref. {rid}). Details stehen im Backend-Log.') from exc
        return handler
