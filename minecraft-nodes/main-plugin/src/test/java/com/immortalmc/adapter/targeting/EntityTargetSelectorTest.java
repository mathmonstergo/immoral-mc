package com.immortalmc.adapter.targeting;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.content.EntityBinding;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.Vector;
import org.junit.jupiter.api.Test;

class EntityTargetSelectorTest {
    @Test
    void selectsVillagerHeightEntityWhenAimingAtBodyInsteadOfBasePoint() {
        EntityBinding villager = binding("30000000-0000-0000-0000-000000000001");
        EntityTargetSelector selector = new EntityTargetSelector(8.0);
        Vector eye = new Vector(0.0, 1.62, 0.0);
        Vector bodyAim = new Vector(0.0, 1.25, 4.0).subtract(eye).normalize();
        BoundingBox villagerBox = new BoundingBox(-0.3, 0.0, 3.7, 0.3, 1.95, 4.3);

        Optional<EntityBinding> selected = selector.select(
                eye,
                bodyAim,
                List.of(new EntityTargetCandidate(villager, villagerBox)));

        assertEquals(Optional.of(villager), selected);
    }

    @Test
    void returnsEmptyWhenNoEntityBoundingBoxIntersectsViewRay() {
        EntityTargetSelector selector = new EntityTargetSelector(8.0);
        Vector eye = new Vector(0.0, 1.62, 0.0);
        Vector forward = new Vector(0.0, 0.0, 1.0);

        Optional<EntityBinding> selected = selector.select(
                eye,
                forward,
                List.of(new EntityTargetCandidate(
                        binding("30000000-0000-0000-0000-000000000002"),
                        new BoundingBox(3.0, 0.0, 3.7, 3.6, 1.95, 4.3))));

        assertTrue(selected.isEmpty());
    }

    private static EntityBinding binding(String entityUuid) {
        return new EntityBinding("world", UUID.fromString(entityUuid));
    }
}
