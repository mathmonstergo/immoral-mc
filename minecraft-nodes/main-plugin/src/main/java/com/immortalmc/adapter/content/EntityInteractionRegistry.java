package com.immortalmc.adapter.content;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.regex.Pattern;

public final class EntityInteractionRegistry {
    private final EntityInteractionRepository repository;
    private List<EntityInteractionDefinition> interactions = List.of();

    public EntityInteractionRegistry(EntityInteractionRepository repository) {
        this.repository = Objects.requireNonNull(repository, "repository");
    }

    public synchronized int reload() {
        interactions = deduplicate(repository.load());
        return interactions.size();
    }

    public synchronized EntityInteractionDefinition saveInteraction(String action, EntityInteractionEntity entity) {
        Objects.requireNonNull(action, "action");
        return saveInteraction(nextId(action), action, entity, false);
    }

    public synchronized EntityInteractionDefinition saveInteraction(
            String id,
            String action,
            EntityInteractionEntity entity) {
        return saveInteraction(id, action, entity, false);
    }

    public synchronized EntityInteractionDefinition saveInteraction(
            String id,
            String action,
            EntityInteractionEntity entity,
            boolean managedEntity) {
        return saveInteraction(id, action, entity, managedEntity, Map.of());
    }

    public synchronized EntityInteractionDefinition saveInteraction(
            String id,
            String action,
            EntityInteractionEntity entity,
            boolean managedEntity,
            Map<String, String> metadata) {
        Objects.requireNonNull(id, "id");
        Objects.requireNonNull(action, "action");
        Objects.requireNonNull(entity, "entity");
        Objects.requireNonNull(metadata, "metadata");

        Optional<EntityInteractionDefinition> existing = find(action, entity.binding());
        if (existing.isPresent()) {
            return existing.orElseThrow();
        }

        EntityInteractionDefinition definition =
                new EntityInteractionDefinition(
                        id,
                        action,
                        entity.binding(),
                        entity.entityType(),
                        true,
                        managedEntity,
                        metadata);
        List<EntityInteractionDefinition> updated = new ArrayList<>(interactions);
        updated.add(definition);
        interactions = deduplicate(updated);
        repository.save(interactions);
        return definition;
    }

    public synchronized Optional<EntityInteractionDefinition> removeInteraction(String action, EntityBinding binding) {
        Objects.requireNonNull(action, "action");
        Objects.requireNonNull(binding, "binding");

        Optional<EntityInteractionDefinition> removed = find(action, binding);
        if (removed.isEmpty()) {
            return Optional.empty();
        }

        interactions = interactions.stream()
                .filter(definition -> !(definition.action().equals(action) && definition.binding().equals(binding)))
                .toList();
        repository.save(interactions);
        return removed;
    }

    public synchronized List<EntityInteractionDefinition> list() {
        return List.copyOf(interactions);
    }

    public synchronized List<EntityInteractionDefinition> listByAction(String action) {
        Objects.requireNonNull(action, "action");
        return interactions.stream()
                .filter(definition -> definition.action().equals(action))
                .toList();
    }

    public synchronized Optional<EntityInteractionDefinition> find(EntityBinding binding) {
        Objects.requireNonNull(binding, "binding");
        return interactions.stream()
                .filter(definition -> definition.binding().equals(binding))
                .findFirst();
    }

    public synchronized Optional<EntityInteractionDefinition> find(String action, EntityBinding binding) {
        Objects.requireNonNull(action, "action");
        Objects.requireNonNull(binding, "binding");
        return interactions.stream()
                .filter(definition -> definition.action().equals(action))
                .filter(definition -> definition.binding().equals(binding))
                .findFirst();
    }

    public synchronized List<EntityInteractionDefinition> findAll(EntityBinding binding) {
        Objects.requireNonNull(binding, "binding");
        return interactions.stream()
                .filter(definition -> definition.binding().equals(binding))
                .toList();
    }

    public synchronized boolean matches(EntityBinding binding) {
        return find(binding).isPresent();
    }

    public synchronized boolean isProtected(EntityBinding binding) {
        Objects.requireNonNull(binding, "binding");
        return interactions.stream()
                .filter(definition -> definition.binding().equals(binding))
                .anyMatch(EntityInteractionDefinition::protectedEntity);
    }

    public synchronized int count() {
        return interactions.size();
    }

    public synchronized String nextId(String action) {
        Objects.requireNonNull(action, "action");
        if (action.isBlank()) {
            throw new IllegalArgumentException("action must not be blank");
        }

        Pattern generatedId = Pattern.compile(Pattern.quote(action) + "-\\d+");
        int next = interactions.stream()
                .map(EntityInteractionDefinition::id)
                .filter(id -> generatedId.matcher(id).matches())
                .map(id -> id.substring(action.length() + 1))
                .mapToInt(Integer::parseInt)
                .max()
                .orElse(0)
                + 1;
        return action + "-" + next;
    }

    private static List<EntityInteractionDefinition> deduplicate(List<EntityInteractionDefinition> definitions) {
        Objects.requireNonNull(definitions, "definitions");
        Map<String, EntityInteractionDefinition> byActionAndBinding = new LinkedHashMap<>();
        for (EntityInteractionDefinition definition : definitions) {
            byActionAndBinding.putIfAbsent(key(definition.action(), definition.binding()), definition);
        }
        return List.copyOf(byActionAndBinding.values());
    }

    private static String key(String action, EntityBinding binding) {
        return action + "\u0000" + binding.worldName() + "\u0000" + binding.entityUuid();
    }
}
