import asyncio
import json

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.main import handle_http_error


def test_http_error_with_incomplete_detail_uses_safe_defaults() -> None:
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "state": {"request_id": "test-request"},
        }
    )

    response = asyncio.run(
        handle_http_error(
            request,
            StarletteHTTPException(
                status_code=400,
                detail={"message": "invalid request", "retryable": "no"},
            ),
        )
    )

    assert response.status_code == 400
    assert json.loads(response.body) == {
        "error": {
            "code": "HTTP_ERROR",
            "message": "invalid request",
            "request_id": "test-request",
            "retryable": False,
        }
    }
