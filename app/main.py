import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.journeys import router as journeys_router
from app.api.reflections import router as reflections_router
from app.api.reviews import router as reviews_router
from app.api.sessions import router as sessions_router
from app.api.settings import router as settings_router
from app.core.config import get_settings
from app.core.errors import api_error

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("lumora.api")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(journeys_router)
app.include_router(reflections_router)
app.include_router(reviews_router)
app.include_router(settings_router)
app.include_router(sessions_router)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning("http_error path=%s status=%s", request.url.path, exc.status_code)
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("validation_error path=%s errors=%s", request.url.path, len(exc.errors()))
    errors = [
        {
            "loc": error.get("loc", []),
            "msg": error.get("msg", "Invalid value."),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=api_error("validation_error", "Request validation failed.", {"errors": errors}),
    )


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Lumora API is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
