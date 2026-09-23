import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import NovaBanqError

logger = logging.getLogger(__name__)


def _error_payload(
    code: str,
    message: str,
    details: dict | None = None,
) -> dict:
    """Build the standard error envelope used across the API."""
    return {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


async def novabanq_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle all application-raised NovaBanqError subclasses."""
    assert isinstance(exc, NovaBanqError)
    logger.warning(
        "Application error on %s %s: [%s] %s",
        request.method,
        request.url.path,
        exc.code,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.code, exc.message, exc.details),
    )


async def validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle Pydantic/FastAPI request validation failures."""
    assert isinstance(exc, RequestValidationError)
    details = {"fields": exc.errors()}
    logger.warning(
        "Validation error on %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_payload(
            "VALIDATION_ERROR",
            "The request payload failed validation.",
            details,
        ),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all handler. Logs the full traceback, returns a safe response."""
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload(
            "INTERNAL_ERROR",
            "An internal error occurred.",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI application."""
    app.add_exception_handler(NovaBanqError, novabanq_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)