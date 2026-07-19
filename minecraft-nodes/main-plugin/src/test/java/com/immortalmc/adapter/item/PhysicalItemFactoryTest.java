package com.immortalmc.adapter.item;

import static org.junit.jupiter.api.Assertions.assertSame;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.List;
import java.util.UUID;
import org.bukkit.Material;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.junit.jupiter.api.Test;

class PhysicalItemFactoryTest {
    @Test
    void createsNonStackingPhysicalProjectionAndDelegatesIdentityEncoding() {
        PhysicalItemCodec codec = mock(PhysicalItemCodec.class);
        ItemStack stack = mock(ItemStack.class);
        ItemMeta meta = mock(ItemMeta.class);
        when(stack.getItemMeta()).thenReturn(meta);
        PhysicalItemFactory factory = new PhysicalItemFactory(codec, material -> {
            assertSame(Material.ENCHANTED_BOOK, material);
            return stack;
        });
        PhysicalItemIdentity identity = PhysicalItemIdentity.techniqueManual(
                UUID.fromString("11111111-1111-4111-8111-111111111111"),
                "manual_yinqi",
                "GF_YinqiShu_01",
                1);

        assertSame(stack, factory.create(
                identity,
                new PhysicalItemPresentation(
                        Material.ENCHANTED_BOOK,
                        "引气术秘籍",
                        List.of("右键研习"))));

        verify(meta).setMaxStackSize(1);
        verify(codec).write(meta, identity);
        verify(stack).setItemMeta(meta);
        verify(stack).setAmount(1);
    }
}
