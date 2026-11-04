import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import RequestResponseEndpoint

from app.api.routes import chat, locations, nearby, pets, places, records, reminders
from app.db.session import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Pet Agent API", version="0.1.0", lifespan=lifespan)
app.include_router(pets.router, prefix="/api/v1/pets", tags=["pets"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(reminders.router, prefix="/api/v1/reminders", tags=["reminders"])
app.include_router(records.router, prefix="/api/v1/records", tags=["records"])
app.include_router(nearby.router, prefix="/api/v1/nearby", tags=["nearby"])
app.include_router(places.router, prefix="/api/v1/places", tags=["places"])
app.include_router(locations.router, prefix="/api/v1/locations", tags=["locations"])


@app.middleware("http")
async def add_request_id(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request.state.request_id,
                "retryable": retryable,
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    message = "未找到请求的资源" if exc.status_code == 404 else "请求失败"
    retryable = False
    if isinstance(exc.detail, dict):
        detail_code = exc.detail.get("code")
        detail_message = exc.detail.get("message")
        detail_retryable = exc.detail.get("retryable", False)
        if isinstance(detail_code, str) and detail_code:
            code = detail_code
        if isinstance(detail_message, str) and detail_message:
            message = detail_message
        if isinstance(detail_retryable, bool):
            retryable = detail_retryable
    return error_response(request, exc.status_code, code, message, retryable)


def custom_validation_message(exc: RequestValidationError) -> str | None:
    """透出应用层自定义校验消息（P2-1 关联校验要求 422 message 可区分）。

    仅提取 ValueError 类消息；类型、未知字段等结构化错误沿用固定文案。
    """
    for error in exc.errors():
        message = error.get("msg")
        if isinstance(message, str) and message.startswith("Value error, "):
            return message.removeprefix("Value error, ")
    return None


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    is_invalid_json = any(error["type"] == "json_invalid" for error in exc.errors())
    if is_invalid_json:
        return error_response(request, 400, "BAD_REQUEST", "请求 JSON 格式无效")
    message = custom_validation_message(exc) or "请求字段缺失或不符合要求"
    return error_response(request, 422, "VALIDATION_ERROR", message)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled request error (request_id=%s)", request.state.request_id
    )
    return error_response(
        request, 500, "INTERNAL_ERROR", "服务暂时无法处理请求", retryable=True
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
