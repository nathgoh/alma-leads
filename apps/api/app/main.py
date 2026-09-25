import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import RequestResponseEndpoint

from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import enforce_same_origin
from app.leads.router import internal_router, public_router
from app.storage.s3 import S3Storage, get_storage

log = logging.getLogger(__name__)

# Multipart framing overhead allowed on top of the resume itself.
_UPLOAD_OVERHEAD = 64 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    storage = get_storage()
    if settings.s3_create_bucket and isinstance(storage, S3Storage):
        try:
            await run_in_threadpool(storage.ensure_bucket)
        except Exception:
            log.exception("Could not ensure bucket %s exists", settings.s3_bucket)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Alma Leads API",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )
    # No CORSMiddleware on purpose: browsers reach the API only via the same-origin /api rewrite.

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    @app.middleware("http")
    async def reject_oversized_uploads(request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Reject before the multipart body is parsed/buffered at all.
        length = request.headers.get("content-length")
        if (
            request.method == "POST"
            and length is not None
            and length.isdigit()
            and int(length) > settings.max_resume_bytes + _UPLOAD_OVERHEAD
        ):
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)

    # Registered last so it runs first: cross-origin writes are rejected before anything else.
    app.middleware("http")(enforce_same_origin)

    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(public_router)
    v1.include_router(auth_router)
    v1.include_router(internal_router)
    app.include_router(v1)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
