from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi import HTTPException

from app.exceptions.base import ApplicationException


async def application_exception_handler(request: Request, exc: ApplicationException) -> JSONResponse:
    payload = {"message": exc.message}
    if exc.detail is not None:
        payload["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=payload)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, (str, dict, list)) else str(exc.detail)
    payload = {"message": detail}
    return JSONResponse(status_code=exc.status_code, content=payload)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    response_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    for error in errors:
        error_type = str(error.get("type", ""))
        message = str(error.get("msg", ""))
        # Contract 400: malformed JSON, missing mandatory field, or an
        # unparseable (malformed) datetime format. Everything else is a
        # semantic validation failure and stays 422.
        is_malformed_or_missing = error_type in {"json_invalid", "missing"}
        is_malformed_datetime = "YYYY-MM-DD HH:mm:ss" in message
        if is_malformed_or_missing or is_malformed_datetime:
            response_status = status.HTTP_400_BAD_REQUEST
            break

    return JSONResponse(
        status_code=response_status,
        content=jsonable_encoder({"message": "validation_error", "detail": errors}),
    )
