package com.immortalmc.adapter.client;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.immortalmc.adapter.item.PhysicalItemGateway;
import com.immortalmc.adapter.item.TechniqueLearningGateway;
import com.immortalmc.adapter.storage.RegionalStorageGateway;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Arrays;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;

public final class GameServiceClient
        implements PhysicalItemGateway, TechniqueLearningGateway, RegionalStorageGateway {
    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(2);

    private final URI baseUri;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;

    public GameServiceClient(URI baseUri, HttpClient httpClient) {
        this(
                baseUri,
                httpClient,
                new ObjectMapper()
                        .registerModule(new JavaTimeModule())
                        .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE));
    }

    GameServiceClient(URI baseUri, HttpClient httpClient, ObjectMapper objectMapper) {
        this.baseUri = normalizeBaseUri(Objects.requireNonNull(baseUri, "baseUri"));
        this.httpClient = Objects.requireNonNull(httpClient, "httpClient");
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper");
    }

    public CompletableFuture<HealthCheckResult> checkHealth() {
        HttpRequest request = newRequestBuilder("/health")
                .GET()
                .build();

        return httpClient
                .sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(this::parseHealthResponse);
    }

    public CompletableFuture<PlayerLoginResult> loginPlayer(UUID minecraftUuid, String playerName) {
        Objects.requireNonNull(minecraftUuid, "minecraftUuid");
        Objects.requireNonNull(playerName, "playerName");

        HttpRequest request;
        try {
            String requestBody = objectMapper.writeValueAsString(new PlayerLoginRequest(minecraftUuid, playerName));
            request = newRequestBuilder("/api/v1/players/login")
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                    .build();
        } catch (IOException error) {
            return CompletableFuture.failedFuture(
                    new GameServiceException("Game Service login request was invalid", error));
        }

        return httpClient
                .sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(this::parseLoginResponse);
    }

    public CompletableFuture<SpiritRootDetectionResult> detectSpiritRoot(UUID accountId) {
        Objects.requireNonNull(accountId, "accountId");

        HttpRequest request = newRequestBuilder("/api/v1/players/" + accountId + "/current-life/spirit-root")
                .POST(HttpRequest.BodyPublishers.noBody())
                .build();

        return httpClient
                .sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(this::parseSpiritRootDetectionResponse);
    }

    public CompletableFuture<QuestInteractionState> fetchQuestInteractionState(
            UUID accountId, List<String> providerIds) {
        Objects.requireNonNull(accountId, "accountId");
        List<String> providers = List.copyOf(providerIds);

        return sendJson(
                newRequestBuilder("/api/v1/players/" + accountId + "/current-life/quest-interaction-state"),
                "POST",
                new QuestInteractionStateRequest(providers),
                QuestInteractionState.class,
                "quest interaction state");
    }

    public CompletableFuture<QuestProviderCatalog> fetchQuestProviderCatalog() {
        HttpRequest request = newRequestBuilder("/api/v1/quest-providers")
                .GET()
                .build();

        return httpClient
                .sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(response -> parseJsonResponse(
                        response,
                        QuestProviderCatalog.class,
                        "quest provider catalog"));
    }

    public CompletableFuture<QuestMutationResult> acceptQuest(
            UUID accountId, String questId, String providerId, UUID operationId) {
        return mutateQuest(
                accountId,
                questId,
                providerId,
                operationId,
                "accept",
                new QuestProviderRequest(providerId));
    }

    public CompletableFuture<QuestMutationResult> turnInQuest(
            UUID accountId,
            String questId,
            String providerId,
            UUID operationId,
            List<UUID> inventoryItemInstanceIds) {
        return mutateQuest(
                accountId,
                questId,
                providerId,
                operationId,
                "turn-in",
                new QuestTurnInRequest(
                        providerId,
                        List.copyOf(Objects.requireNonNull(
                                inventoryItemInstanceIds,
                                "inventoryItemInstanceIds"))));
    }

    public CompletableFuture<CombatKillBatchResponse> sendCombatKills(
            List<CombatKillEventRequest> events) {
        CombatKillBatchRequest batch = new CombatKillBatchRequest(1, events);
        return sendJson(
                        newRequestBuilder("/api/v1/combat/mythicmob-kills/batch"),
                        "POST",
                        batch,
                        CombatKillBatchResponse.class,
                        "combat kill batch")
                .thenApply(response -> {
                    try {
                        return response.validateAgainst(batch.events());
                    } catch (IllegalArgumentException error) {
                        throw new CompletionException(new GameServiceException(
                                "Game Service combat kill batch response was invalid",
                                error));
                    }
                });
    }

    public CompletableFuture<CultivationSnapshot> fetchCultivation(UUID accountId) {
        Objects.requireNonNull(accountId, "accountId");
        return sendGet(
                "/api/v1/players/" + accountId + "/current-life/cultivation",
                CultivationSnapshot.class,
                "cultivation snapshot");
    }

    public CompletableFuture<List<TechniqueSnapshot>> fetchTechniques(UUID accountId) {
        Objects.requireNonNull(accountId, "accountId");
        return sendGet(
                        "/api/v1/players/" + accountId + "/current-life/cultivation/techniques",
                        TechniqueSnapshot[].class,
                        "cultivation techniques")
                .thenApply(snapshots -> List.copyOf(Arrays.asList(snapshots)));
    }

    public CompletableFuture<SeclusionSnapshot> startSeclusion(
            UUID accountId, SeclusionRequest request, UUID operationId) {
        Objects.requireNonNull(accountId, "accountId");
        return sendMutation(
                "/api/v1/players/" + accountId + "/current-life/cultivation/seclusions",
                "POST",
                request,
                operationId,
                SeclusionSnapshot.class,
                "seclusion start");
    }

    public CompletableFuture<SeclusionSnapshot> fetchSeclusion(UUID accountId, UUID sessionId) {
        Objects.requireNonNull(accountId, "accountId");
        Objects.requireNonNull(sessionId, "sessionId");
        return sendGet(
                "/api/v1/players/" + accountId + "/current-life/cultivation/seclusions/" + sessionId,
                SeclusionSnapshot.class,
                "seclusion status");
    }

    public CompletableFuture<SeclusionSnapshot> settleSeclusion(
            UUID accountId, UUID sessionId, UUID operationId) {
        Objects.requireNonNull(accountId, "accountId");
        Objects.requireNonNull(sessionId, "sessionId");
        return sendNoBodyMutation(
                "/api/v1/players/" + accountId + "/current-life/cultivation/seclusions/" + sessionId + "/settle",
                "POST",
                operationId,
                SeclusionSnapshot.class,
                "seclusion settlement");
    }

    public CompletableFuture<BreakthroughSnapshot> startBreakthrough(
            UUID accountId, BreakthroughRequest request, UUID operationId) {
        Objects.requireNonNull(accountId, "accountId");
        return sendMutation(
                "/api/v1/players/" + accountId + "/current-life/cultivation/breakthroughs",
                "POST",
                request,
                operationId,
                BreakthroughSnapshot.class,
                "breakthrough start");
    }

    public CompletableFuture<BreakthroughSnapshot> fetchBreakthrough(UUID accountId, UUID sessionId) {
        Objects.requireNonNull(accountId, "accountId");
        Objects.requireNonNull(sessionId, "sessionId");
        return sendGet(
                "/api/v1/players/" + accountId + "/current-life/cultivation/breakthroughs/" + sessionId,
                BreakthroughSnapshot.class,
                "breakthrough status");
    }

    public CompletableFuture<BreakthroughSnapshot> settleBreakthrough(
            UUID accountId, UUID sessionId, UUID operationId) {
        Objects.requireNonNull(accountId, "accountId");
        Objects.requireNonNull(sessionId, "sessionId");
        return sendNoBodyMutation(
                "/api/v1/players/" + accountId + "/current-life/cultivation/breakthroughs/" + sessionId + "/settle",
                "POST",
                operationId,
                BreakthroughSnapshot.class,
                "breakthrough settlement");
    }

    public CompletableFuture<ItemAdjustmentSnapshot> adjustItem(
            UUID accountId, ItemAdjustmentRequest request, UUID operationId) {
        Objects.requireNonNull(accountId, "accountId");
        return sendMutation(
                "/api/v1/players/" + accountId + "/current-life/items/adjustments",
                "POST",
                request,
                operationId,
                ItemAdjustmentSnapshot.class,
                "item adjustment");
    }

    @Override
    public CompletableFuture<ItemInstancesSnapshot> fetchPendingItemDeliveries(UUID accountId) {
        Objects.requireNonNull(accountId, "accountId");
        return sendGet(
                "/api/v1/players/" + accountId + "/current-life/items/pending-deliveries",
                ItemInstancesSnapshot.class,
                "pending item deliveries");
    }

    @Override
    public CompletableFuture<ItemInstancesSnapshot> fetchInventoryItems(UUID accountId) {
        Objects.requireNonNull(accountId, "accountId");
        return sendGet(
                "/api/v1/players/" + accountId + "/current-life/items/inventory",
                ItemInstancesSnapshot.class,
                "inventory item instances");
    }

    @Override
    public CompletableFuture<ItemDeliveryConfirmationSnapshot> confirmItemDelivery(
            UUID accountId, UUID itemInstanceId) {
        Objects.requireNonNull(accountId, "accountId");
        Objects.requireNonNull(itemInstanceId, "itemInstanceId");
        return sendNoBody(
                "/api/v1/players/" + accountId + "/current-life/items/" + itemInstanceId
                        + "/delivery-confirmation",
                "PUT",
                ItemDeliveryConfirmationSnapshot.class,
                "item delivery confirmation");
    }

    @Override
    public CompletableFuture<LearnTechniqueSnapshot> learnTechnique(
            UUID accountId, UUID itemInstanceId, UUID operationId) {
        Objects.requireNonNull(accountId, "accountId");
        Objects.requireNonNull(itemInstanceId, "itemInstanceId");
        return sendMutation(
                "/api/v1/players/" + accountId + "/current-life/cultivation/techniques/learn",
                "POST",
                new LearnTechniqueRequest(itemInstanceId),
                operationId,
                LearnTechniqueSnapshot.class,
                "technique learning");
    }

    @Override
    public CompletableFuture<StorageSnapshot> fetchStorage(UUID accountId, String areaId, int page) {
        Objects.requireNonNull(accountId, "accountId");
        requireText(areaId, "areaId");
        if (page < 1) {
            throw new IllegalArgumentException("page must be positive");
        }
        return sendGet(
                "/api/v1/players/" + accountId + "/current-life/storage/" + areaId + "?page=" + page,
                StorageSnapshot.class,
                "regional storage snapshot");
    }

    @Override
    public CompletableFuture<StorageMoveSnapshot> moveStorage(
            UUID accountId,
            String areaId,
            StorageMoveRequest request,
            UUID operationId) {
        Objects.requireNonNull(accountId, "accountId");
        requireText(areaId, "areaId");
        return sendMutation(
                "/api/v1/players/" + accountId + "/current-life/storage/" + areaId + "/moves",
                "POST",
                request,
                operationId,
                StorageMoveSnapshot.class,
                "regional storage move");
    }

    private <T> CompletableFuture<T> sendGet(String path, Class<T> responseType, String operationName) {
        HttpRequest request = newRequestBuilder(path).GET().build();
        return httpClient
                .sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(response -> parseJsonResponse(response, responseType, operationName));
    }

    private <T> CompletableFuture<T> sendMutation(
            String path,
            String method,
            Object body,
            UUID operationId,
            Class<T> responseType,
            String operationName) {
        Objects.requireNonNull(body, "body");
        Objects.requireNonNull(operationId, "operationId");
        return sendJson(
                newRequestBuilder(path).header("Idempotency-Key", operationId.toString()),
                method,
                body,
                responseType,
                operationName);
    }

    private <T> CompletableFuture<T> sendNoBodyMutation(
            String path,
            String method,
            UUID operationId,
            Class<T> responseType,
            String operationName) {
        Objects.requireNonNull(operationId, "operationId");
        HttpRequest request = newRequestBuilder(path)
                .header("Idempotency-Key", operationId.toString())
                .method(method, HttpRequest.BodyPublishers.noBody())
                .build();
        return httpClient
                .sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(response -> parseJsonResponse(response, responseType, operationName));
    }

    private <T> CompletableFuture<T> sendNoBody(
            String path,
            String method,
            Class<T> responseType,
            String operationName) {
        HttpRequest request = newRequestBuilder(path)
                .method(method, HttpRequest.BodyPublishers.noBody())
                .build();
        return httpClient
                .sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(response -> parseJsonResponse(response, responseType, operationName));
    }

    private CompletableFuture<QuestMutationResult> mutateQuest(
            UUID accountId,
            String questId,
            String providerId,
            UUID operationId,
            String operation,
            Object requestBody) {
        Objects.requireNonNull(accountId, "accountId");
        Objects.requireNonNull(questId, "questId");
        Objects.requireNonNull(providerId, "providerId");
        Objects.requireNonNull(operationId, "operationId");
        Objects.requireNonNull(requestBody, "requestBody");

        return sendJson(
                newRequestBuilder("/api/v1/players/" + accountId + "/current-life/quests/" + questId + "/"
                                + operation)
                        .header("Idempotency-Key", operationId.toString()),
                "PUT",
                requestBody,
                QuestMutationResult.class,
                "quest " + operation);
    }

    private <T> CompletableFuture<T> sendJson(
            HttpRequest.Builder requestBuilder,
            String method,
            Object body,
            Class<T> responseType,
            String operationName) {
        HttpRequest request;
        try {
            request = requestBuilder
                    .header("Content-Type", "application/json")
                    .method(method, HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(body)))
                    .build();
        } catch (IOException error) {
            return CompletableFuture.failedFuture(
                    new GameServiceException("Game Service " + operationName + " request was invalid", error));
        }

        return httpClient
                .sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(response -> parseJsonResponse(response, responseType, operationName));
    }

    private <T> T parseJsonResponse(HttpResponse<String> response, Class<T> responseType, String operationName) {
        if (response.statusCode() != 200) {
            throw new CompletionException(parseErrorResponse(response, operationName));
        }
        try {
            return objectMapper.readValue(response.body(), responseType);
        } catch (IOException error) {
            throw new CompletionException(
                    new GameServiceException("Game Service " + operationName + " response was invalid", error));
        }
    }

    private GameServiceException parseErrorResponse(HttpResponse<String> response, String operationName) {
        try {
            ErrorEnvelope envelope = objectMapper.readValue(response.body(), ErrorEnvelope.class);
            if (envelope.error() != null) {
                return new GameServiceException(
                        response.statusCode(),
                        envelope.error().code(),
                        envelope.error().message(),
                        envelope.error().retryable());
            }
        } catch (IOException ignored) {
            // Fall through to a stable HTTP-level error when the response is not a domain envelope.
        }
        return new GameServiceException(
                response.statusCode(),
                "http." + response.statusCode(),
                "Game Service " + operationName + " failed with HTTP " + response.statusCode(),
                response.statusCode() == 429 || response.statusCode() >= 500);
    }

    private HealthCheckResult parseHealthResponse(HttpResponse<String> response) {
        if (response.statusCode() != 200) {
            throw new CompletionException(
                    new GameServiceException("Game Service health check failed with HTTP " + response.statusCode()));
        }
        try {
            return objectMapper.readValue(response.body(), HealthCheckResult.class);
        } catch (IOException error) {
            throw new CompletionException(new GameServiceException("Game Service health response was invalid", error));
        }
    }

    private PlayerLoginResult parseLoginResponse(HttpResponse<String> response) {
        if (response.statusCode() != 200) {
            throw new CompletionException(
                    new GameServiceException("Game Service login failed with HTTP " + response.statusCode()));
        }
        try {
            return objectMapper.readValue(response.body(), PlayerLoginResult.class);
        } catch (IOException error) {
            throw new CompletionException(new GameServiceException("Game Service login response was invalid", error));
        }
    }

    private SpiritRootDetectionResult parseSpiritRootDetectionResponse(HttpResponse<String> response) {
        if (response.statusCode() != 200) {
            throw new CompletionException(new GameServiceException(
                    "Game Service spirit-root detection failed with HTTP " + response.statusCode()));
        }
        try {
            return objectMapper.readValue(response.body(), SpiritRootDetectionResult.class);
        } catch (IOException error) {
            throw new CompletionException(
                    new GameServiceException("Game Service spirit-root detection response was invalid", error));
        }
    }

    private static URI normalizeBaseUri(URI uri) {
        String value = uri.toString();
        return value.endsWith("/") ? uri : URI.create(value + "/");
    }

    private HttpRequest.Builder newRequestBuilder(String path) {
        return HttpRequest.newBuilder(baseUri.resolve(path))
                .version(HttpClient.Version.HTTP_1_1)
                .timeout(REQUEST_TIMEOUT);
    }

    private static String requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank");
        }
        return value;
    }

    private record PlayerLoginRequest(UUID minecraftUuid, String playerName) {}

    private record QuestInteractionStateRequest(List<String> providerIds) {}

    private record QuestProviderRequest(String providerId) {}

    private record QuestTurnInRequest(String providerId, List<UUID> inventoryItemInstanceIds) {}

    private record LearnTechniqueRequest(UUID itemInstanceId) {}

    private record ErrorEnvelope(ErrorBody error) {}

    private record ErrorBody(String code, String message, boolean retryable) {}
}
