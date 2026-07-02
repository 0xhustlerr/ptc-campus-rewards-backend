"""FastAPI application entrypoint — PTC Campus Rewards API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.middleware import RequestLoggingMiddleware
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.rate_limit import limiter
from app.schemas.common import HealthResponse
from app.utils.health import check_database, check_redis

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging("DEBUG" if settings.debug else "INFO")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Closed-loop campus rewards wallet for PTC barber college students. "
        "Students earn and redeem **PTC Credits** — not a public crypto token. "
        "No blockchain, external transfers, cash-out, or student-to-student transfers."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def root_health() -> HealthResponse:
    """Liveness — the process is up and serving requests."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@app.get("/health/ready", tags=["health"])
def readiness() -> JSONResponse:
    """Readiness — reports 503 when a critical dependency is unavailable so a
    load balancer stops routing traffic to a broken instance."""
    database = check_database()
    redis = check_redis()
    ok = database == "ok" and redis == "ok"
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "ready" if ok else "not_ready",
            "database": database,
            "redis": redis,
        },
    )
