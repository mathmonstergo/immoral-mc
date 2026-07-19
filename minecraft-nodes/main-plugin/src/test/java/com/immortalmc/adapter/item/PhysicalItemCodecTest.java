package com.immortalmc.adapter.item;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.UUID;
import org.bukkit.NamespacedKey;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;
import org.junit.jupiter.api.Test;

class PhysicalItemCodecTest {
    private static final NamespacedKey FORMAT = new NamespacedKey("immortalmc", "item_format_version");
    private static final NamespacedKey INSTANCE = new NamespacedKey("immortalmc", "item_instance_id");
    private static final NamespacedKey ITEM_CODE = new NamespacedKey("immortalmc", "item_code");
    private static final NamespacedKey TECHNIQUE = new NamespacedKey("immortalmc", "technique_id");
    private static final NamespacedKey TECHNIQUE_VERSION = new NamespacedKey("immortalmc", "technique_version");
    private static final UUID INSTANCE_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");

    @Test
    void writesAndReadsStableTechniqueManualMetadata() {
        PersistentDataContainer data = mock(PersistentDataContainer.class);
        ItemMeta meta = mock(ItemMeta.class);
        when(meta.getPersistentDataContainer()).thenReturn(data);
        PhysicalItemCodec codec = codec();
        PhysicalItemIdentity identity = PhysicalItemIdentity.techniqueManual(
                INSTANCE_ID, "manual_yinqi", "GF_YinqiShu_01", 3);

        codec.write(meta, identity);

        verify(data).set(FORMAT, PersistentDataType.INTEGER, 1);
        verify(data).set(INSTANCE, PersistentDataType.STRING, INSTANCE_ID.toString());
        verify(data).set(ITEM_CODE, PersistentDataType.STRING, "manual_yinqi");
        verify(data).set(TECHNIQUE, PersistentDataType.STRING, "GF_YinqiShu_01");
        verify(data).set(TECHNIQUE_VERSION, PersistentDataType.INTEGER, 3);

        when(data.get(FORMAT, PersistentDataType.INTEGER)).thenReturn(1);
        when(data.get(INSTANCE, PersistentDataType.STRING)).thenReturn(INSTANCE_ID.toString());
        when(data.get(ITEM_CODE, PersistentDataType.STRING)).thenReturn("manual_yinqi");
        when(data.get(TECHNIQUE, PersistentDataType.STRING)).thenReturn("GF_YinqiShu_01");
        when(data.get(TECHNIQUE_VERSION, PersistentDataType.INTEGER)).thenReturn(3);

        assertEquals(identity, codec.read(meta).orElseThrow());
    }

    @Test
    void rejectsUnknownVersionsAndPartialIdentity() {
        PersistentDataContainer data = mock(PersistentDataContainer.class);
        ItemMeta meta = mock(ItemMeta.class);
        when(meta.getPersistentDataContainer()).thenReturn(data);
        when(data.get(FORMAT, PersistentDataType.INTEGER)).thenReturn(2);

        assertThrows(IllegalArgumentException.class, () -> codec().read(meta));

        when(data.get(FORMAT, PersistentDataType.INTEGER)).thenReturn(1);
        assertThrows(IllegalArgumentException.class, () -> codec().read(meta));
    }

    private static PhysicalItemCodec codec() {
        return new PhysicalItemCodec(FORMAT, INSTANCE, ITEM_CODE, TECHNIQUE, TECHNIQUE_VERSION);
    }
}
