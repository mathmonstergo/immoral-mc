package com.immortalmc.adapter.content;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.bukkit.configuration.file.FileConfiguration;

final class EntityInteractionConfigMapper {
    static final String INTERACTIONS_PATH = "content.entity-interactions.entries";
    private static final String LEGACY_SPIRIT_ROOT_DETECTORS_PATH = "content.spirit-root.detectors";
    private static final String LEGACY_SPIRIT_ROOT_ACTION = "spirit-root-detect";
    private static final String UNKNOWN_ENTITY_TYPE = "UNKNOWN";
    private static final String ID_KEY = "id";
    private static final String ACTION_KEY = "action";
    private static final String WORLD_KEY = "world";
    private static final String ENTITY_UUID_KEY = "entity-uuid";
    private static final String ENTITY_TYPE_KEY = "entity-type";
    private static final String PROTECTED_KEY = "protected";

    List<EntityInteractionDefinition> load(FileConfiguration config) {
        if (config.isSet(INTERACTIONS_PATH)) {
            return loadGeneric(config.getMapList(INTERACTIONS_PATH));
        }
        return loadLegacySpiritRootDetectors(config.getMapList(LEGACY_SPIRIT_ROOT_DETECTORS_PATH));
    }

    List<Map<String, Object>> dump(List<EntityInteractionDefinition> interactions) {
        return interactions.stream()
                .map(this::toConfigEntry)
                .toList();
    }

    private List<EntityInteractionDefinition> loadGeneric(List<Map<?, ?>> entries) {
        List<EntityInteractionDefinition> interactions = new ArrayList<>();
        for (Map<?, ?> entry : entries) {
            String id = requiredString(entry, ID_KEY);
            String action = requiredString(entry, ACTION_KEY);
            EntityBinding binding = bindingFrom(entry);
            String entityType = optionalString(entry, ENTITY_TYPE_KEY, UNKNOWN_ENTITY_TYPE);
            boolean protectedEntity = optionalBoolean(entry, PROTECTED_KEY, true);
            interactions.add(new EntityInteractionDefinition(id, action, binding, entityType, protectedEntity));
        }
        return List.copyOf(interactions);
    }

    private List<EntityInteractionDefinition> loadLegacySpiritRootDetectors(List<Map<?, ?>> entries) {
        List<EntityInteractionDefinition> interactions = new ArrayList<>();
        int index = 1;
        for (Map<?, ?> entry : entries) {
            interactions.add(new EntityInteractionDefinition(
                    LEGACY_SPIRIT_ROOT_ACTION + "-" + index,
                    LEGACY_SPIRIT_ROOT_ACTION,
                    bindingFrom(entry),
                    UNKNOWN_ENTITY_TYPE,
                    true));
            index++;
        }
        return List.copyOf(interactions);
    }

    private EntityBinding bindingFrom(Map<?, ?> entry) {
        String world = requiredString(entry, WORLD_KEY);
        String entityUuid = requiredString(entry, ENTITY_UUID_KEY);
        return new EntityBinding(world, UUID.fromString(entityUuid));
    }

    private String requiredString(Map<?, ?> entry, String key) {
        Object value = entry.get(key);
        if (!(value instanceof String text) || text.isBlank()) {
            throw new IllegalArgumentException("Invalid entity interaction entry in config.yml: missing " + key);
        }
        return text;
    }

    private String optionalString(Map<?, ?> entry, String key, String fallback) {
        Object value = entry.get(key);
        if (value == null) {
            return fallback;
        }
        if (!(value instanceof String text) || text.isBlank()) {
            throw new IllegalArgumentException("Invalid entity interaction entry in config.yml: invalid " + key);
        }
        return text;
    }

    private boolean optionalBoolean(Map<?, ?> entry, String key, boolean fallback) {
        Object value = entry.get(key);
        if (value == null) {
            return fallback;
        }
        if (!(value instanceof Boolean bool)) {
            throw new IllegalArgumentException("Invalid entity interaction entry in config.yml: invalid " + key);
        }
        return bool;
    }

    private Map<String, Object> toConfigEntry(EntityInteractionDefinition interaction) {
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put(ID_KEY, interaction.id());
        entry.put(ACTION_KEY, interaction.action());
        entry.put(WORLD_KEY, interaction.binding().worldName());
        entry.put(ENTITY_UUID_KEY, interaction.binding().entityUuid().toString());
        entry.put(ENTITY_TYPE_KEY, interaction.entityType());
        entry.put(PROTECTED_KEY, interaction.protectedEntity());
        return entry;
    }
}
