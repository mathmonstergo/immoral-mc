package com.immortalmc.adapter.client;

import java.util.UUID;

public record SpiritRootDetectionResult(UUID lifeId, SpiritRootSnapshot spiritRoot, boolean alreadyDetected) {}
