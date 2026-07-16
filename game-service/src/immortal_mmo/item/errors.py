from immortal_mmo.core.errors import ConflictError


class ItemInsufficientQuantityError(ConflictError):
    code = "item.insufficient_quantity"
    message = "Required item quantity is insufficient."
