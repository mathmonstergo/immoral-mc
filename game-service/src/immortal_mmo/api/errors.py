import json

from fastapi import Request
from starlette.responses import Response

from immortal_mmo.core.errors import DomainError


def serialize_domain_error(error: DomainError) -> bytes:
    return json.dumps(
        {
            "error": {
                "code": error.code,
                "message": error.message,
                "retryable": error.retryable,
            }
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


async def domain_error_handler(request: Request, exc: DomainError) -> Response:
    del request
    return Response(
        content=serialize_domain_error(exc),
        status_code=exc.status_code,
        media_type="application/json",
    )
