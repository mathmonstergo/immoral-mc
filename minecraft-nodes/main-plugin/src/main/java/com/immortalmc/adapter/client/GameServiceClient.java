package com.immortalmc.adapter.client;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;

public final class GameServiceClient {
    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(2);

    private final URI baseUri;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;

    public GameServiceClient(URI baseUri, HttpClient httpClient) {
        this(baseUri, httpClient, new ObjectMapper());
    }

    GameServiceClient(URI baseUri, HttpClient httpClient, ObjectMapper objectMapper) {
        this.baseUri = normalizeBaseUri(Objects.requireNonNull(baseUri, "baseUri"));
        this.httpClient = Objects.requireNonNull(httpClient, "httpClient");
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper");
    }

    public CompletableFuture<HealthCheckResult> checkHealth() {
        HttpRequest request = HttpRequest.newBuilder(baseUri.resolve("/health"))
                .timeout(REQUEST_TIMEOUT)
                .GET()
                .build();

        return httpClient
                .sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(this::parseHealthResponse);
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

    private static URI normalizeBaseUri(URI uri) {
        String value = uri.toString();
        return value.endsWith("/") ? uri : URI.create(value + "/");
    }
}
