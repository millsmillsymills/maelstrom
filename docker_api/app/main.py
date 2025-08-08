#!/usr/bin/env python3
"""
Docker Management API using FastAPI and Docker SDK.
Provides secure endpoints for querying, managing, and troubleshooting containers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from .routes import containers, system, exec as exec_route, ws, images
from .utils.auth import api_key_auth
from .utils.errors import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title="Docker Management API",
        description="Secure REST API for managing Docker containers",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        dependencies=[api_key_auth],
    )

    # CORS (locked down by default; adjust as needed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(containers.router, prefix="/containers", tags=["containers"])
    app.include_router(system.router, prefix="/system", tags=["system"])
    app.include_router(images.router, tags=["images"])  # exposes /images
    app.include_router(exec_route.router, prefix="/containers", tags=["exec"])
    app.include_router(ws.router, tags=["ws"])

    # Health check
    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    # Exceptions
    register_exception_handlers(app)

    logger.info("Docker Management API initialized")
    return app


app = create_app()
