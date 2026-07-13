package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ImmortalCommandSourceTest {
    private static final UUID PLAYER_UUID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID CITIZENS_UUID = UUID.fromString("40000000-0000-0000-0000-000000000001");

    @Test
    void consoleHasNoCitizensNpcIdentity() {
        assertEquals(Optional.empty(), ImmortalCommandSource.console().lookedAtCitizensNpcUuid());
    }

    @Test
    void playerSourceCarriesPersistentCitizensNpcIdentity() {
        EntityInteractionEntity target = new EntityInteractionEntity(
                new EntityBinding("world", UUID.fromString("30000000-0000-0000-0000-000000000001")),
                "PLAYER");

        ImmortalCommandSource source = ImmortalCommandSource.player(PLAYER_UUID, target, CITIZENS_UUID);

        assertEquals(Optional.of(CITIZENS_UUID), source.lookedAtCitizensNpcUuid());
    }
}
