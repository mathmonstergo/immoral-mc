class DomainError(Exception):
    status_code = 400
    code = "domain.error"
    message = "Domain error."
    retryable = False

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message is not None:
            self.message = message


class NotFoundError(DomainError):
    status_code = 404
    code = "domain.not_found"
    message = "Resource was not found."
