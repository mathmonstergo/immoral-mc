package com.immortalmc.adapter.dialogue;

import java.util.Map;
import java.util.Objects;
import java.util.Optional;

public final class NpcDialogueRegistry {
    private final NpcDialogueRepository repository;
    private Map<String, NpcDialogueDefinition> dialogues = Map.of();

    public NpcDialogueRegistry(NpcDialogueRepository repository) {
        this.repository = Objects.requireNonNull(repository, "repository");
    }

    public synchronized int reload() {
        dialogues = Map.copyOf(repository.loadAll());
        return dialogues.size();
    }

    public synchronized Optional<NpcDialogueDefinition> find(String dialogueId) {
        Objects.requireNonNull(dialogueId, "dialogueId");
        return Optional.ofNullable(dialogues.get(dialogueId));
    }

    public synchronized int count() {
        return dialogues.size();
    }
}
