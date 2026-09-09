"""FastAPI 入口。

Java 对照：SpringBootApplication + 全局 CORS。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings
from app.interfaces.http.routes import request_validation_exception_handler, router
from app.shared.logging_utils import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.3.0")
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
