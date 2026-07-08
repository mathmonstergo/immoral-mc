package com.immortalmc.adapter.interaction;

import com.immortalmc.adapter.content.EntityInteractionDefinition;

@FunctionalInterface
public interface EntityInteractionAction<T> {
    void handle(EntityInteractionDefinition definition, T context);
}
