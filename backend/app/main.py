import uuid
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.api.router import api_router
from backend.app.application.calendars.auto_generation_runner import calendar_auto_generation_loop
from backend.app.application.audit.service import set_current_request_id
from backend.app.core.config import settings


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensures every request has an X-Request-ID for audit correlation."""

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_current_request_id(req_id)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.calendar_auto_generation_runner_enabled:
        app.state.calendar_auto_generation_task = asyncio.create_task(
            calendar_auto_generation_loop()
        )
    yield
    task = getattr(app.state, "calendar_auto_generation_task", None)
    if task is not None:
        task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin, "http://localhost:5174"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
