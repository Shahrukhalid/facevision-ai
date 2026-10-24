"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..config import Config
from ..state import AppState
from . import routes_core, routes_identity, routes_jobs, routes_live

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "media-src 'self' blob:; connect-src 'self' ws: wss:; font-src 'self' data:; object-src 'none'; "
       "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")


class SecurityMiddleware:
    """Host-header allow-list (blocks DNS rebinding), same-origin check for state-changing requests and
    WebSockets (blocks cross-site requests), and security headers."""

    def __init__(self, app, config: Config):
        self.app = app
        hosts = {"localhost", "127.0.0.1", "[::1]", "::1", "testserver"}
        hosts.update(h.lower() for h in config.allowed_hosts)
        if config.host not in {"0.0.0.0", "::"}:
            hosts.add(config.host.lower())
        self.hosts = hosts

    def _host_ok(self, host: str) -> bool:
        h = host.lower()
        if h.startswith("["):
            h = h.split("]")[0] + "]"
        else:
            h = h.rsplit(":", 1)[0] if h.count(":") == 1 else h
        return h in self.hosts

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        host = headers.get("host", "")
        origin = headers.get("origin")
        reject = None
        if not self._host_ok(host):
            reject = "Host not allowed. Add it to FV_ALLOWED_HOSTS if you exposed FaceVision AI on purpose."
        elif origin and (scope["type"] == "websocket" or scope.get("method") in UNSAFE):
            o = urlparse(origin)
            if not o.netloc or not self._host_ok(o.netloc) or o.netloc.lower() != host.lower():
                reject = "Cross-origin request blocked."
        if reject:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            resp = JSONResponse({"detail": reject}, status_code=403)
            return await resp(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                extra = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
                         (b"referrer-policy", b"no-referrer"), (b"content-security-policy", CSP.encode()),
                         (b"permissions-policy", b"camera=(self), microphone=(), geolocation=()")]
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        return await self.app(scope, receive, send_wrapper)


def create_app(state: AppState | None = None, config: Config | None = None) -> FastAPI:
    config = config or (state.config if state else Config.from_env())
    state = state or AppState(config)
    app = FastAPI(title="FaceVision AI", version=__version__, docs_url="/api/docs", redoc_url="/api/redoc",
                  openapi_url="/api/openapi.json",
                  description="Local REST API for consent-based face detection, analysis, recognition and "
                              "anonymisation. Biometric endpoints require a signed-in session or an API key "
                              "(X-API-Key header).")
    app.state.fv = state
    app.include_router(routes_core.router)
    app.include_router(routes_identity.router)
    app.include_router(routes_jobs.router)
    app.include_router(routes_live.router)

    if (WEB_DIR / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/") or path.startswith("ws/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            f = (WEB_DIR / path).resolve()
            if path and WEB_DIR in f.parents and f.is_file():
                return FileResponse(f)
            return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})
    else:
        @app.get("/", include_in_schema=False)
        def no_ui():
            return JSONResponse({"detail": "The web app is not built. Run scripts/setup to build it, or use the API at /api/docs."})

    app.add_middleware(SecurityMiddleware, config=config)
    return app
