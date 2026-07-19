package com.immortalmc.adapter.item;

import com.immortalmc.adapter.client.LearnTechniqueSnapshot;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

/** Game Service contract for consuming one physical technique manual. */
public interface TechniqueLearningGateway {
    CompletableFuture<LearnTechniqueSnapshot> learnTechnique(
            UUID accountId,
            UUID itemInstanceId,
            UUID operationId);
}
