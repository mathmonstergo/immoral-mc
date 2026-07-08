package com.immortalmc.adapter.dialogue;

import java.util.Map;

@FunctionalInterface
public interface NpcDialogueRepository {
    Map<String, NpcDialogueDefinition> loadAll();
}
