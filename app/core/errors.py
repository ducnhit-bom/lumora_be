from typing import Any, Optional


def api_error(code: str, message: str, details: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
