package com.immortalmc.adapter.item;

import java.util.Objects;
import net.kyori.adventure.text.Component;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

public final class PhysicalItemFactory {
    private final PhysicalItemCodec codec;
    private final StackFactory stacks;

    public PhysicalItemFactory(PhysicalItemCodec codec) {
        this(codec, ItemStack::new);
    }

    PhysicalItemFactory(PhysicalItemCodec codec, StackFactory stacks) {
        this.codec = Objects.requireNonNull(codec, "codec");
        this.stacks = Objects.requireNonNull(stacks, "stacks");
    }

    public ItemStack create(PhysicalItemIdentity identity, PhysicalItemPresentation presentation) {
        Objects.requireNonNull(identity, "identity");
        Objects.requireNonNull(presentation, "presentation");
        ItemStack item = stacks.create(presentation.material());
        ItemMeta meta = Objects.requireNonNull(item.getItemMeta(), "Physical item material has no item meta");
        meta.displayName(Component.text(presentation.displayName()));
        meta.lore(presentation.lore().stream().map(Component::text).toList());
        meta.setMaxStackSize(1);
        codec.write(meta, identity);
        item.setItemMeta(meta);
        item.setAmount(1);
        return item;
    }

    @FunctionalInterface
    interface StackFactory {
        ItemStack create(org.bukkit.Material material);
    }
}
