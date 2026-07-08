from fastapi import Request
from fastapi.responses import JSONResponse

from immortal_mmo.core.errors import DomainError


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            }
        },
    )

