from typing import Any


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.headers = headers or {}


def not_found(message: str = "资源不存在") -> ApiError:
    return ApiError(404, "not_found", message)


def unauthenticated() -> ApiError:
    return ApiError(401, "unauthenticated", "请先登录")


def forbidden(code: str, message: str) -> ApiError:
    return ApiError(403, code, message)
