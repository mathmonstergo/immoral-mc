package com.immortalmc.adapter.content;

import java.util.List;

public interface EntityInteractionRepository {
    List<EntityInteractionDefinition> load();

    void save(List<EntityInteractionDefinition> interactions);
}
