import json

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
