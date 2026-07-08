package com.immortalmc.adapter.interaction;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class EntityInteractionActionRouterTest {
    @Test
    void routesRegisteredActionWithDefinitionAndContext() {
        List<String> handled = new ArrayList<>();
        EntityInteractionActionRouter<String> router = new EntityInteractionActionRouter<>(Map.of(
                "npc-dialogue",
                (definition, context) -> handled.add(definition.id() + ":" + context)));

        boolean routed = router.route(interaction("dialogue-1", "npc-dialogue"), "player-context");

        assertTrue(routed);
        assertEquals(List.of("dialogue-1:player-context"), handled);
    }

    @Test
    void returnsFalseForUnknownAction() {
        EntityInteractionActionRouter<String> router = new EntityInteractionActionRouter<>(Map.of());

        assertFalse(router.route(interaction("dialogue-1", "npc-dialogue"), "player-context"));
    }

    private static EntityInteractionDefinition interaction(String id, String action) {
        return new EntityInteractionDefinition(
                id,
                action,
                new EntityBinding("world", UUID.fromString("30000000-0000-0000-0000-000000000001")),
                "VILLAGER",
                true);
    }
}
