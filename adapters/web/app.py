from __future__ import annotations

import os

import asyncpg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from adapters.web import routes
from adapters.web.api import (
    auth,
    cascades,
    costs,
    chat,
    gates,
    knowledge,
    ledger,
    metrics,
    trace,
    scc,
    sessions,
    ws,
)

DEFAULT_DATABASE_URL = "postgresql://eclusa:eclusa@localhost:5432/eclusa"

__all__ = ["create_app", "app"]


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_app() -> FastAPI:
    app = FastAPI(title="Eclusa Web API")
    app.state.pool = None
    app.state._owns_pool = False

    @app.on_event("startup")
    async def _startup() -> None:
        if app.state.pool is None:
            app.state.pool = await asyncpg.create_pool(
                _database_url(),
                min_size=1,
                max_size=10,
            )
            app.state._owns_pool = True

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        pool = getattr(app.state, "pool", None)
        if getattr(app.state, "_owns_pool", False) and pool is not None:
            await pool.close()
        app.state.pool = None
        app.state._owns_pool = False

    @app.get("/healthz")
    async def healthz():
        """DB pool liveness check. AUTH-04."""
        pool = app.state.pool
        if pool is None:
            return JSONResponse({"status": "unavailable", "detail": "pool not initialised"}, status_code=503)
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"status": "ok", "pool_size": pool.get_size(), "pool_free": pool.get_idle_size()}
        except Exception as exc:
            return JSONResponse({"status": "unavailable", "detail": str(exc)}, status_code=503)

    @app.get("/readyz")
    async def readyz():
        """Readiness check. AUTH-04."""
        pool = app.state.pool
        if pool is None:
            return JSONResponse({"status": "not_ready", "detail": "pool not initialised"}, status_code=503)
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"status": "ready"}
        except Exception as exc:
            return JSONResponse({"status": "not_ready", "detail": str(exc)}, status_code=503)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:80",
            "http://localhost",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    app.include_router(routes.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(cascades.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(scc.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(costs.router, prefix="/api")
    app.include_router(ledger.router, prefix="/api")
    app.include_router(knowledge.router, prefix="/api")
    app.include_router(metrics.router, prefix="/api")
    app.include_router(trace.router, prefix="/api")
    app.include_router(gates.router, prefix="/api")
    app.include_router(ws.router)
    return app


app = create_app()
