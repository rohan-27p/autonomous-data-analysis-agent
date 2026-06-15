from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from autodata_agent.api.routes import router
from autodata_agent.core.errors import AppError


def create_app() -> FastAPI:
    app = FastAPI(
        title="Autonomous Data Analysis Agent Backend",
        version="0.1.0",
        description=(
            "Backend API for data ingestion, autonomous analysis, visualization specs, "
            "and history."
        ),
    )
    app.include_router(router, prefix="/api/v1")

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected backend error occurred.",
                    "details": {"reason": str(exc)},
                }
            },
        )

    return app


app = create_app()
