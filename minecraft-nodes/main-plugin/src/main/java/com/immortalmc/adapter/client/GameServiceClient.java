package com.immortalmc.adapter.client;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;

public final class GameServiceClient {
    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(2);

    private final URI baseUri;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;

    public GameServiceClient(URI baseUri, HttpClient httpClient) {
        this(baseUri, httpClient, new ObjectMapper().setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE));
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

    private record PlayerLoginRequest(UUID minecraftUuid, String playerName) {}
}
