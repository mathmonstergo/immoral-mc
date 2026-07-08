package com.immortalmc.adapter.client;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;

public record LifeSnapshot(UUID lifeId, UUID accountId, int generationNo, String status, JsonNode spiritRoot) {}
