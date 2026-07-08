import logging
import time
import uuid
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app.api.router import api_router
from backend.app.application.audit.service import get_current_request_id, set_current_request_id
from backend.app.application.scheduler.jobs import (
    check_unconfirmed_escalamiento,
    process_notification_queue,
    process_overdue_confirmations,
    send_pre_service_reminders,
)
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

_VALIDATION_TRANSLATIONS: dict[str, str] = {
    "missing": "Este campo es obligatorio.",
    "string_type": "Debe ser un texto.",
    "integer_type": "Debe ser un número entero.",
    "number_type": "Debe ser un número.",
    "bool_type": "Debe ser verdadero o falso.",
    "list_type": "Debe ser una lista.",
    "string_too_short": "Debe tener al menos {min_length} caracteres.",
    "string_too_long": "Debe tener como máximo {max_length} caracteres.",
    "value_error.email": "El formato del email no es válido.",
    "value_error.number.not_gt": "Debe ser mayor que {limit_value}.",
    "value_error.number.not_ge": "Debe ser mayor o igual a {limit_value}.",
    "value_error.number.not_lt": "Debe ser menor que {limit_value}.",
    "value_error.number.not_le": "Debe ser menor o igual a {limit_value}.",
    "greater_than": "Debe ser mayor que {gt}.",
    "less_than": "Debe ser menor que {lt}.",
    "ensure_ascii": "No debe contener caracteres especiales.",
}


def _translate_validation_error(error: dict) -> str:
    error_type: str = error.get("type", "")
    loc: list = error.get("loc", [])
    field = str(loc[-1]) if loc else ""

    template = _VALIDATION_TRANSLATIONS.get(error_type)
    if template is None:
        return error.get("msg", "Error de validación.")

    ctx: dict = error.get("ctx", {})
    try:
        message = template.format(**ctx)
    except KeyError:
        message = template

    if field:
        return f"{field}: {message}"
    return message


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [_translate_validation_error(e) for e in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled request error", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor."},
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects security headers into every HTTP response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class UnhandledExceptionMiddleware(BaseHTTPMiddleware):
    """Converts unexpected errors to JSON before outer response middleware runs."""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            return await unhandled_exception_handler(request, exc)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensures every request has an X-Request-ID for audit correlation."""

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_current_request_id(req_id)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "request_id": get_current_request_id(),
            },
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        process_notification_queue,
        IntervalTrigger(seconds=30),
        id="process_notifications",
        name="Process notification queue",
        max_instances=1,
    )
    scheduler.add_job(
        send_pre_service_reminders,
        IntervalTrigger(minutes=5),
        id="send_reminders",
        name="Send pre-service reminders",
    )
    scheduler.add_job(
        check_unconfirmed_escalamiento,
        IntervalTrigger(minutes=15),
        id="check_escalamiento",
        name="Check unconfirmed escalamiento",
    )
    scheduler.add_job(
        process_overdue_confirmations,
        IntervalTrigger(minutes=10),
        id="process_overdue",
        name="Process overdue confirmations",
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("APScheduler started with 4 notification jobs")
    yield
    scheduler.shutdown(wait=False)
    logger.info("APScheduler shut down")


def create_app() -> FastAPI:
    is_production = settings.app_env == "production"
    is_staging = settings.app_env == "staging"

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    app.add_middleware(UnhandledExceptionMiddleware)
    if is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["https://general-medical-services.vercel.app"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    elif is_staging:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.frontend_origin],
            allow_origin_regex=r"^https://.*-hrafael2011s-projects\.vercel\.app$",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
