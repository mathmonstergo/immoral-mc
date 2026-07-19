from immortal_mmo.core.errors import ConflictError, NotFoundError, RuleViolationError


class StorageAreaNotFoundError(NotFoundError):
    code = "storage.area_not_found"
    message = "Regional storage is not configured for this area."


class StoragePageNotFoundError(NotFoundError):
    code = "storage.page_not_found"
    message = "Regional storage page does not exist."


class StorageRevisionConflictError(ConflictError):
    code = "storage.revision_conflict"
    message = "Regional storage changed; refresh the page before retrying."


class StorageOperationConflictError(ConflictError):
    code = "storage.operation_conflict"
    message = "Storage operation ID was reused for a different request."


class StorageMoveRuleError(RuleViolationError):
    code = "storage.move_rule_violation"
    message = "Regional storage move is not valid for the current item state."
