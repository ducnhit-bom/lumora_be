from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.journeys import router as journeys_router
from app.api.sessions import router as sessions_router
from app.core.config import get_settings
from app.core.errors import api_error

settings = get_settings()

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
app.include_router(sessions_router)


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
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
