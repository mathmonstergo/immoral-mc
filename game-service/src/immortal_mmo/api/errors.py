from fastapi import Request
from starlette.responses import Response

from immortal_mmo.core.error_wire import serialize_domain_error
from immortal_mmo.core.errors import DomainError


async def domain_error_handler(request: Request, exc: DomainError) -> Response:
    del request
    return Response(
        content=serialize_domain_error(exc),
        status_code=exc.status_code,
        media_type="application/json",
    )
