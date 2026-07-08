package com.immortalmc.adapter.interaction;

import com.immortalmc.adapter.content.EntityInteractionDefinition;
import java.util.Map;
import java.util.Objects;

public final class EntityInteractionActionRouter<T> {
    private final Map<String, EntityInteractionAction<T>> actions;

    public EntityInteractionActionRouter(Map<String, EntityInteractionAction<T>> actions) {
        this.actions = Map.copyOf(Objects.requireNonNull(actions, "actions"));
    }

    public boolean route(EntityInteractionDefinition definition, T context) {
        Objects.requireNonNull(definition, "definition");
        Objects.requireNonNull(context, "context");
        EntityInteractionAction<T> action = actions.get(definition.action());
        if (action == null) {
            return false;
        }
        action.handle(definition, context);
        return true;
    }
}
