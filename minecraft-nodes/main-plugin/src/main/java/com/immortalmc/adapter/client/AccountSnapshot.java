package com.immortalmc.adapter.client;

import java.util.UUID;

public record AccountSnapshot(UUID accountId, UUID minecraftUuid, String playerName) {}
