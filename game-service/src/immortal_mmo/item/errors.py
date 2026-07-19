from immortal_mmo.core.errors import ConflictError, NotFoundError, RuleViolationError


class ItemInsufficientQuantityError(ConflictError):
    code = "item.insufficient_quantity"
    message = "Required item quantity is insufficient."


class ItemInstanceNotFoundError(NotFoundError):
    code = "item.instance_not_found"
    message = "Physical item instance was not found for the current life."


class ItemDeliveryConflictError(RuleViolationError):
    code = "item.delivery_conflict"
    message = "Physical item delivery confirmation is not valid."
