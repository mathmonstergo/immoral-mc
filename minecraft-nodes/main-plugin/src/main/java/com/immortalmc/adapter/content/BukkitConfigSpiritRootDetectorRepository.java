package com.immortalmc.adapter.content;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

public final class BukkitConfigSpiritRootDetectorRepository implements SpiritRootDetectorRepository {
    private static final String DETECTORS_PATH = "content.spirit-root.detectors";
    private static final String WORLD_KEY = "world";
    private static final String ENTITY_UUID_KEY = "entity-uuid";

    private final JavaPlugin plugin;

    public BukkitConfigSpiritRootDetectorRepository(JavaPlugin plugin) {
        this.plugin = Objects.requireNonNull(plugin, "plugin");
    }

    @Override
    public List<EntityBinding> load() {
        plugin.reloadConfig();
        List<EntityBinding> bindings = new ArrayList<>();
        for (Map<?, ?> entry : plugin.getConfig().getMapList(DETECTORS_PATH)) {
            Object world = entry.get(WORLD_KEY);
            Object entityUuid = entry.get(ENTITY_UUID_KEY);
            if (!(world instanceof String worldName) || !(entityUuid instanceof String entityUuidText)) {
                throw new IllegalArgumentException("Invalid spirit-root detector entry in config.yml");
            }
            bindings.add(new EntityBinding(worldName, UUID.fromString(entityUuidText)));
        }
        return List.copyOf(bindings);
    }

    @Override
    public void save(List<EntityBinding> bindings) {
        Objects.requireNonNull(bindings, "bindings");
        List<Map<String, Object>> entries = bindings.stream()
                .map(this::toConfigEntry)
                .toList();
        FileConfiguration config = plugin.getConfig();
        config.set(DETECTORS_PATH, entries);
        plugin.saveConfig();
    }

    private Map<String, Object> toConfigEntry(EntityBinding binding) {
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put(WORLD_KEY, binding.worldName());
        entry.put(ENTITY_UUID_KEY, binding.entityUuid().toString());
        return entry;
    }
}
