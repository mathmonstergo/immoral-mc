package com.immortalmc.adapter.item;

import com.immortalmc.adapter.client.ItemInstanceSnapshot;
import java.util.Optional;

public final class PhysicalItemSnapshots {
    private PhysicalItemSnapshots() {}

    public static PhysicalItemIdentity identity(ItemInstanceSnapshot snapshot) {
        if (snapshot.isTechniqueManual()) {
            return PhysicalItemIdentity.techniqueManual(
                    snapshot.itemInstanceId(),
                    snapshot.itemCode(),
                    snapshot.techniqueId(),
                    snapshot.definitionVersion());
        }
        return new PhysicalItemIdentity(
                snapshot.itemInstanceId(),
                snapshot.itemCode(),
                Optional.empty(),
                Optional.empty());
    }

    public static PhysicalItemPresentation presentation(ItemInstanceSnapshot snapshot) {
        if (snapshot.isTechniqueManual()) {
            String displayName = switch (snapshot.techniqueId()) {
                case "GF_YinqiShu_01" -> "引气术秘籍";
                default -> "功法秘籍 · " + snapshot.techniqueId();
            };
            return new PhysicalItemPresentation(
                    org.bukkit.Material.ENCHANTED_BOOK,
                    displayName,
                    java.util.List.of(
                            "功法：" + snapshot.techniqueId(),
                            "右键研读后从第 0 层开始修炼",
                            "实例：" + snapshot.itemInstanceId()));
        }
        return new PhysicalItemPresentation(
                org.bukkit.Material.PAPER,
                snapshot.itemCode(),
                java.util.List.of("实例：" + snapshot.itemInstanceId()));
    }
}
