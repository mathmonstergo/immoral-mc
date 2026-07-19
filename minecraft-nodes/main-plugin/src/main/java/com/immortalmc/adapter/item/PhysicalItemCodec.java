package com.immortalmc.adapter.item;

import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import org.bukkit.NamespacedKey;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.Plugin;

public final class PhysicalItemCodec {
    static final int FORMAT_VERSION = 1;

    private final NamespacedKey formatVersionKey;
    private final NamespacedKey itemInstanceIdKey;
    private final NamespacedKey itemCodeKey;
    private final NamespacedKey techniqueIdKey;
    private final NamespacedKey techniqueVersionKey;

    public PhysicalItemCodec(Plugin plugin) {
        this(
                new NamespacedKey(plugin, "item_format_version"),
                new NamespacedKey(plugin, "item_instance_id"),
                new NamespacedKey(plugin, "item_code"),
                new NamespacedKey(plugin, "technique_id"),
                new NamespacedKey(plugin, "technique_version"));
    }

    PhysicalItemCodec(
            NamespacedKey formatVersionKey,
            NamespacedKey itemInstanceIdKey,
            NamespacedKey itemCodeKey,
            NamespacedKey techniqueIdKey,
            NamespacedKey techniqueVersionKey) {
        this.formatVersionKey = Objects.requireNonNull(formatVersionKey, "formatVersionKey");
        this.itemInstanceIdKey = Objects.requireNonNull(itemInstanceIdKey, "itemInstanceIdKey");
        this.itemCodeKey = Objects.requireNonNull(itemCodeKey, "itemCodeKey");
        this.techniqueIdKey = Objects.requireNonNull(techniqueIdKey, "techniqueIdKey");
        this.techniqueVersionKey = Objects.requireNonNull(techniqueVersionKey, "techniqueVersionKey");
    }

    public void write(ItemMeta meta, PhysicalItemIdentity identity) {
        Objects.requireNonNull(meta, "meta");
        Objects.requireNonNull(identity, "identity");
        PersistentDataContainer data = meta.getPersistentDataContainer();
        data.set(formatVersionKey, PersistentDataType.INTEGER, FORMAT_VERSION);
        data.set(itemInstanceIdKey, PersistentDataType.STRING, identity.itemInstanceId().toString());
        data.set(itemCodeKey, PersistentDataType.STRING, identity.itemCode());
        identity.techniqueId().ifPresentOrElse(
                value -> data.set(techniqueIdKey, PersistentDataType.STRING, value),
                () -> data.remove(techniqueIdKey));
        identity.techniqueVersion().ifPresentOrElse(
                value -> data.set(techniqueVersionKey, PersistentDataType.INTEGER, value),
                () -> data.remove(techniqueVersionKey));
    }

    public Optional<PhysicalItemIdentity> read(ItemStack item) {
        if (item == null || item.getType().isAir() || !item.hasItemMeta()) {
            return Optional.empty();
        }
        return read(item.getItemMeta());
    }

    Optional<PhysicalItemIdentity> read(ItemMeta meta) {
        PersistentDataContainer data = Objects.requireNonNull(meta, "meta").getPersistentDataContainer();
        Integer formatVersion = data.get(formatVersionKey, PersistentDataType.INTEGER);
        if (formatVersion == null) {
            return Optional.empty();
        }
        if (formatVersion != FORMAT_VERSION) {
            throw new IllegalArgumentException("Unsupported physical item format version: " + formatVersion);
        }
        String instanceValue = required(data, itemInstanceIdKey, PersistentDataType.STRING, "item_instance_id");
        String itemCode = required(data, itemCodeKey, PersistentDataType.STRING, "item_code");
        String techniqueId = data.get(techniqueIdKey, PersistentDataType.STRING);
        Integer techniqueVersion = data.get(techniqueVersionKey, PersistentDataType.INTEGER);
        UUID itemInstanceId;
        try {
            itemInstanceId = UUID.fromString(instanceValue);
        } catch (IllegalArgumentException error) {
            throw new IllegalArgumentException("Physical item has an invalid item_instance_id", error);
        }
        return Optional.of(new PhysicalItemIdentity(
                itemInstanceId,
                itemCode,
                Optional.ofNullable(techniqueId),
                Optional.ofNullable(techniqueVersion)));
    }

    private static <T> T required(
            PersistentDataContainer data,
            NamespacedKey key,
            PersistentDataType<?, T> type,
            String field) {
        T value = data.get(key, type);
        if (value == null || value instanceof String text && text.isBlank()) {
            throw new IllegalArgumentException("Physical item is missing " + field);
        }
        return value;
    }
}
