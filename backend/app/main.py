import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app.api.router import api_router
from backend.app.application.audit.service import set_current_request_id
from backend.app.core.config import settings


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


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensures every request has an X-Request-ID for audit correlation."""

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_current_request_id(req_id)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


def create_app() -> FastAPI:
    is_production = settings.app_env == "production"

    app = FastAPI(
        title=settings.app_name,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    if is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["https://general-medical-services.vercel.app"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.frontend_origin, "http://localhost:5174", "http://localhost:8999"],
            allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|192\.168\.\d+\.\d+):(5173|8999)$",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
