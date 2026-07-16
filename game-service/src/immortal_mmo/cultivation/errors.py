from immortal_mmo.core.errors import ConflictError, NotFoundError, RuleViolationError


class CultivationSeclusionRuleError(RuleViolationError):
    code = "cultivation.seclusion_rule_violation"
    message = "Seclusion requirements are not satisfied."


class CultivationSeclusionConflictError(ConflictError):
    code = "cultivation.seclusion_conflict"
    message = "Seclusion conflicts with current cultivation state."


class CultivationSeclusionNotFoundError(NotFoundError):
    code = "cultivation.seclusion_not_found"
    message = "Seclusion session was not found."
