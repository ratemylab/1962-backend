from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.exceptions.base import ApplicationException
from app.exceptions.handlers import (
    application_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.config import settings
from app.middleware.auth import AuthMiddleware


app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.add_middleware(AuthMiddleware)

app.include_router(api_router)

app.add_exception_handler(ApplicationException, application_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
