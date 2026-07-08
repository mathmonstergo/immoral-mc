package com.immortalmc.adapter.content;

import java.util.List;
import java.util.Objects;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

public final class BukkitConfigEntityInteractionRepository implements EntityInteractionRepository {
    private final JavaPlugin plugin;
    private final EntityInteractionConfigMapper mapper = new EntityInteractionConfigMapper();

    public BukkitConfigEntityInteractionRepository(JavaPlugin plugin) {
        this.plugin = Objects.requireNonNull(plugin, "plugin");
    }

    @Override
    public List<EntityInteractionDefinition> load() {
        plugin.reloadConfig();
        return mapper.load(plugin.getConfig());
    }

    @Override
    public void save(List<EntityInteractionDefinition> interactions) {
        Objects.requireNonNull(interactions, "interactions");
        FileConfiguration config = plugin.getConfig();
        config.set(EntityInteractionConfigMapper.INTERACTIONS_PATH, mapper.dump(interactions));
        plugin.saveConfig();
    }
}
